from __future__ import annotations

from dataclasses import dataclass
import random


@dataclass(frozen=True, slots=True)
class GeneratedDifferentialCase:
    seed: int
    source: str
    expected: int


def generate_cases(
    seeds: tuple[int, ...],
) -> tuple[GeneratedDifferentialCase, ...]:
    cases: list[GeneratedDifferentialCase] = []
    for seed in seeds:
        rng = random.Random(seed)
        left = rng.randint(-100, 100)
        right = rng.randint(-100, 100)
        offset = rng.randint(-20, 20)
        expected = left + right + offset
        cases.append(
            GeneratedDifferentialCase(
                seed=seed,
                source=(
                    "fn main() -> tryte:\n"
                    f"    mut left: tryte = {left}\n"
                    f"    mut right: tryte = {right}\n"
                    f"    return left + right + {offset}\n"
                ),
                expected=expected,
            )
        )
    return tuple(cases)
