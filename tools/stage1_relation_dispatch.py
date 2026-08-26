"""Relation-safe bank dispatch helpers for generated Stage1 S3 candidates.

Preparation/test tooling only. This module does not mutate the canonical S3
compiler and is not a compiler backend.

S3 relation rule:
- ==, !=, <, <=, >, >= are boolean trit predicates: true=-1, false=0.
- <=> is ordered three-way comparison: less=-1, equal=0, greater=1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


BOOLEAN_TRUE = -1
BOOLEAN_FALSE = 0
BOOLEAN_INVALID = 1
THREE_WAY_LESS = -1
THREE_WAY_EQUAL = 0
THREE_WAY_GREATER = 1


@dataclass(frozen=True, slots=True)
class DispatchCase:
    key: int
    body: tuple[str, ...]


class DispatchContractError(ValueError):
    pass


def normalize_cases(cases: Iterable[DispatchCase]) -> tuple[DispatchCase, ...]:
    materialized = tuple(cases)
    if not materialized:
        raise DispatchContractError("bank dispatch requires at least one case")
    keys = [case.key for case in materialized]
    if any(isinstance(key, bool) or not isinstance(key, int) for key in keys):
        raise DispatchContractError("bank keys must be integers")
    if len(set(keys)) != len(keys):
        raise DispatchContractError("bank keys must be unique")
    if keys != sorted(keys):
        raise DispatchContractError("bank keys must be strictly increasing")
    if any(not case.body for case in materialized):
        raise DispatchContractError("every bank case needs a non-empty body")
    return materialized


def _indent(lines: Sequence[str], prefix: str) -> list[str]:
    return [prefix + line for line in lines]


def emit_balanced_boolean_dispatch(
    selector: str,
    cases: Iterable[DispatchCase],
    *,
    indent: str = "",
    step: str = "    ",
    fail_closed_body: Sequence[str] = ("return -1",),
) -> str:
    """Emit exact-key S3 dispatch using == plus the boolean < predicate.

    The +1 arm of either boolean relation is always fail-closed.
    """

    if not selector or selector.strip() != selector:
        raise DispatchContractError("selector must be a non-empty trimmed expression")
    normalized = normalize_cases(cases)
    if not step:
        raise DispatchContractError("step must be non-empty")
    if not fail_closed_body:
        raise DispatchContractError("fail_closed_body must be non-empty")

    def emit_leaf(leaf: DispatchCase, level: str) -> list[str]:
        lines = [f"{level}match {selector} == {leaf.key}:"]
        lines.append(f"{level}{step}-1:")
        lines.extend(_indent(leaf.body, level + step * 2))
        lines.append(f"{level}{step}0:")
        lines.extend(_indent(fail_closed_body, level + step * 2))
        lines.append(f"{level}{step}1:")
        lines.extend(_indent(fail_closed_body, level + step * 2))
        return lines

    def emit(items: tuple[DispatchCase, ...], level: str) -> list[str]:
        if len(items) == 1:
            return emit_leaf(items[0], level)

        pivot_index = len(items) // 2
        pivot = items[pivot_index]
        left = items[:pivot_index]
        right = items[pivot_index + 1 :]

        lines = [f"{level}match {selector} == {pivot.key}:"]
        lines.append(f"{level}{step}-1:")
        lines.extend(_indent(pivot.body, level + step * 2))
        lines.append(f"{level}{step}0:")
        lines.append(f"{level}{step * 2}match {selector} < {pivot.key}:")
        lines.append(f"{level}{step * 3}-1:")
        if left:
            lines.extend(emit(left, level + step * 4))
        else:
            lines.extend(_indent(fail_closed_body, level + step * 4))
        lines.append(f"{level}{step * 3}0:")
        if right:
            lines.extend(emit(right, level + step * 4))
        else:
            lines.extend(_indent(fail_closed_body, level + step * 4))
        lines.append(f"{level}{step * 3}1:")
        lines.extend(_indent(fail_closed_body, level + step * 4))
        lines.append(f"{level}{step}1:")
        lines.extend(_indent(fail_closed_body, level + step * 2))
        return lines

    return "\n".join(emit(normalized, indent)) + "\n"


def route_boolean_dispatch(selector: int, keys: Sequence[int]) -> int | None:
    """Pure-Python oracle for the generated equality + boolean-less tree."""

    if isinstance(selector, bool) or not isinstance(selector, int):
        raise DispatchContractError("selector must be an integer")
    normalized = tuple(keys)
    if not normalized:
        raise DispatchContractError("keys must be non-empty")
    if normalized != tuple(sorted(normalized)) or len(set(normalized)) != len(normalized):
        raise DispatchContractError("keys must be unique and sorted")

    def route(items: tuple[int, ...]) -> int | None:
        if len(items) == 1:
            return items[0] if selector == items[0] else None
        pivot_index = len(items) // 2
        pivot = items[pivot_index]
        if selector == pivot:
            return pivot
        if selector < pivot:
            left = items[:pivot_index]
            return route(left) if left else None
        right = items[pivot_index + 1 :]
        return route(right) if right else None

    return route(normalized)


def audit_contiguous_banks(bank_count: int) -> dict[str, object]:
    if isinstance(bank_count, bool) or not isinstance(bank_count, int) or bank_count <= 0:
        raise DispatchContractError("bank_count must be a positive integer")
    keys = tuple(range(bank_count))
    valid = {selector: route_boolean_dispatch(selector, keys) for selector in keys}
    invalid_inputs = (-2, -1, bank_count, bank_count + 1)
    invalid = {selector: route_boolean_dispatch(selector, keys) for selector in invalid_inputs}
    exact = all(routed == selector for selector, routed in valid.items())
    invalid_closed = all(routed is None for routed in invalid.values())
    routed = [value for value in valid.values() if value is not None]
    one_to_one = len(routed) == len(set(routed)) == bank_count
    return {
        "bank_count": bank_count,
        "valid_routes": valid,
        "invalid_routes": invalid,
        "all_valid_exact": exact,
        "invalid_fail_closed": invalid_closed,
        "one_to_one": one_to_one,
        "pass": exact and invalid_closed and one_to_one,
    }
