"""Deterministic, signature-preserving reduction for Reliability Lab v2.

The reducer is deliberately independent of the compiler.  Callers provide an
evaluator for one exact source byte string, and a candidate is accepted only
when both its outcome and its failure signature remain unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping, Sequence

from tools.reliability_contract_v2 import (
    DEFAULT_RESOURCE_POLICY,
    NON_FAILURE_OUTCOMES,
    sha256_hex,
    validate_failure_signature,
)


@dataclass(frozen=True, slots=True)
class MinimizationObservation:
    """The only evaluator result fields relevant to reduction."""

    outcome: str
    failure_signature: str | None

    def __post_init__(self) -> None:
        validate_failure_signature(self.outcome, self.failure_signature)

    @classmethod
    def from_value(cls, value: object) -> "MinimizationObservation":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            outcome = value.get("outcome")
            signature = value.get("failure_signature")
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            if len(value) != 2:
                raise TypeError("evaluator tuple must contain outcome and signature")
            outcome, signature = value
        else:
            raise TypeError("evaluator must return an outcome/signature pair")
        if not isinstance(outcome, str):
            raise TypeError("evaluator outcome must be a string")
        if signature is not None and not isinstance(signature, str):
            raise TypeError("evaluator failure_signature must be a string or None")
        return cls(outcome, signature)


@dataclass(frozen=True, slots=True)
class MinimizationResult:
    """Immutable evidence from one bounded minimization run."""

    initial_source_sha256: str
    minimized_source_sha256: str
    initial_bytes: int
    minimized_bytes: int
    initial_lines: int
    minimized_lines: int
    expected_outcome: str
    expected_failure_signature: str | None
    evaluations: int
    accepted_reductions: int
    budget_exhausted: bool
    minimized_source: bytes

    @property
    def source(self) -> bytes:
        """Compatibility spelling for callers interested in the final bytes."""
        return self.minimized_source

    @property
    def reduced(self) -> bool:
        return self.accepted_reductions > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "s3.reliability.minimization.v1",
            "initial_source_sha256": self.initial_source_sha256,
            "minimized_source_sha256": self.minimized_source_sha256,
            "initial_bytes": self.initial_bytes,
            "minimized_bytes": self.minimized_bytes,
            "initial_lines": self.initial_lines,
            "minimized_lines": self.minimized_lines,
            "expected_outcome": self.expected_outcome,
            "expected_failure_signature": self.expected_failure_signature,
            "evaluations": self.evaluations,
            "accepted_reductions": self.accepted_reductions,
            "budget_exhausted": self.budget_exhausted,
        }


Evaluator = Callable[[bytes], object]


def _line_count(source: bytes) -> int:
    return len(source.splitlines())


def _validate_budget(max_evaluations: int) -> None:
    if (
        isinstance(max_evaluations, bool)
        or not isinstance(max_evaluations, int)
        or max_evaluations < 1
    ):
        raise ValueError("max_evaluations must be a positive integer")
    if max_evaluations > DEFAULT_RESOURCE_POLICY.minimizer_max_evaluations:
        raise ValueError("max_evaluations exceeds frozen minimizer_max_evaluations")


def minimize_source(
    source: bytes,
    evaluator: Evaluator,
    *,
    expected_outcome: str,
    expected_failure_signature: str | None,
    max_evaluations: int = DEFAULT_RESOURCE_POLICY.minimizer_max_evaluations,
) -> MinimizationResult:
    """Reduce ``source`` while preserving the exact expected failure identity.

    Reduction order is fixed: contiguous source lines, then contiguous bytes.
    The evaluator is called at most ``max_evaluations`` times, including the
    initial identity check.  A budget boundary returns the best proven source;
    it never accepts an unverified candidate.
    """
    if not isinstance(source, bytes):
        raise TypeError("source must be bytes")
    if len(source) > DEFAULT_RESOURCE_POLICY.source_max_bytes:
        raise ValueError("source exceeds frozen source_max_bytes")
    _validate_budget(max_evaluations)
    validate_failure_signature(expected_outcome, expected_failure_signature)

    evaluations = 0
    accepted = 0
    budget_exhausted = False

    def reproduces(candidate: bytes) -> bool:
        nonlocal evaluations, budget_exhausted
        if evaluations >= max_evaluations:
            budget_exhausted = True
            return False
        observation = MinimizationObservation.from_value(evaluator(candidate))
        evaluations += 1
        return (
            observation.outcome == expected_outcome
            and observation.failure_signature == expected_failure_signature
        )

    if not reproduces(source):
        raise ValueError("initial source does not reproduce the expected failure")

    current = source

    def reduce_units(units: list[bytes]) -> list[bytes]:
        nonlocal current, accepted, budget_exhausted
        if len(units) < 2:
            return units
        granularity = 2
        while len(units) >= 2 and evaluations < max_evaluations:
            chunk_size = (len(units) + granularity - 1) // granularity
            reduced = False
            for start in range(0, len(units), chunk_size):
                end = min(len(units), start + chunk_size)
                candidate_units = units[:start] + units[end:]
                candidate = b"".join(candidate_units)
                if len(candidate) >= len(current) or candidate == current:
                    continue
                if reproduces(candidate):
                    current = candidate
                    units = candidate_units
                    accepted += 1
                    granularity = max(2, granularity - 1)
                    reduced = True
                    break
            if budget_exhausted:
                break
            if reduced:
                continue
            if granularity >= len(units):
                break
            granularity = min(len(units), granularity * 2)
        if evaluations >= max_evaluations:
            budget_exhausted = True
        return units

    lines = source.splitlines(keepends=True)
    reduce_units(lines)

    if evaluations < max_evaluations and len(current) >= 2:
        reduce_units([bytes((value,)) for value in current])
    elif evaluations >= max_evaluations:
        budget_exhausted = True

    return MinimizationResult(
        initial_source_sha256=sha256_hex(source),
        minimized_source_sha256=sha256_hex(current),
        initial_bytes=len(source),
        minimized_bytes=len(current),
        initial_lines=_line_count(source),
        minimized_lines=_line_count(current),
        expected_outcome=expected_outcome,
        expected_failure_signature=expected_failure_signature,
        evaluations=evaluations,
        accepted_reductions=accepted,
        budget_exhausted=budget_exhausted,
        minimized_source=current,
    )


def minimize_failure(
    source: bytes,
    evaluator: Evaluator,
    *,
    expected_outcome: str,
    expected_failure_signature: str | None,
    max_evaluations: int = DEFAULT_RESOURCE_POLICY.minimizer_max_evaluations,
) -> MinimizationResult:
    """Named alias emphasizing that only failures are normally minimized."""
    if expected_outcome in NON_FAILURE_OUTCOMES:
        raise ValueError("minimize_failure requires a failure outcome")
    return minimize_source(
        source,
        evaluator,
        expected_outcome=expected_outcome,
        expected_failure_signature=expected_failure_signature,
        max_evaluations=max_evaluations,
    )


reduce_source = minimize_source
