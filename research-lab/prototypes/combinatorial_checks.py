"""Bounded exact combinatorial-structure checks for S3 research.

These helpers are intentionally exponential and are meant for tiny ground sets.
They are counterexample finders/oracles, not production compiler algorithms.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
from typing import Callable, Hashable, Iterable, Iterator, TypeVar


T = TypeVar("T", bound=Hashable)


def powerset(items: Iterable[T]) -> Iterator[frozenset[T]]:
    ordered = tuple(items)
    for size in range(len(ordered) + 1):
        for subset in combinations(ordered, size):
            yield frozenset(subset)


@dataclass(frozen=True, slots=True)
class MatroidViolation:
    axiom: str
    a: frozenset[Hashable]
    b: frozenset[Hashable] | None = None
    detail: str = ""


def find_matroid_violation(
    ground: Iterable[T],
    independent: Callable[[frozenset[T]], bool],
    *,
    max_ground_size: int = 12,
) -> MatroidViolation | None:
    """Return a minimal-ish hereditary/exchange violation, or None.

    The test assumes the empty set should be independent and checks the standard
    finite independent-set axioms.  Enumeration order favors small witnesses.
    """

    ground_tuple = tuple(ground)
    if len(ground_tuple) > max_ground_size:
        raise ValueError("ground set too large for exhaustive matroid check")

    subsets = tuple(powerset(ground_tuple))
    if not independent(frozenset()):
        return MatroidViolation("empty-set", frozenset(), detail="empty set is not independent")

    # Hereditary property: every subset of an independent set is independent.
    for b in sorted(subsets, key=lambda s: (len(s), tuple(map(repr, sorted(s, key=repr))))):
        if not independent(b):
            continue
        for a in powerset(tuple(sorted(b, key=repr))):
            if not independent(a):
                return MatroidViolation(
                    "hereditary",
                    frozenset(a),
                    frozenset(b),
                    detail="subset of an independent set is not independent",
                )

    independent_sets = tuple(s for s in subsets if independent(s))
    # Exchange: if |A| < |B| there is x in B\A with A+x independent.
    for a in sorted(independent_sets, key=lambda s: (len(s), tuple(map(repr, sorted(s, key=repr))))):
        for b in sorted(independent_sets, key=lambda s: (len(s), tuple(map(repr, sorted(s, key=repr))))):
            if len(a) >= len(b):
                continue
            candidates = tuple(sorted(b - a, key=repr))
            if not any(independent(a | {x}) for x in candidates):
                return MatroidViolation(
                    "exchange",
                    frozenset(a),
                    frozenset(b),
                    detail=f"no x in B\\A extends A; candidates={candidates!r}",
                )
    return None


@dataclass(frozen=True, slots=True)
class SubmodularityViolation:
    a: frozenset[Hashable]
    b: frozenset[Hashable]
    lhs: float
    rhs: float


def find_submodularity_violation(
    ground: Iterable[T],
    value: Callable[[frozenset[T]], float],
    *,
    tolerance: float = 1e-12,
    max_ground_size: int = 10,
) -> SubmodularityViolation | None:
    """Check F(A)+F(B) >= F(A∩B)+F(A∪B) exhaustively."""

    ground_tuple = tuple(ground)
    if len(ground_tuple) > max_ground_size:
        raise ValueError("ground set too large for exhaustive submodularity check")
    subsets = tuple(powerset(ground_tuple))
    values = {subset: float(value(subset)) for subset in subsets}

    for a in subsets:
        for b in subsets:
            lhs = values[a] + values[b]
            rhs = values[a & b] + values[a | b]
            if lhs + tolerance < rhs:
                return SubmodularityViolation(a, b, lhs, rhs)
    return None
