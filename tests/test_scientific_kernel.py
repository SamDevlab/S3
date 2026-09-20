from __future__ import annotations

import math
import platform

import pytest

from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend, generate_native_assembly
from bootstrap.s3.pipeline import compile_source, run_source


DIRECT_SSD_SOURCE = """\
fn direct_ssd(left: &f64_vector, right: &f64_vector) -> f64:
    mut length: i64 = f64_vector_len(left)
    match length == f64_vector_len(right):
        -1:
            mut index: i64 = 0
            mut total: f64 = 0.0
            while index < length:
                mut delta: f64 = f64_vector_get(left, index) - f64_vector_get(right, index)
                total = total + delta * delta
                index = index + 1
            return total
        0:
            return -1.0
        1:
            return -1.0
fn main() -> f64:
    mut left: f64_vector = f64_vector_new(3)
    mut right: f64_vector = f64_vector_new(3)
    discard f64_vector_push(&mut left, 1.0)
    discard f64_vector_push(&mut left, 2.0)
    discard f64_vector_push(&mut left, 3.0)
    discard f64_vector_push(&mut right, 2.0)
    discard f64_vector_push(&mut right, 4.0)
    discard f64_vector_push(&mut right, 6.0)
    return direct_ssd(&left, &right)
"""

RMSD_SOURCE = DIRECT_SSD_SOURCE.replace(
    "fn main() -> f64:\n",
    "fn rmsd(left: &f64_vector, right: &f64_vector) -> f64:\n"
    "    mut length: i64 = f64_vector_len(left)\n"
    "    match length == 0:\n"
    "        -1:\n"
    "            return -1.0\n"
    "        0:\n"
    "            return sqrt(direct_ssd(left, right) / to_f64(length))\n"
    "        1:\n"
    "            return -1.0\n"
    "fn main() -> f64:\n",
    1,
).replace(
    "    return direct_ssd(&left, &right)\n",
    "    return rmsd(&left, &right)\n",
    1,
)

NATIVE_RMSD_SOURCE = RMSD_SOURCE.replace(
    "fn main() -> f64:",
    "fn main() -> trit:",
    1,
).replace(
    "    return rmsd(&left, &right)\n",
    "    return rmsd(&left, &right) == 2.160246899469287\n",
    1,
)


def test_direct_f64_vector_ssd_reuses_existing_reference_and_call_contracts() -> None:
    compilation = compile_source(DIRECT_SSD_SOURCE)
    assert compilation.semantic_model.contains_dynamic
    assert run_source(DIRECT_SSD_SOURCE, optimization="O0") == 14.0
    assert run_source(DIRECT_SSD_SOURCE, optimization="O1") == 14.0


def test_sqrt_uses_existing_dynamic_call_contract_and_ieee_edge_cases() -> None:
    assert run_source("fn main() -> f64:\n    return sqrt(9.0)\n") == 3.0
    negative = run_source("fn main() -> f64:\n    return sqrt(-1.0)\n")
    assert math.isnan(negative)
    assert run_source("fn main() -> f64:\n    return sqrt(-0.0)\n") == 0.0
    assert math.copysign(1.0, run_source("fn main() -> f64:\n    return sqrt(-0.0)\n")) < 0.0


def test_rmsd_composes_direct_ssd_and_sqrt() -> None:
    compilation = compile_source(RMSD_SOURCE)
    assert any(
        instruction.callee == "sqrt"
        for function in compilation.assembly.functions
        for instruction in function.instructions
    )
    expected = math.sqrt(14.0 / 3.0)
    assert run_source(RMSD_SOURCE, optimization="O0") == expected
    assert run_source(RMSD_SOURCE, optimization="O1") == expected


@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="native qualification requires Linux x86-64",
)
def test_rmsd_native_uses_sse2_runtime_helper(tmp_path) -> None:
    toolchain = NativeToolchain.detect()
    source = NATIVE_RMSD_SOURCE
    compilation = compile_source(source)
    assembly = X8664Backend().generate(compilation.assembly)
    assert "sqrtsd xmm0,xmm0" in assembly
    executable = toolchain.build(assembly, tmp_path / "rmsd")
    completed = toolchain.run(executable)
    assert completed.returncode == 0
    assert completed.stdout == "program returned: -1\n"
