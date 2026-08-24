"""M2.76 bounded S3-authored record and enum fixed-layout candidate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .lexer import SyntaxMode
from .pipeline import run_source
from .ternary import validate_tryte


M276_MAX_FIELDS = 8
M276_MAX_VARIANTS = 8
M276_VALID_TYPES = frozenset({1, 2, 3, 4})
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "selfhost"
    / "semantic"
    / "fixed_layout_candidate.s3"
).read_text(encoding="utf-8")


class FixedLayoutCandidateError(ValueError):
    """Raised when an M2.76 layout request is outside the bounded contract."""


@dataclass(frozen=True, slots=True)
class FixedLayoutResult:
    layout_kind: str
    accepted: bool
    cell_count: int | None
    identity: tuple[int, int] | None
    diagnostic_code: int


def _validate_type(type_id: int, field: str) -> int:
    if isinstance(type_id, bool) or not isinstance(type_id, int):
        raise TypeError(f"{field} must be an integer")
    validate_tryte(type_id)
    if type_id not in M276_VALID_TYPES:
        raise FixedLayoutCandidateError(f"{field} is outside the scalar type range")
    return type_id


def _normalize_fields(
    field_types: list[int] | tuple[int, ...],
) -> tuple[int, ...]:
    if not isinstance(field_types, (list, tuple)):
        raise TypeError("field_types must be a list or tuple")
    if len(field_types) > M276_MAX_FIELDS:
        raise FixedLayoutCandidateError("record layout exceeds the M2.76 field bound")
    return tuple(_validate_type(type_id, "field type") for type_id in field_types)


def _normalize_variants(
    variants: list[list[int] | tuple[int, ...]]
    | tuple[list[int] | tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    if not isinstance(variants, (list, tuple)):
        raise TypeError("variants must be a list or tuple")
    if not 1 <= len(variants) <= M276_MAX_VARIANTS:
        raise FixedLayoutCandidateError("enum layout exceeds the M2.76 variant bound")
    normalized: list[tuple[int, ...]] = []
    for variant in variants:
        normalized.append(_normalize_fields(variant))
    return tuple(normalized)


def _add_mod(left: int, right: int) -> int:
    value = left + right
    if value > 364:
        value -= 729
    if value < -364:
        value += 729
    return value


def _mix(checksum: int, position: int, value: int) -> int:
    result = checksum
    for _ in range(5):
        result = _add_mod(result, result)
    return _add_mod(_add_mod(result, position), value)


def _record_identity(field_types: tuple[int, ...], seed: int) -> int:
    checksum = _add_mod(seed, len(field_types))
    for index, type_id in enumerate(field_types):
        checksum = _mix(checksum, index + 1, type_id)
    return checksum


def _enum_identity(variants: tuple[tuple[int, ...], ...], seed: int) -> int:
    checksum = _add_mod(seed, len(variants))
    for variant_index, variant in enumerate(variants):
        checksum = _mix(checksum, variant_index + 1, len(variant))
        for payload_index, type_id in enumerate(variant):
            checksum = _mix(checksum, 20 + variant_index + payload_index, type_id)
    return checksum


def _encode_source_array(values: list[int], size: int) -> str:
    padded = [*values, *([1] * (size - len(values)))]
    return ", ".join(str(value) for value in padded)


def _run(source: str) -> int:
    try:
        return run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise FixedLayoutCandidateError("S3 fixed-layout candidate execution failed") from error


def _record_candidate_code(field_types: tuple[int, ...], operation: str, seed: int = 0) -> int:
    fields = _encode_source_array(list(field_types), M276_MAX_FIELDS)
    call = (
        f"record_layout_summary(field_types, {len(field_types)})"
        if operation == "summary"
        else f"record_layout_identity(field_types, {len(field_types)}, {seed})"
    )
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    field_types: tryte[8] = [{fields}]\n"
        + f"    return {call}\n"
    )
    return _run(source)


def _enum_candidate_code(
    variants: tuple[tuple[int, ...], ...], operation: str, seed: int = 0
) -> int:
    payload_types: list[int] = []
    payload_counts: list[int] = []
    for variant in variants:
        payload_types.extend(variant)
        payload_types.extend([1] * (M276_MAX_FIELDS - len(variant)))
        payload_counts.append(len(variant))
    payload_types.extend([1] * (M276_MAX_FIELDS * (M276_MAX_VARIANTS - len(variants))))
    payload_counts.extend([0] * (M276_MAX_VARIANTS - len(variants)))
    type_values = ", ".join(str(value) for value in payload_types)
    count_values = ", ".join(str(value) for value in payload_counts)
    call = (
        f"enum_layout_summary(payload_types, payload_counts, {len(variants)})"
        if operation == "summary"
        else f"enum_layout_identity(payload_types, payload_counts, {len(variants)}, {seed})"
    )
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    payload_types: tryte[64] = [{type_values}]\n"
        + f"    payload_counts: tryte[8] = [{count_values}]\n"
        + f"    return {call}\n"
    )
    return _run(source)


def _summary_result(kind: str, encoded: int, maximum: int) -> FixedLayoutResult:
    if 0 <= encoded <= maximum:
        return FixedLayoutResult(kind, True, encoded, None, 0)
    if 200 <= encoded <= 299:
        return FixedLayoutResult(kind, False, None, None, encoded - 200)
    raise FixedLayoutCandidateError("S3 fixed-layout candidate returned an invalid summary")


def record_layout_reference(field_types: list[int] | tuple[int, ...]) -> FixedLayoutResult:
    fields = _normalize_fields(field_types)
    return FixedLayoutResult(
        "record",
        True,
        len(fields),
        (_record_identity(fields, 17), _record_identity(fields, 53)),
        0,
    )


def record_layout_candidate(field_types: list[int] | tuple[int, ...]) -> FixedLayoutResult:
    fields = _normalize_fields(field_types)
    summary = _summary_result("record", _record_candidate_code(fields, "summary"), M276_MAX_FIELDS)
    if not summary.accepted:
        return summary
    identity = (
        _record_candidate_code(fields, "identity", 17),
        _record_candidate_code(fields, "identity", 53),
    )
    return FixedLayoutResult("record", True, summary.cell_count, identity, 0)


def enum_layout_reference(
    variants: list[list[int] | tuple[int, ...]]
    | tuple[list[int] | tuple[int, ...], ...],
) -> FixedLayoutResult:
    normalized = _normalize_variants(variants)
    cell_count = 1 + max((len(variant) for variant in normalized), default=0)
    return FixedLayoutResult(
        "enum",
        True,
        cell_count,
        (_enum_identity(normalized, 37), _enum_identity(normalized, 71)),
        0,
    )


def enum_layout_candidate(
    variants: list[list[int] | tuple[int, ...]]
    | tuple[list[int] | tuple[int, ...], ...],
) -> FixedLayoutResult:
    normalized = _normalize_variants(variants)
    summary = _summary_result(
        "enum", _enum_candidate_code(normalized, "summary"), 1 + M276_MAX_FIELDS
    )
    if not summary.accepted:
        return summary
    identity = (
        _enum_candidate_code(normalized, "identity", 37),
        _enum_candidate_code(normalized, "identity", 71),
    )
    return FixedLayoutResult("enum", True, summary.cell_count, identity, 0)


def run_fixed_layout_differential(
    field_types: list[int] | tuple[int, ...],
    variants: list[list[int] | tuple[int, ...]]
    | tuple[list[int] | tuple[int, ...], ...],
) -> tuple[FixedLayoutResult, FixedLayoutResult, FixedLayoutResult, FixedLayoutResult]:
    record_reference = record_layout_reference(field_types)
    record_candidate = record_layout_candidate(field_types)
    enum_reference = enum_layout_reference(variants)
    enum_candidate = enum_layout_candidate(variants)
    return record_reference, record_candidate, enum_reference, enum_candidate
