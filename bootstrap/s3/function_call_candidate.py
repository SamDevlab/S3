"""M2.75 bounded S3-authored function signature and call candidate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .lexer import SyntaxMode
from .pipeline import run_source
from .ternary import validate_tryte


M275_MAX_FUNCTIONS = 8
M275_MAX_PARAMETERS = 8
M275_VALID_TYPES = frozenset({1, 2, 3, 4})
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "selfhost"
    / "semantic"
    / "function_call_candidate.s3"
).read_text(encoding="utf-8")


class FunctionCallCandidateError(ValueError):
    """Raised when an M2.75 request is outside the bounded call contract."""


@dataclass(frozen=True, slots=True)
class FunctionSignature:
    function_id: int
    parameter_types: tuple[int, ...]
    return_type: int


@dataclass(frozen=True, slots=True)
class FunctionCallResult:
    query_id: int
    argument_types: tuple[int, ...]
    accepted: bool
    result_type: int | None
    diagnostic_code: int


@dataclass(frozen=True, slots=True)
class FunctionCallEvidence:
    reference: FunctionCallResult
    candidate: FunctionCallResult

    @property
    def match(self) -> bool:
        return self.reference == self.candidate


def _validate_type(type_id: int, field: str) -> int:
    if isinstance(type_id, bool) or not isinstance(type_id, int):
        raise TypeError(f"{field} must be an integer")
    validate_tryte(type_id)
    if type_id not in M275_VALID_TYPES:
        raise FunctionCallCandidateError(f"{field} is outside the scalar type range")
    return type_id


def _normalize_signatures(
    signatures: list[tuple[int, list[int] | tuple[int, ...], int]]
    | tuple[tuple[int, list[int] | tuple[int, ...], int], ...],
) -> tuple[FunctionSignature, ...]:
    if not isinstance(signatures, (list, tuple)):
        raise TypeError("signatures must be a list or tuple")
    if len(signatures) > M275_MAX_FUNCTIONS:
        raise FunctionCallCandidateError("function table exceeds the M2.75 bound")
    normalized: list[FunctionSignature] = []
    for entry in signatures:
        if not isinstance(entry, tuple) or len(entry) != 3:
            raise TypeError("signatures must be (function_id, parameter_types, return_type) tuples")
        function_id, parameter_types, return_type = entry
        if isinstance(function_id, bool) or not isinstance(function_id, int):
            raise TypeError("function id must be an integer")
        validate_tryte(function_id)
        if not isinstance(parameter_types, (list, tuple)):
            raise TypeError("parameter_types must be a list or tuple")
        if len(parameter_types) > M275_MAX_PARAMETERS:
            raise FunctionCallCandidateError("function signature exceeds the M2.75 parameter bound")
        normalized.append(
            FunctionSignature(
                function_id,
                tuple(_validate_type(type_id, "parameter type") for type_id in parameter_types),
                _validate_type(return_type, "return type"),
            )
        )
    return tuple(normalized)


def _normalize_arguments(argument_types: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    if not isinstance(argument_types, (list, tuple)):
        raise TypeError("argument_types must be a list or tuple")
    if len(argument_types) > M275_MAX_PARAMETERS:
        raise FunctionCallCandidateError("argument list exceeds the M2.75 parameter bound")
    return tuple(_validate_type(type_id, "argument type") for type_id in argument_types)


def _decode(query_id: int, argument_types: tuple[int, ...], encoded: int) -> FunctionCallResult:
    if 101 <= encoded <= 104:
        return FunctionCallResult(query_id, argument_types, True, encoded - 100, 0)
    if 202 <= encoded <= 206:
        return FunctionCallResult(query_id, argument_types, False, None, encoded - 200)
    raise FunctionCallCandidateError("S3 function-call candidate returned an invalid result")


def _reference_code(
    signatures: tuple[FunctionSignature, ...], query_id: int, argument_types: tuple[int, ...]
) -> int:
    seen: set[int] = set()
    for signature in signatures:
        if signature.function_id in seen:
            return 202
        seen.add(signature.function_id)
    for signature in signatures:
        if signature.function_id != query_id:
            continue
        if len(signature.parameter_types) != len(argument_types):
            return 205
        if signature.parameter_types != argument_types:
            return 206
        return 100 + signature.return_type
    return 204


def reference_function_call(
    signatures: list[tuple[int, list[int] | tuple[int, ...], int]]
    | tuple[tuple[int, list[int] | tuple[int, ...], int], ...],
    query_id: int,
    argument_types: list[int] | tuple[int, ...],
) -> FunctionCallResult:
    signatures = _normalize_signatures(signatures)
    if isinstance(query_id, bool) or not isinstance(query_id, int):
        raise TypeError("query_id must be an integer")
    validate_tryte(query_id)
    arguments = _normalize_arguments(argument_types)
    return _decode(query_id, arguments, _reference_code(signatures, query_id, arguments))


def candidate_function_call(
    signatures: list[tuple[int, list[int] | tuple[int, ...], int]]
    | tuple[tuple[int, list[int] | tuple[int, ...], int], ...],
    query_id: int,
    argument_types: list[int] | tuple[int, ...],
) -> FunctionCallResult:
    signatures = _normalize_signatures(signatures)
    if isinstance(query_id, bool) or not isinstance(query_id, int):
        raise TypeError("query_id must be an integer")
    validate_tryte(query_id)
    arguments = _normalize_arguments(argument_types)
    function_ids = [str(signature.function_id) for signature in signatures]
    parameter_counts = [str(len(signature.parameter_types)) for signature in signatures]
    return_types = [str(signature.return_type) for signature in signatures]
    parameter_values: list[str] = []
    for signature in signatures:
        parameter_values.extend(str(type_id) for type_id in signature.parameter_types)
        parameter_values.extend(
            ["1"] * (M275_MAX_PARAMETERS - len(signature.parameter_types))
        )
    function_ids.extend(["0"] * (M275_MAX_FUNCTIONS - len(function_ids)))
    parameter_counts.extend(["0"] * (M275_MAX_FUNCTIONS - len(parameter_counts)))
    return_types.extend(["1"] * (M275_MAX_FUNCTIONS - len(return_types)))
    parameter_values.extend(["1"] * (M275_MAX_FUNCTIONS * M275_MAX_PARAMETERS - len(parameter_values)))
    argument_values = [str(type_id) for type_id in arguments]
    argument_values.extend(["1"] * (M275_MAX_PARAMETERS - len(argument_values)))
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    function_ids: tryte[8] = [{', '.join(function_ids)}]\n"
        + f"    parameter_counts: tryte[8] = [{', '.join(parameter_counts)}]\n"
        + f"    return_types: tryte[8] = [{', '.join(return_types)}]\n"
        + f"    parameter_types: tryte[64] = [{', '.join(parameter_values)}]\n"
        + f"    argument_types: tryte[8] = [{', '.join(argument_values)}]\n"
        + "    return check_function_call(\n"
        + "        function_ids, parameter_counts, return_types, parameter_types,\n"
        + f"        {len(signatures)}, {query_id}, argument_types, {len(arguments)}\n"
        + "    )\n"
    )
    try:
        encoded = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise FunctionCallCandidateError("S3 function-call candidate execution failed") from error
    return _decode(query_id, arguments, encoded)


def run_function_call_differential(
    signatures: list[tuple[int, list[int] | tuple[int, ...], int]]
    | tuple[tuple[int, list[int] | tuple[int, ...], int], ...],
    query_id: int,
    argument_types: list[int] | tuple[int, ...],
) -> FunctionCallEvidence:
    reference = reference_function_call(signatures, query_id, argument_types)
    candidate = candidate_function_call(signatures, query_id, argument_types)
    return FunctionCallEvidence(reference, candidate)
