from __future__ import annotations

import pytest

from tests.support.differential import (
    DifferentialCase,
    DifferentialExpectation,
    assert_hosted_equivalence,
)
from tests.support.generated_differential import generate_cases


pytestmark = pytest.mark.s3_differential

SEEDS = (11, 29, 47, 83, 101, 137, 173, 211)


def test_generated_differential_cases_are_seed_reproducible() -> None:
    first = generate_cases(SEEDS)
    second = generate_cases(SEEDS)

    assert first == second
    assert tuple(case.seed for case in first) == SEEDS
    assert all(-220 <= case.expected <= 220 for case in first)


@pytest.mark.parametrize("case", generate_cases(SEEDS), ids=lambda case: f"seed-{case.seed}")
def test_generated_cases_match_o0_o1(case) -> None:
    observations = assert_hosted_equivalence(
        DifferentialCase(
            name=f"generated-seed-{case.seed}",
            source=case.source,
            expectation=DifferentialExpectation(return_value=case.expected),
            tags=("generated", "seeded"),
        )
    )

    assert tuple(observation.return_value for observation in observations) == (
        case.expected,
        case.expected,
    )
