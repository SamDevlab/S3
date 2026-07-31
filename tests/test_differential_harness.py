from __future__ import annotations

from bootstrap.s3.diagnostics import DiagnosticCategory, DiagnosticCode
from tests.support.differential import (
    DifferentialCase,
    DifferentialExpectation,
    assert_hosted_equivalence,
)


def test_hosted_harness_compares_o0_o1_return_and_memory() -> None:
    observations = assert_hosted_equivalence(
        DifferentialCase(
            name="mutable-array-observable-memory",
            source=(
                "fn main() -> tryte:\n"
                "    mut values: tryte[3] = [0, 0, 0]\n"
                "    mut index: tryte = 0\n"
                "    values[index] = 5\n"
                "    index = 1\n"
                "    values[index] = 7\n"
                "    return values[0]\n"
            ),
            expectation=DifferentialExpectation(
                return_value=5,
                memory=((0, (5, 7, 0)), (1, (1,))),
            ),
            observable_memory=(0, 1),
            exercised_passes=("dse", "ssa", "de-ssa"),
        )
    )

    assert tuple(result.optimization.value for result in observations) == (
        "O0",
        "O1",
    )
    assert all(result.succeeded for result in observations)


def test_hosted_harness_compares_stable_runtime_error_category() -> None:
    observations = assert_hosted_equivalence(
        DifferentialCase(
            name="runtime-overflow-category",
            source=(
                "fn main() -> tryte:\n"
                "    mut value: tryte = 364\n"
                "    return value + 1\n"
            ),
            expectation=DifferentialExpectation(
                error_category=DiagnosticCategory.OVERFLOW,
                error_code=DiagnosticCode.RUNTIME_OVERFLOW,
            ),
            exercised_passes=("ssa",),
        )
    )

    assert {result.error_category for result in observations} == {"overflow"}
    assert {result.error_code for result in observations} == {
        "S3E_RUNTIME_OVERFLOW",
    }


def test_hosted_harness_compares_bounds_error_category() -> None:
    observations = assert_hosted_equivalence(
        DifferentialCase(
            name="runtime-bounds-category",
            source=(
                "fn read(index: tryte) -> tryte:\n"
                "    values: tryte[1] = [1]\n"
                "    return values[index]\n"
                "fn main() -> tryte:\n"
                "    return read(1)\n"
            ),
            expectation=DifferentialExpectation(
                error_category=DiagnosticCategory.BOUNDS,
                error_code=DiagnosticCode.RUNTIME_BOUNDS,
            ),
            exercised_passes=("ssa", "de-ssa"),
        )
    )

    assert {result.error_category for result in observations} == {"bounds"}
