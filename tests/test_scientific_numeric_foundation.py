from __future__ import annotations

import math
import platform

import pytest

from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_sources
from bootstrap.s3.stdlib import standard_library_sources


def _compile(main: str, optimization: OptimizationLevel = OptimizationLevel.O0):
    sources = standard_library_sources(modules=("s3.v1.science",))
    sources["main.s3"] = "module main\n" + main
    return compile_sources(sources, optimization=optimization)


def _vectors(left: tuple[float, ...], right: tuple[float, ...]) -> str:
    lines = [
        f"    mut left: f64_vector = f64_vector_new({len(left)})",
        f"    mut right: f64_vector = f64_vector_new({len(right)})",
    ]
    lines.extend(f"    discard f64_vector_push(&mut left, {value!r})" for value in left)
    lines.extend(f"    discard f64_vector_push(&mut right, {value!r})" for value in right)
    return "\n".join(lines) + "\n"


def _run(main: str, optimization: OptimizationLevel = OptimizationLevel.O0):
    return execute_ir(_compile(main, optimization).ir)


def test_reductions_define_empty_single_mixed_sign_and_population_variance() -> None:
    source = (
        "from s3.v1.science import sum\n"
        "from s3.v1.science import mean\n"
        "from s3.v1.science import variance\n"
        "fn main() -> f64:\n"
        "    mut empty: f64_vector = f64_vector_new(0)\n"
        "    mut one: f64_vector = f64_vector_new(1)\n"
        "    discard f64_vector_push(&mut one, -4.0)\n"
        "    mut values: f64_vector = f64_vector_new(4)\n"
        "    discard f64_vector_push(&mut values, -2.0)\n"
        "    discard f64_vector_push(&mut values, 0.0)\n"
        "    discard f64_vector_push(&mut values, 2.0)\n"
        "    discard f64_vector_push(&mut values, 4.0)\n"
        "    return sum(&empty) + sum(&one) + mean(&empty) + mean(&values) "
        "+ variance(&one) + variance(&values)\n"
    )
    expected = 0.0 - 4.0 + 0.0 + 1.0 + 0.0 + 5.0
    assert _run(source, OptimizationLevel.O0) == expected
    assert _run(source, OptimizationLevel.O1) == expected


def test_scientific_binary_kernels_match_contract_and_report_invalid_lengths() -> None:
    source = (
        "from s3.v1.science import F64Result\n"
        "from s3.v1.science import dot\n"
        "from s3.v1.science import squared_distance\n"
        "from s3.v1.science import distance\n"
        "from s3.v1.science import l2_norm\n"
        "from s3.v1.science import rmsd\n"
        "fn mismatch(value: trit) -> i64:\n"
        "    match value:\n"
        "        -1:\n"
        "            return 0\n"
        "        0:\n"
        "            return 1\n"
        "        1:\n"
        "            return 1\n"
        "fn main() -> i64:\n"
        + _vectors((1.0, 3.0), (2.0, 4.0))
        + "    product: F64Result = dot(&left, &right)\n"
        + "    square: F64Result = squared_distance(&left, &right)\n"
        + "    length: F64Result = distance(&left, &right)\n"
        + "    root_mean_square: F64Result = rmsd(&left, &right)\n"
        + "    mut short: f64_vector = f64_vector_new(1)\n"
        + "    discard f64_vector_push(&mut short, 1.0)\n"
        + "    mut failures: i64 = mismatch(product.status == 0)\n"
        + "    failures = failures + mismatch(product.value == 14.0)\n"
        + "    failures = failures + mismatch(square.value == 2.0)\n"
        + "    failures = failures + mismatch(length.value == sqrt(2.0))\n"
        + "    failures = failures + mismatch(l2_norm(&left) == sqrt(10.0))\n"
        + "    failures = failures + mismatch(root_mean_square.value == 1.0)\n"
        + "    failures = failures + mismatch(dot(&left, &short).status == 1)\n"
        + "    failures = failures + mismatch(squared_distance(&left, &short).status == 1)\n"
        + "    failures = failures + mismatch(distance(&left, &short).status == 1)\n"
        + "    failures = failures + mismatch(rmsd(&left, &short).status == 1)\n"
        + "    return failures\n"
    )
    assert _run(source, OptimizationLevel.O0) == 0
    assert _run(source, OptimizationLevel.O1) == 0


def test_empty_binary_and_rmsd_statuses_are_explicit() -> None:
    source = (
        "from s3.v1.science import F64Result\n"
        "from s3.v1.science import dot\n"
        "from s3.v1.science import squared_distance\n"
        "from s3.v1.science import distance\n"
        "from s3.v1.science import l2_norm\n"
        "from s3.v1.science import rmsd\n"
        "fn mismatch(value: trit) -> i64:\n"
        "    match value:\n"
        "        -1:\n"
        "            return 0\n"
        "        0:\n"
        "            return 1\n"
        "        1:\n"
        "            return 1\n"
        "fn main() -> i64:\n"
        "    mut left: f64_vector = f64_vector_new(0)\n"
        "    mut right: f64_vector = f64_vector_new(0)\n"
        "    mut failures: i64 = mismatch(dot(&left, &right).status == 0)\n"
        "    failures = failures + mismatch(squared_distance(&left, &right).value == 0.0)\n"
        "    failures = failures + mismatch(distance(&left, &right).value == 0.0)\n"
        "    failures = failures + mismatch(l2_norm(&left) == 0.0)\n"
        "    failures = failures + mismatch(rmsd(&left, &right).status == 2)\n"
        "    return failures\n"
    )
    assert _run(source, OptimizationLevel.O0) == 0


def test_scientific_reductions_preserve_ieee_nan_and_infinity() -> None:
    source = (
        "from s3.v1.science import sum\n"
        "fn main() -> f64:\n"
        "    mut values: f64_vector = f64_vector_new(2)\n"
        "    discard f64_vector_push(&mut values, sqrt(-1.0))\n"
        "    discard f64_vector_push(&mut values, 1.0)\n"
        "    return sum(&values)\n"
    )
    assert math.isnan(_run(source, OptimizationLevel.O0))
    assert math.isnan(_run(source, OptimizationLevel.O1))


@pytest.mark.skipif(
    platform.system() != "Linux"
    or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="native scientific qualification requires Linux x86-64",
)
def test_scientific_kernels_native_match_hosted_contracts(tmp_path) -> None:
    toolchain = NativeToolchain.detect()
    source = (
        "from s3.v1.science import F64Result\n"
        "from s3.v1.science import sum\n"
        "from s3.v1.science import dot\n"
        "from s3.v1.science import mean\n"
        "from s3.v1.science import variance\n"
        "from s3.v1.science import squared_distance\n"
        "from s3.v1.science import distance\n"
        "from s3.v1.science import l2_norm\n"
        "from s3.v1.science import rmsd\n"
        "fn mismatch(value: trit) -> i64:\n"
        "    match value:\n"
        "        -1:\n"
        "            return 0\n"
        "        0:\n"
        "            return 1\n"
        "        1:\n"
        "            return 1\n"
        "fn main() -> i64:\n"
        + _vectors((-2.0, 0.0, 2.0, 4.0), (1.0, 1.0, 1.0, 1.0))
        + "    mut short: f64_vector = f64_vector_new(1)\n"
        + "    discard f64_vector_push(&mut short, 1.0)\n"
        + "    mut failures: i64 = mismatch(sum(&left) == 4.0)\n"
        + "    failures = failures + mismatch(mean(&left) == 1.0)\n"
        + "    failures = failures + mismatch(variance(&left) == 5.0)\n"
        + "    failures = failures + mismatch(dot(&left, &right).value == 4.0)\n"
        + "    failures = failures + mismatch(squared_distance(&left, &right).value == 20.0)\n"
        + "    failures = failures + mismatch(distance(&left, &right).value == sqrt(20.0))\n"
        + "    failures = failures + mismatch(l2_norm(&left) == sqrt(24.0))\n"
        + "    failures = failures + mismatch(rmsd(&left, &right).value == sqrt(5.0))\n"
        + "    failures = failures + mismatch(dot(&left, &short).status == 1)\n"
        + "    failures = failures + mismatch(squared_distance(&left, &short).status == 1)\n"
        + "    return failures\n"
    )
    compilation = _compile(source)
    assembly = X8664Backend().generate(compilation.assembly)
    executable = toolchain.build(assembly, tmp_path / "scientific-kernels")
    completed = toolchain.run(executable)
    assert completed.returncode == 0
    assert completed.stdout == "program returned: 0\n"


def test_scientific_result_type_and_module_exports_are_stable() -> None:
    source = _compile(
        "from s3.v1.science import F64Result\n"
        "fn main() -> i64:\n"
        "    mut value: F64Result = F64Result(status=0, value=2.5)\n"
        "    return value.status\n"
    )
    assert execute_ir(source.ir) == 0
