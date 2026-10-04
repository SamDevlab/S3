from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import tracemalloc
from dataclasses import fields, is_dataclass
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bootstrap.s3.backends.x86_64.backend import X8664Backend
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source


def _source(function_count: int) -> str:
    lines = [
        "record WideRecord:",
        *(f"    field_{index:02d}: i64" for index in range(32)),
        "fn touch(input_record: WideRecord) -> i64:",
        "    return input_record.field_00 + input_record.field_31",
    ]
    helper_count = function_count - 2
    for index in range(helper_count):
        lines.extend(
            [
                f"fn work_{index:03d}(input: i64) -> i64:",
                "    mut value: i64 = input",
                "    mut cursor: i64 = 0",
                "    while cursor < 3:",
                "        match cursor <=> 1:",
                "            -1:",
                f"                value = value + {index % 7 + 1}",
                "            0:",
                "                match value <=> 0:",
                "                    -1:",
                "                        value = value + to_i64(-1)",
                "                    0:",
                "                        value = value + 2",
                "                    1:",
                "                        value = value + 1",
                "            1:",
                "                value = value + 3",
                "        cursor = cursor + 1",
                "    return value",
            ]
        )
    fields = ", ".join(f"field_{index:02d}={index}" for index in range(32))
    lines.extend(
        [
            "fn main() -> i64:",
            f"    mut seed: i64 = touch(WideRecord({fields}))",
            f"    return work_{helper_count - 1:03d}(seed)",
        ]
    )
    return "\n".join(lines) + "\n"


def _ast_node_count(root: object) -> int:
    ast_module = "bootstrap.s3.ast"
    seen: set[int] = set()

    def visit(value: object) -> int:
        if is_dataclass(value) and type(value).__module__ == ast_module:
            identity = id(value)
            if identity in seen:
                return 0
            seen.add(identity)
            return 1 + sum(visit(getattr(value, item.name)) for item in fields(value))
        if isinstance(value, (tuple, list)):
            return sum(visit(item) for item in value)
        if isinstance(value, dict):
            return sum(visit(item) for item in value.values())
        return 0

    return visit(root)


def _measure(
    function_count: int,
    *,
    native_dir: Path | None,
    gcc: str | None,
) -> tuple[dict[str, int | float | None], str]:
    source = _source(function_count)
    tracemalloc.start()
    started = perf_counter()
    compilation = compile_source(source, optimization=OptimizationLevel.O1)
    compile_seconds = perf_counter() - started
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    native_assembly = X8664Backend().generate(compilation.assembly)
    assembly_text = compilation.assembly.render()
    ir = compilation.ir
    ir_blocks = sum(len(function.blocks) for function in ir.functions)
    ir_instructions = sum(
        len(block.instructions)
        for function in ir.functions
        for block in function.blocks
    )
    helper_index = function_count - 3
    expected = 36 + helper_index % 7
    actual = execute_ir(ir)
    if actual != expected:
        raise RuntimeError(
            f"scale workload result mismatch for {function_count} functions: "
            f"expected {expected}, got {actual}"
        )
    native_binary_bytes: int | None = None
    if native_dir is not None and gcc is not None:
        assembly_path = native_dir / f"scale-{function_count}.s"
        executable_path = native_dir / f"scale-{function_count}"
        assembly_path.write_text(native_assembly, encoding="utf-8")
        subprocess.run(
            [gcc, "-nostartfiles", "-no-pie", str(assembly_path), "-o", str(executable_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        native_result = subprocess.run(
            [str(executable_path)], check=False, capture_output=True, text=True
        )
        if native_result.returncode != 0 or f"program returned: {expected}" not in native_result.stdout:
            raise RuntimeError(
                f"native scale result mismatch for {function_count} functions: "
                f"exit={native_result.returncode}; output={native_result.stdout!r}; "
                f"stderr={native_result.stderr!r}"
            )
        native_binary_bytes = executable_path.stat().st_size
    return (
        {
            "source_bytes": len(source.encode("utf-8")),
            "token_count": len(compilation.tokens),
            "function_count": len(compilation.ast.functions),
            "module_count": 1,
            "ast_node_count": _ast_node_count(compilation.ast),
            "ir_function_count": len(ir.functions),
            "ir_block_count": ir_blocks,
            "ir_instruction_count": ir_instructions,
            "compile_seconds_o1": round(compile_seconds, 6),
            "peak_traced_bytes": peak_bytes,
            "assembly_text_bytes": len(assembly_text.encode("utf-8")),
            "native_assembly_text_bytes": len(native_assembly.encode("utf-8")),
            "emulator_result": actual,
            "native_result": expected if native_binary_bytes is not None else None,
            "native_binary_bytes": native_binary_bytes,
        },
        native_assembly,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Measure normal S3 compiler scaling.")
    parser.add_argument(
        "--emit-native-asm",
        type=Path,
        help="write the largest probe's generated x86-64 assembly to this path",
    )
    parser.add_argument(
        "--native",
        action="store_true",
        help="assemble and execute every scale on Linux x86-64 with gcc",
    )
    args = parser.parse_args()

    native_dir: Path | None = None
    gcc: str | None = None
    if args.native:
        gcc = shutil.which("gcc")
        if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
            parser.error("--native requires Linux x86-64")
        if gcc is None:
            parser.error("--native requires gcc")
        native_dir = Path(tempfile.mkdtemp(prefix="s3-language-scale-native-"))

    results: list[dict[str, int | float | None]] = []
    largest_native_assembly = ""
    for function_count in (10, 25, 50, 100):
        result, native_assembly = _measure(
            function_count, native_dir=native_dir, gcc=gcc
        )
        results.append({"requested_functions": function_count, **result})
        largest_native_assembly = native_assembly
    if args.emit_native_asm:
        args.emit_native_asm.parent.mkdir(parents=True, exist_ok=True)
        args.emit_native_asm.write_text(largest_native_assembly, encoding="utf-8")
    print(
        json.dumps(
            {
                "probe": "language-maturity-normal-compiler-scale-v1",
                "optimization": "O1",
                "host_platform": f"{platform.system()} {platform.machine()}",
                "native_execution_measured": args.native,
                "results": results,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
