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
    "scalar_i64": ("""fn main() -> i64:
    return 7 + 6 + 3
""", 16),
    "scalar_tryte": ("""fn main() -> tryte:
    return 7 + 6 + 3
""", 16),
    "integer_loop": ("""fn main() -> i64:
    mut i: i64 = 0
    mut total: i64 = 0
    while i < 10:
        total = total + i
        i = i + 1
    return total
""", 45),
    "nested_loop": ("""fn main() -> tryte:
    mut outer: tryte = 0
    mut total: tryte = 0
    while outer < 3:
        mut inner: tryte = 0
        while inner < 3:
            total = total + outer + inner
            inner = inner + 1
        outer = outer + 1
    return total
""", 18),
    "branch_heavy": ("""fn main() -> tryte:
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
""", 18),
    "call_heavy": ("""fn add(a: tryte, b: tryte) -> tryte:
    return a + b
fn twice(x: tryte) -> tryte:
    return add(x, x)
fn main() -> tryte:
    return twice(add(3, 4))
""", 14),
    "slice_reference": ("""fn sum(xs: &[tryte]) -> tryte:
    return xs[0] + xs[1]
fn mutate(xs: &mut [i64]) -> trit:
    xs[0] = 9
    return xs[0] == 9
fn main() -> trit:
    mut values: i64[2] = [1, 2]
    small: tryte[2] = [10, 20]
    return (mutate(&mut values) == -1) & (sum(&small) == 30)
""", -1),
    "f64_kernel": ("""fn scale(a: f64, b: f64) -> f64:
    return a * b + 0.5
fn main() -> trit:
    return scale(1.5, 2.0) == 3.5
""", -1),
    "trit_kernel": ("""fn main() -> trit:
    mut a: trit = -1
    mut b: trit = 1
    return ((a & b) | (~a)) == 1
""", -1),
    "fixed_array": ("""fn main() -> i64:
    values: i64[3] = [1, 2, 3]
    return values[0] + values[1] + values[2]
""", 6),
    "array_loop": ("""fn main() -> i64:
    mut values: i64[3] = [1, 2, 3]
    mut i: i64 = 0
    mut total: i64 = 0
    while i < 3:
        total = total + values[i]
        i = i + 1
    return total
""", 6),
    "call_chain": ("""fn inc(x: i64) -> i64:
    return x + 1
fn twice(x: i64) -> i64:
    return inc(inc(x))
fn main() -> i64:
    return twice(40)
""", 42),
}


INSTRUCTION = re.compile(r"^\s*[0-9a-f]+:\s+[0-9a-f ]+\s+(\S+)")


def measure_disassembly(executable: Path) -> dict[str, int]:
    text = subprocess.check_output(
        ["objdump", "-d", "--section=.text", str(executable)], text=True
    )
    mnemonics = [m.group(1).lower() for line in text.splitlines() if (m := INSTRUCTION.match(line))]
    section_table = subprocess.check_output(["readelf", "-SW", str(executable)], text=True)
    text_bytes = None
    for line in section_table.splitlines():
        if re.search(r"\]\s+\.text\s+", line):
            text_bytes = int(line.split()[6], 16)
            break
    if text_bytes is None:
        raise RuntimeError("could not locate .text section")
    memory = ("mov", "movzx", "movsx", "lea", "push", "pop")
    branches = ("j", "loop")
    return {
        "native_static_instructions": len(mnemonics),
        "native_load_store_address": sum(m.startswith(memory) for m in mnemonics),
        "native_branches": sum(m.startswith(branches) for m in mnemonics),
        "native_calls": sum(m in {"call", "callq"} for m in mnemonics),
        "native_frame_accesses": text.count("[rbp"),
        "text_bytes": text_bytes,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    toolchain = NativeToolchain.detect()
    result: dict[str, object] = {
        "protocol": "O1 emulator plus Linux x86-64 native build/run",
        "candidate_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "workload_count": len(WORKLOADS),
        "workloads": {},
    }
    for name, (source, expected) in WORKLOADS.items():
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
        result["workloads"][name] = {
            "expected": expected,
            "emulator_result": observed,
            "native_results": native_results,
            "semantics": "PASS",
            "compile_time_ns_median": statistics.median(compile_times),
            "native_run_time_ns_median": statistics.median(native_times),
            "assembly_instruction_count": len(ops),
            **measure_disassembly(executable),
            "assembly_loads": sum(op.startswith(("TLOAD", "TALOAD", "TREFLOAD", "TSLOAD")) for op in ops),
            "assembly_stores": sum(op.startswith(("TSTORE", "TASTORE", "TREFSTORE", "TSSTORE")) for op in ops),
            "assembly_branches": sum(op.startswith(("TBRANCH", "TJMP")) for op in ops),
            "assembly_calls": sum(op == "TCALL" for op in ops),
        }
    (OUT / "post_p7_obligation_profile.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
