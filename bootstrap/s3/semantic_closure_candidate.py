"""M2.78 composed semantic closure over the M2.71-M2.77 candidates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .control_flow_candidate import (
    FlowStatement,
    reference_control_flow,
)
from .fixed_layout_candidate import (
    enum_layout_reference,
    record_layout_reference,
)
from .function_call_candidate import (
    FunctionSignature,
    reference_function_call,
)
from .lexer import SyntaxMode
from .name_resolution_candidate import reference_name_resolution
from .pipeline import run_source
from .place_reference_candidate import reference_place_operation
from .scalar_type_checking_candidate import (
    _OPERATIONS as SCALAR_OPERATIONS,
    reference_scalar_type_check,
)
from .symbol_table_candidate import reference_symbol_lookup
from .ternary import validate_tryte


M278_WIDTH = 8
M278_LAYOUT_WIDTH = 64
M278_IDENTITY_MODULUS = 181
M278_STAGE_SYMBOLS = 201
M278_STAGE_NAMES = 202
M278_STAGE_SCALARS = 203
M278_STAGE_PLACES = 204
M278_STAGE_FUNCTIONS = 205
M278_STAGE_LAYOUTS = 206
M278_STAGE_FLOW = 207

_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_FILES = (
    ("m271_", _ROOT / "selfhost/semantic/symbol_table_candidate.s3"),
    ("m272_", _ROOT / "selfhost/semantic/name_resolution_candidate.s3"),
    ("m273_", _ROOT / "selfhost/semantic/scalar_type_checking_candidate.s3"),
    ("m274_", _ROOT / "selfhost/semantic/place_reference_candidate.s3"),
    ("m275_", _ROOT / "selfhost/semantic/function_call_candidate.s3"),
    ("m276_", _ROOT / "selfhost/semantic/fixed_layout_candidate.s3"),
    ("m277_", _ROOT / "selfhost/semantic/control_flow_candidate.s3"),
)
_CLOSURE_SOURCE = (
    _ROOT / "selfhost/semantic/semantic_closure_candidate.s3"
).read_text(encoding="utf-8")


class SemanticClosureCandidateError(ValueError):
    """Raised when a composed M2.78 input is outside the bounded contract."""


@dataclass(frozen=True, slots=True)
class SemanticClosureInput:
    symbol_entries: tuple[tuple[int, int], ...]
    symbol_query: int
    name_entries: tuple[tuple[int, int, int], ...]
    scope_parents: tuple[int, ...]
    name_query: int
    name_query_scope: int
    scalar_operation: str
    scalar_left_type: int
    scalar_right_type: int = 0
    scalar_target_type: int = 0
    place_operation: str = "read"
    place_type: int = 1
    place_kind: int = 1
    place_readable: bool = True
    place_writable: bool = False
    place_addressable: bool = False
    place_initialized: bool = True
    function_signatures: tuple[FunctionSignature, ...] = ()
    function_query: int = 0
    argument_types: tuple[int, ...] = ()
    record_types: tuple[int, ...] = ()
    enum_variants: tuple[tuple[int, ...], ...] = ((1,),)
    flow_statements: tuple[FlowStatement, ...] = ()
    flow_requires_return: bool = False


@dataclass(frozen=True, slots=True)
class SemanticClosureResult:
    accepted: bool
    identity: int | None
    diagnostic_code: int


@dataclass(frozen=True, slots=True)
class SemanticClosureEvidence:
    reference: SemanticClosureResult
    candidate: SemanticClosureResult

    @property
    def match(self) -> bool:
        return self.reference == self.candidate


def _validate_sequence(values: Iterable[int], width: int, field: str) -> tuple[int, ...]:
    normalized = tuple(values)
    if len(normalized) > width:
        raise SemanticClosureCandidateError(f"{field} exceeds the M2.78 bound")
    for value in normalized:
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(f"{field} values must be integers")
        validate_tryte(value)
    return normalized


def _pad(values: Iterable[int], width: int, fill: int) -> tuple[int, ...]:
    normalized = tuple(values)
    return normalized + (fill,) * (width - len(normalized))


def _normalize_case(case: SemanticClosureInput) -> SemanticClosureInput:
    if not isinstance(case, SemanticClosureInput):
        raise TypeError("case must be SemanticClosureInput")
    _validate_sequence((item[0] for item in case.symbol_entries), M278_WIDTH, "symbol_entries")
    _validate_sequence((item[0] for item in case.name_entries), M278_WIDTH, "name_entries")
    _validate_sequence(case.scope_parents, M278_WIDTH, "scope_parents")
    _validate_sequence(case.record_types, M278_WIDTH, "record_types")
    if len(case.enum_variants) > M278_WIDTH:
        raise SemanticClosureCandidateError("enum_variants exceeds the M2.78 bound")
    for variant in case.enum_variants:
        _validate_sequence(variant, M278_WIDTH, "enum variant")
    if len(case.function_signatures) > M278_WIDTH:
        raise SemanticClosureCandidateError("function_signatures exceeds the M2.78 bound")
    if len(case.argument_types) > M278_WIDTH:
        raise SemanticClosureCandidateError("argument_types exceeds the M2.78 bound")
    if len(case.flow_statements) > M278_WIDTH:
        raise SemanticClosureCandidateError("flow_statements exceeds the M2.78 bound")
    return case


def _fold_identity(values: Iterable[int]) -> int:
    result = 0
    for value in values:
        result += value
        while result > 364:
            result -= 729
        while result < -364:
            result += 729
    return result % M278_IDENTITY_MODULUS


def _scalar_code(result) -> int:
    return 100 + result.result_type if result.accepted else 200 + result.diagnostic_code


def _place_code(result) -> int:
    if not result.accepted:
        return 200 + result.diagnostic_code
    base = {1: 100, 2: 110, 3: 120}[result.result_place_kind]
    return base + result.result_type_id


def _function_code(result) -> int:
    return 100 + result.result_type if result.accepted else 200 + result.diagnostic_code


def _flow_code(result) -> int:
    if not result.accepted:
        return 200 + result.diagnostic_code
    return {"fallthrough": 100, "returns": 101, "terminates": 102}[result.classification]


def _reference_result(case: SemanticClosureInput) -> SemanticClosureResult:
    try:
        symbol_result = reference_symbol_lookup(case.symbol_entries, case.symbol_query)
    except Exception:
        return SemanticClosureResult(False, None, M278_STAGE_SYMBOLS)
    try:
        name_result = reference_name_resolution(
            case.name_entries,
            case.scope_parents,
            case.name_query,
            case.name_query_scope,
        )
    except Exception:
        return SemanticClosureResult(False, None, M278_STAGE_NAMES)
    try:
        scalar_result = reference_scalar_type_check(
            case.scalar_operation,
            case.scalar_left_type,
            case.scalar_right_type,
            case.scalar_target_type,
        )
    except Exception:
        return SemanticClosureResult(False, None, M278_STAGE_SCALARS)
    if not scalar_result.accepted:
        return SemanticClosureResult(False, None, M278_STAGE_SCALARS)
    try:
        place_result = reference_place_operation(
            case.place_operation,
            case.place_type,
            case.place_kind,
            case.place_readable,
            case.place_writable,
            case.place_addressable,
            case.place_initialized,
        )
    except Exception:
        return SemanticClosureResult(False, None, M278_STAGE_PLACES)
    if not place_result.accepted:
        return SemanticClosureResult(False, None, M278_STAGE_PLACES)
    try:
        function_result = reference_function_call(
            tuple(
                (signature.function_id, signature.parameter_types, signature.return_type)
                for signature in case.function_signatures
            ),
            case.function_query,
            case.argument_types,
        )
    except Exception:
        return SemanticClosureResult(False, None, M278_STAGE_FUNCTIONS)
    if not function_result.accepted:
        return SemanticClosureResult(False, None, M278_STAGE_FUNCTIONS)
    try:
        record_result = record_layout_reference(case.record_types)
        enum_result = enum_layout_reference(case.enum_variants)
    except Exception:
        return SemanticClosureResult(False, None, M278_STAGE_LAYOUTS)
    try:
        flow_result = reference_control_flow(
            case.flow_statements,
            requires_return=case.flow_requires_return,
        )
    except Exception:
        return SemanticClosureResult(False, None, M278_STAGE_FLOW)
    if not flow_result.accepted:
        return SemanticClosureResult(False, None, M278_STAGE_FLOW)
    identity = _fold_identity(
        (
            symbol_result,
            name_result,
            _scalar_code(scalar_result),
            _place_code(place_result),
            _function_code(function_result),
            record_result.cell_count or 0,
            enum_result.cell_count or 0,
            *(record_result.identity or ()),
            *(enum_result.identity or ()),
            _flow_code(flow_result),
        )
    )
    return SemanticClosureResult(True, identity, 0)


def _namespace_source(prefix: str, path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    names = re.findall(r"^fn\s+([A-Za-z_][A-Za-z0-9_]*)", source, flags=re.MULTILINE)
    for name in names:
        source = re.sub(rf"\b{re.escape(name)}\b", prefix + name, source)
    return source


_COMPOSED_SOURCE = "\n\n".join(
    [_namespace_source(prefix, path) for prefix, path in _SOURCE_FILES]
    + [_CLOSURE_SOURCE]
)


def _encode_array(values: Iterable[int], width: int, fill: int) -> str:
    return ", ".join(str(value) for value in _pad(values, width, fill))


def _encode_function_parameters(signatures: tuple[FunctionSignature, ...]) -> tuple[str, str, str, str]:
    ids = [signature.function_id for signature in signatures]
    counts = [len(signature.parameter_types) for signature in signatures]
    returns = [signature.return_type for signature in signatures]
    parameters: list[int] = []
    for signature in signatures:
        parameters.extend(signature.parameter_types)
        parameters.extend([1] * (M278_WIDTH - len(signature.parameter_types)))
    parameters.extend([1] * (M278_WIDTH * (M278_WIDTH - len(signatures))))
    return (
        _encode_array(ids, M278_WIDTH, 0),
        _encode_array(counts, M278_WIDTH, 0),
        _encode_array(returns, M278_WIDTH, 1),
        _encode_array(parameters, M278_LAYOUT_WIDTH, 1),
    )


def _encode_enum(variants: tuple[tuple[int, ...], ...]) -> tuple[str, str]:
    payload_types: list[int] = []
    payload_counts: list[int] = []
    for variant in variants:
        payload_types.extend(variant)
        payload_types.extend([1] * (M278_WIDTH - len(variant)))
        payload_counts.append(len(variant))
    payload_types.extend([1] * (M278_LAYOUT_WIDTH - len(payload_types)))
    return (
        _encode_array(payload_types, M278_LAYOUT_WIDTH, 1),
        _encode_array(payload_counts, M278_WIDTH, 0),
    )


def _candidate_code(case: SemanticClosureInput) -> int:
    symbol_ids = [entry[0] for entry in case.symbol_entries]
    symbol_kinds = [entry[1] for entry in case.symbol_entries]
    name_ids = [entry[0] for entry in case.name_entries]
    name_kinds = [entry[1] for entry in case.name_entries]
    name_scopes = [entry[2] for entry in case.name_entries]
    function_ids, parameter_counts, return_types, parameter_types = _encode_function_parameters(
        case.function_signatures
    )
    enum_payload_types, enum_payload_counts = _encode_enum(case.enum_variants)
    place_operation_code = {
        "read": 1,
        "write": 2,
        "address_shared": 3,
        "address_mutable": 4,
        "deref_shared": 5,
        "deref_mutable": 6,
        "reborrow_shared": 7,
        "reborrow_mutable": 8,
    }[case.place_operation]
    flow_kinds = [statement.kind for statement in case.flow_statements]
    flow_left = [statement.branch_left for statement in case.flow_statements]
    flow_right = [statement.branch_right for statement in case.flow_statements]
    source = (
        _COMPOSED_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    symbol_ids: tryte[8] = [{_encode_array(symbol_ids, M278_WIDTH, 0)}]\n"
        + f"    symbol_kinds: tryte[8] = [{_encode_array(symbol_kinds, M278_WIDTH, 0)}]\n"
        + f"    name_ids: tryte[8] = [{_encode_array(name_ids, M278_WIDTH, 0)}]\n"
        + f"    name_kinds: tryte[8] = [{_encode_array(name_kinds, M278_WIDTH, 0)}]\n"
        + f"    name_scopes: tryte[8] = [{_encode_array(name_scopes, M278_WIDTH, 0)}]\n"
        + f"    scope_parents: tryte[8] = [{_encode_array(case.scope_parents, M278_WIDTH, 0)}]\n"
        + f"    function_ids: tryte[8] = [{function_ids}]\n"
        + f"    function_parameter_counts: tryte[8] = [{parameter_counts}]\n"
        + f"    function_return_types: tryte[8] = [{return_types}]\n"
        + f"    function_parameter_types: tryte[64] = [{parameter_types}]\n"
        + f"    argument_types: tryte[8] = [{_encode_array(case.argument_types, M278_WIDTH, 1)}]\n"
        + f"    record_types: tryte[8] = [{_encode_array(case.record_types, M278_WIDTH, 1)}]\n"
        + f"    enum_payload_types: tryte[64] = [{enum_payload_types}]\n"
        + f"    enum_payload_counts: tryte[8] = [{enum_payload_counts}]\n"
        + f"    flow_kinds: tryte[8] = [{_encode_array(flow_kinds, M278_WIDTH, 0)}]\n"
        + f"    flow_left: tryte[8] = [{_encode_array(flow_left, M278_WIDTH, 0)}]\n"
        + f"    flow_right: tryte[8] = [{_encode_array(flow_right, M278_WIDTH, 0)}]\n"
        + "    return check_semantic_closure(\n"
        + "        symbol_ids, symbol_kinds, "
        + f"{len(symbol_ids)}, {case.symbol_query},\n"
        + "        name_ids, name_kinds, name_scopes, "
        + f"{len(name_ids)}, scope_parents, {len(case.scope_parents)}, "
        + f"{case.name_query}, {case.name_query_scope},\n"
        + f"        {SCALAR_OPERATIONS[case.scalar_operation]}, {case.scalar_left_type}, "
        + f"{case.scalar_right_type}, {case.scalar_target_type},\n"
        + f"        {place_operation_code}, "
        + f"{case.place_type}, {case.place_kind}, {int(case.place_readable)}, "
        + f"{int(case.place_writable)}, {int(case.place_addressable)}, {int(case.place_initialized)},\n"
        + f"        function_ids, function_parameter_counts, function_return_types, function_parameter_types, {len(case.function_signatures)}, {case.function_query}, argument_types, {len(case.argument_types)},\n"
        + f"        record_types, {len(case.record_types)}, enum_payload_types, enum_payload_counts, {len(case.enum_variants)},\n"
        + f"        flow_kinds, flow_left, flow_right, {len(case.flow_statements)}, {int(case.flow_requires_return)}\n"
        + "    )\n"
    )
    try:
        return run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise SemanticClosureCandidateError("S3 composed semantic candidate execution failed") from error


def candidate_semantic_closure(case: SemanticClosureInput) -> SemanticClosureResult:
    case = _normalize_case(case)
    encoded = _candidate_code(case)
    if 0 <= encoded <= 180:
        return SemanticClosureResult(True, encoded, 0)
    if 201 <= encoded <= 207:
        return SemanticClosureResult(False, None, encoded)
    raise SemanticClosureCandidateError("S3 composed semantic candidate returned an invalid result")


def run_semantic_closure_differential(
    case: SemanticClosureInput,
) -> SemanticClosureEvidence:
    case = _normalize_case(case)
    return SemanticClosureEvidence(_reference_result(case), candidate_semantic_closure(case))
