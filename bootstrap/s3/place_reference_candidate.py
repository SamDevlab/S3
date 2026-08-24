"""M2.74 bounded S3-authored place and reference candidate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .lexer import SyntaxMode
from .pipeline import run_source
from .ternary import validate_tryte


M274_TYPE_TRIT = 1
M274_TYPE_TRYTE = 2
M274_TYPE_I64 = 3
M274_TYPE_F64 = 4
M274_VALUE = 1
M274_SHARED_REF = 2
M274_MUTABLE_REF = 3
M274_VALID_TYPES = frozenset({1, 2, 3, 4})
M274_VALID_KINDS = frozenset({M274_VALUE, M274_SHARED_REF, M274_MUTABLE_REF})
_OPERATIONS = {
    "read": 1,
    "write": 2,
    "address_shared": 3,
    "address_mutable": 4,
    "deref_shared": 5,
    "deref_mutable": 6,
    "reborrow_shared": 7,
    "reborrow_mutable": 8,
}
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "selfhost"
    / "semantic"
    / "place_reference_candidate.s3"
).read_text(encoding="utf-8")


class PlaceReferenceCandidateError(ValueError):
    """Raised when an M2.74 request is outside the bounded place contract."""


@dataclass(frozen=True, slots=True)
class PlaceReferenceResult:
    operation: str
    type_id: int
    place_kind: int
    readable: bool
    writable: bool
    addressable: bool
    initialized: bool
    accepted: bool
    result_type_id: int | None
    result_place_kind: int | None
    diagnostic_code: int


@dataclass(frozen=True, slots=True)
class PlaceReferenceEvidence:
    reference: PlaceReferenceResult
    candidate: PlaceReferenceResult

    @property
    def match(self) -> bool:
        return self.reference == self.candidate


def _validate_id(value: int, field: str, valid: frozenset[int]) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    validate_tryte(value)
    if value not in valid:
        raise PlaceReferenceCandidateError(f"{field} is outside the M2.74 range")
    return value


def _validate_flag(value: bool, field: str) -> int:
    if not isinstance(value, bool):
        raise TypeError(f"{field} must be a bool")
    return int(value)


def _normalize_request(
    operation: str,
    type_id: int,
    place_kind: int,
    readable: bool,
    writable: bool,
    addressable: bool,
    initialized: bool,
) -> tuple[str, int, int, int, int, int, int, int]:
    if operation not in _OPERATIONS:
        raise PlaceReferenceCandidateError(f"unsupported place operation '{operation}'")
    return (
        operation,
        _OPERATIONS[operation],
        _validate_id(type_id, "type_id", M274_VALID_TYPES),
        _validate_id(place_kind, "place_kind", M274_VALID_KINDS),
        _validate_flag(readable, "readable"),
        _validate_flag(writable, "writable"),
        _validate_flag(addressable, "addressable"),
        _validate_flag(initialized, "initialized"),
    )


def _decode(
    operation: str,
    type_id: int,
    place_kind: int,
    readable: bool,
    writable: bool,
    addressable: bool,
    initialized: bool,
    encoded: int,
) -> PlaceReferenceResult:
    result_type_id: int | None = None
    result_place_kind: int | None = None
    if 101 <= encoded <= 104:
        result_type_id = encoded - 100
        result_place_kind = M274_VALUE
    elif 111 <= encoded <= 114:
        result_type_id = encoded - 110
        result_place_kind = M274_SHARED_REF
    elif 121 <= encoded <= 124:
        result_type_id = encoded - 120
        result_place_kind = M274_MUTABLE_REF
    if result_type_id is not None:
        return PlaceReferenceResult(
            operation, type_id, place_kind, bool(readable), bool(writable), bool(addressable), bool(initialized),
            True, result_type_id, result_place_kind, 0,
        )
    if 201 <= encoded <= 208:
        return PlaceReferenceResult(
            operation, type_id, place_kind, bool(readable), bool(writable), bool(addressable), bool(initialized),
            False, None, None, encoded - 200,
        )
    raise PlaceReferenceCandidateError("S3 place candidate returned an invalid result")


def _reference_code(operation: str, type_id: int, place_kind: int, readable: int, writable: int, addressable: int, initialized: int) -> int:
    if operation == "read":
        return 100 + type_id if initialized and readable else 203
    if operation == "write":
        return 100 + type_id if writable else 204
    if operation == "address_shared":
        return 110 + type_id if addressable else 205
    if operation == "address_mutable":
        return 120 + type_id if addressable and writable else (205 if not addressable else 206)
    if operation == "deref_shared":
        return 100 + type_id if place_kind in {M274_SHARED_REF, M274_MUTABLE_REF} and initialized and readable else (207 if place_kind == M274_VALUE else 203)
    if operation == "deref_mutable":
        if place_kind != M274_MUTABLE_REF:
            return 208
        return 100 + type_id if writable else 204
    if operation == "reborrow_shared":
        return 110 + type_id if place_kind in {M274_SHARED_REF, M274_MUTABLE_REF} and initialized and readable else (207 if place_kind == M274_VALUE else 203)
    if operation == "reborrow_mutable":
        if place_kind != M274_MUTABLE_REF:
            return 208
        return 120 + type_id if writable else 204
    return 201


def reference_place_operation(
    operation: str,
    type_id: int,
    place_kind: int,
    readable: bool,
    writable: bool,
    addressable: bool,
    initialized: bool,
) -> PlaceReferenceResult:
    operation, _code, type_id, place_kind, readable, writable, addressable, initialized = _normalize_request(
        operation, type_id, place_kind, readable, writable, addressable, initialized
    )
    return _decode(
        operation,
        type_id,
        place_kind,
        bool(readable),
        bool(writable),
        bool(addressable),
        bool(initialized),
        _reference_code(operation, type_id, place_kind, readable, writable, addressable, initialized),
    )


def candidate_place_operation(
    operation: str,
    type_id: int,
    place_kind: int,
    readable: bool,
    writable: bool,
    addressable: bool,
    initialized: bool,
) -> PlaceReferenceResult:
    operation, operation_code, type_id, place_kind, readable, writable, addressable, initialized = _normalize_request(
        operation, type_id, place_kind, readable, writable, addressable, initialized
    )
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    return check_place_operation({operation_code}, {type_id}, {place_kind}, {readable}, {writable}, {addressable}, {initialized})\n"
    )
    try:
        encoded = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise PlaceReferenceCandidateError("S3 place candidate execution failed") from error
    return _decode(
        operation,
        type_id,
        place_kind,
        bool(readable),
        bool(writable),
        bool(addressable),
        bool(initialized),
        encoded,
    )


def run_place_reference_differential(
    operation: str,
    type_id: int,
    place_kind: int,
    readable: bool,
    writable: bool,
    addressable: bool,
    initialized: bool,
) -> PlaceReferenceEvidence:
    reference = reference_place_operation(
        operation, type_id, place_kind, readable, writable, addressable, initialized
    )
    candidate = candidate_place_operation(
        operation, type_id, place_kind, readable, writable, addressable, initialized
    )
    return PlaceReferenceEvidence(reference, candidate)
