from __future__ import annotations

import json
import re
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(ROOT))

from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


WORKLOADS = {
    "jsmn_tokenizer": (ROOT / "examples/external/jsmn/jsmn_demo.s3", 3),
    "numeric_integer_loop": (None, 45),
    "nested_loop": (None, 18),
    "branch_heavy_scalar": (None, 18),
    "call_heavy_scalar": (None, 14),
    "slice_reference": (None, -1),
    "f64_scientific_kernel": (None, -1),
    "trit_heavy_small": (None, -1),
}

SOURCES = {
    "numeric_integer_loop": """fn main() -> i64:
    mut i: i64 = 0
    mut total: i64 = 0
    while i < 10:
        total = total + i
        i = i + 1
    return total
""",
    "nested_loop": """fn main() -> tryte:
    mut outer: tryte = 0
    mut total: tryte = 0
    while outer < 3:
        mut inner: tryte = 0
        while inner < 3:
            total = total + outer + inner
            inner = inner + 1
        outer = outer + 1
    return total
""",
    "branch_heavy_scalar": """fn main() -> tryte:
    mut value: tryte = 1
    mut result: tryte = 0
    while value < 10:
        match value <=> 5:
            -1:
                result = result + 1
            0:
                result = result + 2
            1:
                result = result + 3
        value = value + 1
    return result
""",
    "call_heavy_scalar": """fn add(a: tryte, b: tryte) -> tryte:
    return a + b
fn twice(x: tryte) -> tryte:
    return add(x, x)
fn main() -> tryte:
    return twice(add(3, 4))
""",
    "slice_reference": """fn sum(xs: &[tryte]) -> tryte:
    return xs[0] + xs[1]
fn mutate(xs: &mut [i64]) -> trit:
    xs[0] = 9
    return xs[0] == 9
fn main() -> trit:
    mut values: i64[2] = [1, 2]
    small: tryte[2] = [10, 20]
    return (mutate(&mut values) == -1) & (sum(&small) == 30)
""",
    "f64_scientific_kernel": """fn scale(a: f64, b: f64) -> f64:
    return a * b + 0.5
fn main() -> trit:
    return scale(1.5, 2.0) == 3.5
""",
    "trit_heavy_small": """fn main() -> trit:
    mut a: trit = -1
    mut b: trit = 1
    return ((a & b) | (~a)) == 1
""",
}


def source_for(name: str, path: Path | None) -> str:
    return path.read_text(encoding="utf-8") if path is not None else SOURCES[name]


def main() -> None:
    toolchain = NativeToolchain.detect()
    OUT.mkdir(parents=True, exist_ok=True)
    result: dict[str, object] = {
        "protocol": "O1 emulator plus Linux x86-64 native build/run",
        "samples": 3,
        "workloads": {},
    }
    for name, (path, expected) in WORKLOADS.items():
        source = source_for(name, path)
        compile_times: list[int] = []
        compilation = None
        for _ in range(3):
            started = time.perf_counter_ns()
            compilation = compile_source(source, "O1", mode=SyntaxMode.V0_6)
            compile_times.append(time.perf_counter_ns() - started)
        assert compilation is not None
        observed = execute_ir(compilation.ir)
        assert observed == expected, (name, observed, expected)
        assembly = X8664Backend().generate(compilation.assembly)
        assembly_path = OUT / f"{name}.s"
        executable = toolchain.build(assembly, OUT / name, keep_assembly=assembly_path)
        native_times: list[int] = []
        native_results: list[str] = []
        for _ in range(3):
            started = time.perf_counter_ns()
            completed = toolchain.run(executable)
            native_times.append(time.perf_counter_ns() - started)
            native_results.append(completed.stdout.strip())
            assert completed.returncode == 0, (name, completed.stderr)
            assert completed.stdout.strip() == f"program returned: {expected}", (name, completed.stdout)
        ops = [
            instruction.opcode.value
            for function in compilation.assembly.functions
            for instruction in function.instructions
        ]
        disassembly = subprocess.run(
            ["objdump", "-d", "--section=.text", str(executable)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        native_instructions = [
            line for line in disassembly.splitlines()
            if re.match(r"^\s*[0-9a-f]+:", line)
        ]
        native_mnemonics = [
            line.split("\t", 2)[-1].split(None, 1)[0]
            for line in native_instructions
            if "\t" in line
        ]
        section_table = subprocess.run(
            ["readelf", "-SW", str(executable)],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        text_bytes = None
        for line in section_table.splitlines():
            if re.search(r"\]\s+\.text\s+", line):
                fields = line.split()
                text_bytes = int(fields[6], 16)
                break
        result["workloads"][name] = {
            "expected": expected,
            "emulator_result": observed,
            "native_results": native_results,
            "semantics": "PASS",
            "compile_time_ns_median": statistics.median(compile_times),
            "native_run_time_ns_median": statistics.median(native_times),
            "assembly_instruction_count": len(ops),
            "text_bytes": text_bytes,
            "native_static_instruction_count": len(native_instructions),
            "native_load_store": sum(
                mnemonic.startswith(("mov", "movzx", "movsx", "lea"))
                for mnemonic in native_mnemonics
            ),
            "native_branches": sum(
                mnemonic.startswith(("j", "loop")) for mnemonic in native_mnemonics
            ),
            "native_calls": sum(mnemonic in {"call", "callq"} for mnemonic in native_mnemonics),
            "native_frame_accesses": sum("[rbp" in line for line in disassembly.splitlines()),
            "loads": sum(op.startswith(("TLOAD", "TALOAD", "TREFLOAD", "TSLOAD")) for op in ops),
            "stores": sum(op.startswith(("TSTORE", "TASTORE", "TREFSTORE", "TSSTORE")) for op in ops),
            "branches": sum(op.startswith(("TBRANCH", "TJMP")) for op in ops),
            "calls": sum(op == "TCALL" for op in ops),
            "returns": sum(op in {"TRET", "TRETURN"} for op in ops),
            "dynamic_metrics": "UNAVAILABLE_NO_SOUND_COUNTER",
        }
    OUT.joinpath("post_p4_native_reprofile.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
