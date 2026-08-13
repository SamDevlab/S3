from __future__ import annotations

import json
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
    "return_constant": ("fn main() -> i64:\n    return 1\n", 1),
    "integer_arithmetic": ("fn main() -> i64:\n    return 7 + 6 + 3\n", 16),
    "branch": ("""fn main() -> trit:
    match 0:
        0:
            return -1
        1:
            return 0
        -1:
            return 0
""", -1),
    "call": ("""fn inc(x: i64) -> i64:
    return x + 1
fn main() -> i64:
    return inc(41)
""", 42),
    "trit": ("""fn main() -> trit:
    return (-1) == (-1)
""", -1),
    "tryte": ("fn main() -> tryte:\n    return 7 + 6 + 3\n", 16),
    "f64": ("""fn main() -> trit:
    return 1.5 + 1.5 == 3.0
""", -1),
    "reference": ("""fn read(xs: &[tryte]) -> tryte:
    return xs[0]
fn main() -> tryte:
    values: tryte[1] = [7]
    return read(&values)
""", 7),
    "slice": ("""fn read(xs: &[tryte]) -> tryte:
    return xs[0] + xs[1]
fn main() -> tryte:
    values: tryte[2] = [7, 8]
    return read(&values)
""", 15),
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    toolchain = NativeToolchain.detect()
    result: dict[str, object] = {
        "protocol": "external repeated native process launch to first correct output",
        "candidate_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "run_count": 15,
        "cold_cache_controlled": False,
        "workloads": {},
    }
    for name, (source, expected) in WORKLOADS.items():
        compilation = compile_source(source, "O1", mode=SyntaxMode.V0_6)
        assert execute_ir(compilation.ir) == expected
        executable = toolchain.build(
            X8664Backend().generate(compilation.assembly), OUT / name, keep_assembly=OUT / f"{name}.s"
        )
        samples: list[int] = []
        outputs: list[str] = []
        for _ in range(result["run_count"]):
            started = time.perf_counter_ns()
            completed = subprocess.run([str(executable)], capture_output=True, text=True, check=False)
            samples.append(time.perf_counter_ns() - started)
            outputs.append(completed.stdout.strip())
            assert completed.returncode == 0
            assert completed.stdout.strip() == f"program returned: {expected}"
        result["workloads"][name] = {
            "expected_result": expected,
            "emulator_result": expected,
            "native_result": outputs[0],
            "differential_match": True,
            "first_useful_work_definition": "first correct program output",
            "median_ns": statistics.median(samples),
            "p25_ns": statistics.quantiles(samples, n=4, method="inclusive")[0],
            "p75_ns": statistics.quantiles(samples, n=4, method="inclusive")[2],
            "min_ns": min(samples),
            "max_ns": max(samples),
            "samples_ns": samples,
        }
    (OUT / "first_useful_work.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
