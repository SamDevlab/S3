"""M2.77 bounded S3-authored control-flow and return-path candidate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .lexer import SyntaxMode
from .pipeline import run_source
from .ternary import validate_tryte


M277_MAX_STATEMENTS = 8
M277_NORMAL = 0
M277_RETURN = 1
M277_TERMINATE = 2
M277_BRANCH = 3
M277_INFINITE_LOOP = 4
M277_VALID_FLOW_RESULTS = frozenset({0, 1, 2})
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2]
    / "selfhost"
    / "semantic"
    / "control_flow_candidate.s3"
).read_text(encoding="utf-8")


class ControlFlowCandidateError(ValueError):
    """Raised when an M2.77 flow request is outside the bounded contract."""


@dataclass(frozen=True, slots=True)
class FlowStatement:
    kind: int
    branch_left: int = 0
    branch_right: int = 0


@dataclass(frozen=True, slots=True)
class FlowAnalysisResult:
    accepted: bool
    classification: str | None
    diagnostic_code: int


def _validate_small_int(value: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    validate_tryte(value)
    return value


def _normalize_statements(
    statements: list[FlowStatement | tuple[int, int, int]]
    | tuple[FlowStatement | tuple[int, int, int], ...],
) -> tuple[FlowStatement, ...]:
    if not isinstance(statements, (list, tuple)):
        raise TypeError("statements must be a list or tuple")
    if len(statements) > M277_MAX_STATEMENTS:
        raise ControlFlowCandidateError("control-flow block exceeds the M2.77 statement bound")
    normalized: list[FlowStatement] = []
    for index, statement in enumerate(statements):
        if isinstance(statement, FlowStatement):
            item = statement
        elif isinstance(statement, tuple) and len(statement) == 3:
            item = FlowStatement(*statement)
        else:
            raise TypeError(f"statement {index} must be FlowStatement or a three-item tuple")
        kind = _validate_small_int(item.kind, f"statement {index} kind")
        if kind not in {M277_NORMAL, M277_RETURN, M277_TERMINATE, M277_BRANCH, M277_INFINITE_LOOP}:
            raise ControlFlowCandidateError(f"statement {index} kind is unsupported")
        left = _validate_small_int(item.branch_left, f"statement {index} branch_left")
        right = _validate_small_int(item.branch_right, f"statement {index} branch_right")
        if kind in {M277_BRANCH, M277_INFINITE_LOOP}:
            if left not in M277_VALID_FLOW_RESULTS:
                raise ControlFlowCandidateError(f"statement {index} branch_left is invalid")
            if kind == M277_BRANCH and right not in M277_VALID_FLOW_RESULTS:
                raise ControlFlowCandidateError(f"statement {index} branch_right is invalid")
        elif left != 0 or right != 0:
            raise ControlFlowCandidateError(f"statement {index} has unexpected branch metadata")
        normalized.append(FlowStatement(kind, left, right))
    return tuple(normalized)


def _combine_branches(left: int, right: int) -> int:
    if left == 0 or right == 0:
        return 0
    if left == 1 and right == 1:
        return 1
    return 2


def _classification(flow: int) -> str:
    return ("fallthrough", "returns", "terminates")[flow]


def _reference_code(statements: tuple[FlowStatement, ...], requires_return: bool) -> int:
    flow = 0
    for statement in statements:
        if flow != 0:
            return 202
        if statement.kind == M277_NORMAL:
            flow = 0
        elif statement.kind == M277_RETURN:
            flow = 1
        elif statement.kind == M277_TERMINATE:
            flow = 2
        elif statement.kind == M277_BRANCH:
            flow = _combine_branches(statement.branch_left, statement.branch_right)
        else:
            flow = 1 if statement.branch_left == 1 else 2
    if requires_return and flow != 1:
        return 201
    return 100 + flow


def _decode(encoded: int) -> FlowAnalysisResult:
    if 100 <= encoded <= 102:
        return FlowAnalysisResult(True, _classification(encoded - 100), 0)
    if 201 <= encoded <= 203:
        return FlowAnalysisResult(False, None, encoded - 200)
    raise ControlFlowCandidateError("S3 control-flow candidate returned an invalid result")


def reference_control_flow(
    statements: list[FlowStatement | tuple[int, int, int]]
    | tuple[FlowStatement | tuple[int, int, int], ...],
    *,
    requires_return: bool,
) -> FlowAnalysisResult:
    if not isinstance(requires_return, bool):
        raise TypeError("requires_return must be a boolean")
    normalized = _normalize_statements(statements)
    return _decode(_reference_code(normalized, requires_return))


def _candidate_code(
    statements: tuple[FlowStatement, ...], requires_return: bool
) -> int:
    kinds = [statement.kind for statement in statements]
    left = [statement.branch_left for statement in statements]
    right = [statement.branch_right for statement in statements]
    kinds.extend([M277_NORMAL] * (M277_MAX_STATEMENTS - len(kinds)))
    left.extend([0] * (M277_MAX_STATEMENTS - len(left)))
    right.extend([0] * (M277_MAX_STATEMENTS - len(right)))
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    statement_kinds: tryte[8] = [{', '.join(str(value) for value in kinds)}]\n"
        + f"    branch_left: tryte[8] = [{', '.join(str(value) for value in left)}]\n"
        + f"    branch_right: tryte[8] = [{', '.join(str(value) for value in right)}]\n"
        + "    return check_control_flow(\n"
        + f"        statement_kinds, branch_left, branch_right, {len(statements)}, {int(requires_return)}\n"
        + "    )\n"
    )
    try:
        return run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise ControlFlowCandidateError("S3 control-flow candidate execution failed") from error


def candidate_control_flow(
    statements: list[FlowStatement | tuple[int, int, int]]
    | tuple[FlowStatement | tuple[int, int, int], ...],
    *,
    requires_return: bool,
) -> FlowAnalysisResult:
    if not isinstance(requires_return, bool):
        raise TypeError("requires_return must be a boolean")
    normalized = _normalize_statements(statements)
    return _decode(_candidate_code(normalized, requires_return))


def run_control_flow_differential(
    statements: list[FlowStatement | tuple[int, int, int]]
    | tuple[FlowStatement | tuple[int, int, int], ...],
    *,
    requires_return: bool,
) -> tuple[FlowAnalysisResult, FlowAnalysisResult]:
    reference = reference_control_flow(statements, requires_return=requires_return)
    candidate = candidate_control_flow(statements, requires_return=requires_return)
    return reference, candidate
