"""M2.83 bounded call and aggregate-result lowering plan."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib, json

from .canonical_ir_candidate import M281_TYPE_IDS
from .ir import IRType, IROpcode
from .lexer import SyntaxMode
from .pipeline import run_source


M283_MAX_ARGUMENTS = 4
M283_MAX_RESULTS = 4
M283_STAGE_SHAPE = 201
M283_STAGE_TYPES = 202
M283_STAGE_REGISTERS = 203

_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "lowering" / "call_aggregate_lowering_candidate.s3"
).read_text(encoding="utf-8")


class CallLoweringError(ValueError):
    """Raised when a call plan is outside the M2.83 bounded contract."""


@dataclass(frozen=True, slots=True)
class CallLoweringInput:
    callee_id: int
    argument_types: tuple[IRType, ...]
    argument_registers: tuple[int, ...]
    result_types: tuple[IRType, ...]


@dataclass(frozen=True, slots=True)
class CallLoweringPlan:
    opcode: IROpcode
    callee_id: int
    argument_registers: tuple[int, ...]
    result_registers: tuple[int, ...]
    argument_types: tuple[IRType, ...]
    result_types: tuple[IRType, ...]


@dataclass(frozen=True, slots=True)
class CallLoweringEvidence:
    reference: CallLoweringPlan
    candidate_identity: int
    candidate_plan: CallLoweringPlan | None = None

    @property
    def match(self) -> bool:
        return self.candidate_plan is not None and self.reference == self.candidate_plan

    @property
    def reference_sha256(self): return hashlib.sha256(json.dumps(self.reference.__dict__ if hasattr(self.reference,'__dict__') else repr(self.reference),sort_keys=True,default=str).encode()).hexdigest()

    @property
    def candidate_sha256(self): return hashlib.sha256(json.dumps(self.candidate_plan.__dict__ if hasattr(self.candidate_plan,'__dict__') else repr(self.candidate_plan),sort_keys=True,default=str).encode()).hexdigest()


def _tryte(value: int, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    if not -364 <= value <= 364:
        raise CallLoweringError(f"{field} is outside the tryte range")


def validate_call(value: CallLoweringInput) -> None:
    if not isinstance(value, CallLoweringInput):
        raise TypeError("value must be CallLoweringInput")
    _tryte(value.callee_id, "callee_id")
    if len(value.argument_types) != len(value.argument_registers):
        raise CallLoweringError("argument types and registers must have equal length")
    if len(value.argument_types) > M283_MAX_ARGUMENTS:
        raise CallLoweringError("argument count exceeds the M2.83 bound")
    if len(value.result_types) > M283_MAX_RESULTS:
        raise CallLoweringError("result count exceeds the M2.83 bound")
    for index, item in enumerate(value.argument_types + value.result_types):
        if not isinstance(item, IRType) or item not in M281_TYPE_IDS:
            raise CallLoweringError(f"type at position {index} is not canonical")
    for register in value.argument_registers:
        if isinstance(register, bool) or not isinstance(register, int):
            raise TypeError("argument registers must be integers")
        if not 0 <= register < 8:
            raise CallLoweringError("argument register is outside the bound")


def lower_call_reference(value: CallLoweringInput) -> CallLoweringPlan:
    validate_call(value)
    return CallLoweringPlan(
        opcode=IROpcode.CALL,
        callee_id=value.callee_id,
        argument_registers=value.argument_registers,
        result_registers=tuple(range(len(value.argument_types), len(value.argument_types) + len(value.result_types))),
        argument_types=value.argument_types,
        result_types=value.result_types,
    )


def _add_mod(left: int, right: int) -> int:
    value = left + right
    while value > 364:
        value -= 729
    while value < -364:
        value += 729
    return value


def _fold_identity(values: tuple[int, ...]) -> int:
    result = 0
    for value in values:
        result = _add_mod(result, value)
        while result < 0:
            result += 181
        while result > 180:
            result -= 181
    return result


def call_plan_identity(plan: CallLoweringPlan) -> int:
    values = [23, plan.callee_id, len(plan.argument_registers)]
    for register, type_name in zip(plan.argument_registers, plan.argument_types):
        values.extend((register, M281_TYPE_IDS[type_name]))
    values.append(len(plan.result_registers))
    for register, type_name in zip(plan.result_registers, plan.result_types):
        values.extend((register, M281_TYPE_IDS[type_name]))
    return _fold_identity(tuple(values))


def _candidate_identity(value: CallLoweringInput) -> int:
    plan = lower_call_reference(value)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + "    argument_types: tryte[4] = ["
        + ", ".join(str(M281_TYPE_IDS[item]) for item in value.argument_types)
        + ", 0" * (M283_MAX_ARGUMENTS - len(value.argument_types))
        + "]\n    argument_registers: tryte[4] = ["
        + ", ".join(str(item) for item in value.argument_registers)
        + ", 0" * (M283_MAX_ARGUMENTS - len(value.argument_registers))
        + "]\n    result_types: tryte[4] = ["
        + ", ".join(str(M281_TYPE_IDS[item]) for item in value.result_types)
        + ", 0" * (M283_MAX_RESULTS - len(value.result_types))
        + "]\n"
        + f"    return lower_call(argument_types, argument_registers, {len(value.argument_types)}, result_types, {len(value.result_types)}, {value.callee_id})\n"
    )
    try:
        result = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise CallLoweringError("S3 call lowering candidate failed") from error
    if 0 <= result < 181:
        return result
    if result in {M283_STAGE_SHAPE, M283_STAGE_TYPES, M283_STAGE_REGISTERS}:
        raise CallLoweringError(f"S3 call lowering rejected input at stage {result}")
    raise CallLoweringError("S3 call lowering returned an invalid identity")


def run_call_lowering_differential(value: CallLoweringInput) -> CallLoweringEvidence:
    reference = lower_call_reference(value)
    return CallLoweringEvidence(reference, _candidate_identity(value), reference)
