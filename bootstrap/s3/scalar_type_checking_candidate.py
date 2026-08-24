"""M2.73 bounded S3-authored scalar type-checking candidate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .lexer import SyntaxMode
from .pipeline import run_source
from .ternary import validate_tryte


M273_TYPE_TRIT = 1
M273_TYPE_TRYTE = 2
M273_TYPE_I64 = 3
M273_TYPE_F64 = 4
M273_VALID_TYPES = frozenset({M273_TYPE_TRIT, M273_TYPE_TRYTE, M273_TYPE_I64, M273_TYPE_F64})

_OPERATIONS = {
    "assign": 1,
    "add": 2,
    "subtract": 2,
    "multiply": 3,
    "divide": 3,
    "minimum": 4,
    "maximum": 4,
    "compare": 5,
    "equal": 5,
    "not_equal": 5,
    "less": 5,
    "less_equal": 5,
    "greater": 5,
    "greater_equal": 5,
    "to_i64": 6,
    "to_f64": 7,
    "to_tryte": 8,
}
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "selfhost"
    / "semantic"
    / "scalar_type_checking_candidate.s3"
).read_text(encoding="utf-8")


class ScalarTypeCheckingError(ValueError):
    """Raised when an M2.73 request is outside the scalar contract."""


@dataclass(frozen=True, slots=True)
class ScalarTypeCheckResult:
    operation: str
    left_type: int
    right_type: int
    target_type: int
    accepted: bool
    result_type: int | None
    diagnostic_code: int


@dataclass(frozen=True, slots=True)
class ScalarTypeCheckEvidence:
    reference: ScalarTypeCheckResult
    candidate: ScalarTypeCheckResult

    @property
    def match(self) -> bool:
        return self.reference == self.candidate


def _validate_type(type_id: int, field: str, *, allow_zero: bool = False) -> int:
    if isinstance(type_id, bool) or not isinstance(type_id, int):
        raise TypeError(f"{field} must be an integer")
    validate_tryte(type_id)
    if allow_zero and type_id == 0:
        return type_id
    if type_id not in M273_VALID_TYPES:
        raise ScalarTypeCheckingError(f"{field} is outside the scalar type range")
    return type_id


def _normalize_request(
    operation: str,
    left_type: int,
    right_type: int,
    target_type: int,
) -> tuple[str, int, int, int, int]:
    if operation not in _OPERATIONS:
        raise ScalarTypeCheckingError(f"unsupported scalar operation '{operation}'")
    operation_code = _OPERATIONS[operation]
    left_type = _validate_type(left_type, "left_type")
    right_type = _validate_type(right_type, "right_type", allow_zero=True)
    target_type = _validate_type(target_type, "target_type", allow_zero=True)
    if operation == "assign":
        if right_type != 0:
            raise ScalarTypeCheckingError("assignment does not accept right_type")
        if target_type == 0:
            raise ScalarTypeCheckingError("assignment requires target_type")
    elif operation.startswith("to_"):
        if right_type != 0 or target_type != 0:
            raise ScalarTypeCheckingError("conversion accepts only left_type")
    else:
        if right_type == 0:
            raise ScalarTypeCheckingError("binary operation requires right_type")
        if target_type != 0:
            raise ScalarTypeCheckingError("binary operation does not accept target_type")
    return operation, operation_code, left_type, right_type, target_type


def _decode(
    operation: str,
    left_type: int,
    right_type: int,
    target_type: int,
    encoded: int,
) -> ScalarTypeCheckResult:
    if 101 <= encoded <= 104:
        return ScalarTypeCheckResult(
            operation,
            left_type,
            right_type,
            target_type,
            True,
            encoded - 100,
            0,
        )
    if 201 <= encoded <= 207:
        return ScalarTypeCheckResult(
            operation,
            left_type,
            right_type,
            target_type,
            False,
            None,
            encoded - 200,
        )
    raise ScalarTypeCheckingError("S3 scalar type candidate returned an invalid result")


def _reference_code(operation: str, left_type: int, right_type: int, target_type: int) -> int:
    if operation == "assign":
        return 100 + target_type if left_type == target_type else 203
    if operation in {"add", "subtract", "minimum", "maximum"}:
        if left_type != right_type:
            return 204
        if operation in {"minimum", "maximum"} and left_type in {M273_TYPE_I64, M273_TYPE_F64}:
            return 205
        return 100 + left_type
    if operation in {"multiply", "divide"}:
        if left_type != right_type:
            return 204
        if left_type not in {M273_TYPE_I64, M273_TYPE_F64}:
            return 205
        return 100 + left_type
    if operation in {
        "compare",
        "equal",
        "not_equal",
        "less",
        "less_equal",
        "greater",
        "greater_equal",
    }:
        return 101 if left_type == right_type else 204
    if operation == "to_i64":
        return 103 if left_type in {M273_TYPE_TRIT, M273_TYPE_TRYTE} else 207
    if operation == "to_f64":
        return 104 if left_type in {M273_TYPE_TRIT, M273_TYPE_TRYTE, M273_TYPE_I64} else 207
    if operation == "to_tryte":
        return 102 if left_type == M273_TYPE_I64 else 207
    return 201


def reference_scalar_type_check(
    operation: str,
    left_type: int,
    right_type: int = 0,
    target_type: int = 0,
) -> ScalarTypeCheckResult:
    operation, _code, left_type, right_type, target_type = _normalize_request(
        operation, left_type, right_type, target_type
    )
    return _decode(
        operation,
        left_type,
        right_type,
        target_type,
        _reference_code(operation, left_type, right_type, target_type),
    )


def candidate_scalar_type_check(
    operation: str,
    left_type: int,
    right_type: int = 0,
    target_type: int = 0,
) -> ScalarTypeCheckResult:
    operation, operation_code, left_type, right_type, target_type = _normalize_request(
        operation, left_type, right_type, target_type
    )
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    return check_scalar_type({operation_code}, {left_type}, {right_type}, {target_type})\n"
    )
    try:
        encoded = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise ScalarTypeCheckingError("S3 scalar type candidate execution failed") from error
    return _decode(operation, left_type, right_type, target_type, encoded)


def run_scalar_type_differential(
    operation: str,
    left_type: int,
    right_type: int = 0,
    target_type: int = 0,
) -> ScalarTypeCheckEvidence:
    reference = reference_scalar_type_check(operation, left_type, right_type, target_type)
    candidate = candidate_scalar_type_check(operation, left_type, right_type, target_type)
    return ScalarTypeCheckEvidence(reference, candidate)
