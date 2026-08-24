"""M2.81 bounded canonical IR data model and S3 candidate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import hashlib

from .canonical_serialization import serialize_canonical
from .differential import DifferentialHarness, DifferentialResult
from .ir import IRType, IROpcode
from .pipeline import run_source
from .lexer import SyntaxMode


M281_MODEL_FORMAT = "s3-canonical-ir-model"
M281_MODEL_VERSION = "0.1.0"
M281_IDENTITY_MODULUS = 181
M281_MAX_FUNCTIONS = 2
M281_MAX_REGISTERS_PER_FUNCTION = 8
M281_MAX_BLOCKS_PER_FUNCTION = 2
M281_MAX_INSTRUCTIONS_PER_BLOCK = 4
M281_MAX_OPERANDS = 4
M281_MAX_TARGETS = 2
M281_STAGE_FUNCTIONS = 201
M281_STAGE_TYPES = 202
M281_STAGE_BLOCKS = 203
M281_STAGE_INSTRUCTIONS = 204
M281_STAGE_OPERANDS = 205
M281_STAGE_TARGETS = 206

M281_TYPE_ORDER = (
    IRType.TRIT,
    IRType.TRYTE,
    IRType.I64,
    IRType.F64,
    IRType.STRING,
    IRType.BYTES,
    IRType.TEXT,
    IRType.VECTOR,
    IRType.REFERENCE,
)
M281_OPCODE_ORDER = tuple(IROpcode)
M281_TYPE_IDS = {item: index for index, item in enumerate(M281_TYPE_ORDER, 1)}
M281_OPCODE_IDS = {item: index for index, item in enumerate(M281_OPCODE_ORDER, 1)}

_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "ir" / "canonical_ir_data_model_candidate.s3"
).read_text(encoding="utf-8")


class CanonicalIRModelError(ValueError):
    """Raised when a canonical M2.81 IR model is outside its bounded shape."""


@dataclass(frozen=True, slots=True)
class CanonicalIRInstruction:
    opcode: IROpcode
    result: int | None = None
    operands: tuple[int, ...] = ()
    immediate: int | None = None
    targets: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class CanonicalIRBlock:
    name_id: int
    instructions: tuple[CanonicalIRInstruction, ...]


@dataclass(frozen=True, slots=True)
class CanonicalIRFunction:
    name_id: int
    return_type: IRType
    register_types: tuple[IRType, ...]
    blocks: tuple[CanonicalIRBlock, ...]


@dataclass(frozen=True, slots=True)
class CanonicalIRProgram:
    functions: tuple[CanonicalIRFunction, ...]


@dataclass(frozen=True, slots=True)
class CanonicalIRResult:
    accepted: bool
    identity: int | None
    diagnostic_code: int


@dataclass(frozen=True, slots=True)
class CanonicalIREvidence:
    reference: CanonicalIRResult
    candidate: CanonicalIRResult
    differential: DifferentialResult

    @property
    def match(self) -> bool:
        return self.differential.match

def canonical_ir_exact_structure(program: CanonicalIRProgram) -> dict[str, object]:
    """Exact bounded observable; legacy identity remains telemetry-only."""
    return canonical_ir_to_dict(program)

def canonical_ir_exact_sha256(program: CanonicalIRProgram) -> str:
    return hashlib.sha256(canonical_ir_json(program).encode()).hexdigest()


def _require_tryte(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field} must be an integer")
    if value < -364 or value > 364:
        raise CanonicalIRModelError(f"{field} is outside the tryte range")
    return value


def _type_id(value: IRType, field: str) -> int:
    if not isinstance(value, IRType):
        raise TypeError(f"{field} must be an IRType")
    try:
        return M281_TYPE_IDS[value]
    except KeyError as error:
        raise CanonicalIRModelError(f"{field} is not in the canonical type table") from error


def _opcode_id(value: IROpcode, field: str) -> int:
    if not isinstance(value, IROpcode):
        raise TypeError(f"{field} must be an IROpcode")
    try:
        return M281_OPCODE_IDS[value]
    except KeyError as error:
        raise CanonicalIRModelError(f"{field} is not in the canonical opcode table") from error


def validate_canonical_ir(program: CanonicalIRProgram) -> None:
    if not isinstance(program, CanonicalIRProgram):
        raise TypeError("program must be CanonicalIRProgram")
    if not 1 <= len(program.functions) <= M281_MAX_FUNCTIONS:
        raise CanonicalIRModelError("function count exceeds the M2.81 bound")
    for function_index, function in enumerate(program.functions):
        if not isinstance(function, CanonicalIRFunction):
            raise TypeError(f"functions[{function_index}] must be CanonicalIRFunction")
        _require_tryte(function.name_id, f"functions[{function_index}].name_id")
        _type_id(function.return_type, f"functions[{function_index}].return_type")
        if len(function.register_types) > M281_MAX_REGISTERS_PER_FUNCTION:
            raise CanonicalIRModelError("register count exceeds the M2.81 bound")
        for register_index, register_type in enumerate(function.register_types):
            _type_id(register_type, f"register_types[{register_index}]")
        if not 1 <= len(function.blocks) <= M281_MAX_BLOCKS_PER_FUNCTION:
            raise CanonicalIRModelError("block count exceeds the M2.81 bound")
        for block_index, block in enumerate(function.blocks):
            if not isinstance(block, CanonicalIRBlock):
                raise TypeError(f"blocks[{block_index}] must be CanonicalIRBlock")
            _require_tryte(block.name_id, f"blocks[{block_index}].name_id")
            if len(block.instructions) > M281_MAX_INSTRUCTIONS_PER_BLOCK:
                raise CanonicalIRModelError("instruction count exceeds the M2.81 bound")
            for instruction_index, instruction in enumerate(block.instructions):
                if not isinstance(instruction, CanonicalIRInstruction):
                    raise TypeError("instructions must be CanonicalIRInstruction")
                _opcode_id(instruction.opcode, f"instructions[{instruction_index}].opcode")
                if instruction.result is not None:
                    if isinstance(instruction.result, bool) or not isinstance(instruction.result, int):
                        raise TypeError("instruction result must be an integer or None")
                    if not 0 <= instruction.result < M281_MAX_REGISTERS_PER_FUNCTION:
                        raise CanonicalIRModelError("instruction result is outside the register bound")
                if len(instruction.operands) > M281_MAX_OPERANDS:
                    raise CanonicalIRModelError("operand count exceeds the M2.81 bound")
                for operand in instruction.operands:
                    if isinstance(operand, bool) or not isinstance(operand, int):
                        raise TypeError("instruction operands must be integers")
                    if not 0 <= operand < M281_MAX_REGISTERS_PER_FUNCTION:
                        raise CanonicalIRModelError("instruction operand is outside the register bound")
                if instruction.immediate is not None:
                    _require_tryte(instruction.immediate, "instruction immediate")
                if len(instruction.targets) > M281_MAX_TARGETS:
                    raise CanonicalIRModelError("target count exceeds the M2.81 bound")
                for target in instruction.targets:
                    _require_tryte(target, "instruction target")


def canonical_ir_to_dict(program: CanonicalIRProgram) -> dict[str, object]:
    validate_canonical_ir(program)
    return {
        "format": M281_MODEL_FORMAT,
        "version": M281_MODEL_VERSION,
        "functions": [
            {
                "name_id": function.name_id,
                "return_type": function.return_type.value,
                "register_types": [item.value for item in function.register_types],
                "blocks": [
                    {
                        "name_id": block.name_id,
                        "instructions": [
                            {
                                "opcode": instruction.opcode.value,
                                "result": instruction.result,
                                "operands": list(instruction.operands),
                                "immediate": instruction.immediate,
                                "targets": list(instruction.targets),
                            }
                            for instruction in block.instructions
                        ],
                    }
                    for block in function.blocks
                ],
            }
            for function in program.functions
        ],
    }


def canonical_ir_json(program: CanonicalIRProgram) -> str:
    return serialize_canonical(canonical_ir_to_dict(program))


def canonical_ir_identity(program: CanonicalIRProgram) -> int:
    validate_canonical_ir(program)
    values: list[int] = [len(program.functions)]
    for function in program.functions:
        values.extend((function.name_id, _type_id(function.return_type, "return_type")))
        values.append(len(function.register_types))
        values.extend(_type_id(item, "register_type") for item in function.register_types)
        values.append(len(function.blocks))
        for block in function.blocks:
            values.extend((block.name_id, len(block.instructions)))
            for instruction in block.instructions:
                values.extend((_opcode_id(instruction.opcode, "opcode"), (instruction.result + 1) if instruction.result is not None else 0))
                values.append(len(instruction.operands))
                values.extend(instruction.operands)
                values.extend((1 if instruction.immediate is not None else 0, instruction.immediate if instruction.immediate is not None else 0))
                values.append(len(instruction.targets))
                values.extend(instruction.targets)
    identity = 0
    for value in values:
        identity += value
        while identity > 364:
            identity -= 729
        while identity < -364:
            identity += 729
        while identity < 0:
            identity += M281_IDENTITY_MODULUS
        while identity >= M281_IDENTITY_MODULUS:
            identity -= M281_IDENTITY_MODULUS
    return identity


def _pad(values: list[int], width: int, fill: int) -> list[int]:
    return values + [fill] * (width - len(values))


def _encode(program: CanonicalIRProgram) -> dict[str, list[int] | int]:
    function_names: list[int] = []
    return_types: list[int] = []
    register_counts: list[int] = []
    block_counts: list[int] = []
    register_types: list[int] = []
    block_names: list[int] = []
    instruction_counts: list[int] = []
    opcodes: list[int] = []
    results: list[int] = []
    operand_counts: list[int] = []
    operands: list[int] = []
    immediate_present: list[int] = []
    immediates: list[int] = []
    target_counts: list[int] = []
    targets: list[int] = []
    for function_index in range(M281_MAX_FUNCTIONS):
        function = program.functions[function_index] if function_index < len(program.functions) else None
        function_names.append(function.name_id if function else 0)
        return_types.append(_type_id(function.return_type, "return_type") if function else 0)
        register_counts.append(len(function.register_types) if function else 0)
        register_types.extend(
            _pad(
                [_type_id(item, "register_type") for item in function.register_types],
                M281_MAX_REGISTERS_PER_FUNCTION,
                0,
            )
            if function
            else [0] * M281_MAX_REGISTERS_PER_FUNCTION
        )
        block_counts.append(len(function.blocks) if function else 0)
        for block_index in range(M281_MAX_BLOCKS_PER_FUNCTION):
            block = function.blocks[block_index] if function and block_index < len(function.blocks) else None
            block_names.append(block.name_id if block else 0)
            instruction_counts.append(len(block.instructions) if block else 0)
            for instruction_index in range(M281_MAX_INSTRUCTIONS_PER_BLOCK):
                instruction = block.instructions[instruction_index] if block and instruction_index < len(block.instructions) else None
                opcodes.append(_opcode_id(instruction.opcode, "opcode") if instruction else 0)
                results.append((instruction.result + 1) if instruction and instruction.result is not None else 0)
                operand_counts.append(len(instruction.operands) if instruction else 0)
                operands.extend(_pad(list(instruction.operands) if instruction else [], M281_MAX_OPERANDS, 0))
                immediate_present.append(1 if instruction and instruction.immediate is not None else 0)
                immediates.append(instruction.immediate if instruction and instruction.immediate is not None else 0)
                target_counts.append(len(instruction.targets) if instruction else 0)
                targets.extend(_pad(list(instruction.targets) if instruction else [], M281_MAX_TARGETS, 0))
    return {
        "function_names": function_names,
        "return_types": return_types,
        "register_counts": register_counts,
        "register_types": register_types,
        "block_counts": block_counts,
        "block_names": block_names,
        "instruction_counts": instruction_counts,
        "opcodes": opcodes,
        "results": results,
        "operand_counts": operand_counts,
        "operands": operands,
        "immediate_present": immediate_present,
        "immediates": immediates,
        "target_counts": target_counts,
        "targets": targets,
        "function_count": len(program.functions),
    }


def candidate_canonical_ir(program: CanonicalIRProgram) -> CanonicalIRResult:
    validate_canonical_ir(program)
    encoded = _encode(program)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + "    function_names: tryte[2] = [" + ", ".join(map(str, encoded["function_names"])) + "]\n"
        + "    return_types: tryte[2] = [" + ", ".join(map(str, encoded["return_types"])) + "]\n"
        + "    register_counts: tryte[2] = [" + ", ".join(map(str, encoded["register_counts"])) + "]\n"
        + "    register_types: tryte[16] = [" + ", ".join(map(str, encoded["register_types"])) + "]\n"
        + "    block_counts: tryte[2] = [" + ", ".join(map(str, encoded["block_counts"])) + "]\n"
        + "    block_names: tryte[4] = [" + ", ".join(map(str, encoded["block_names"])) + "]\n"
        + "    instruction_counts: tryte[4] = [" + ", ".join(map(str, encoded["instruction_counts"])) + "]\n"
        + "    opcodes: tryte[16] = [" + ", ".join(map(str, encoded["opcodes"])) + "]\n"
        + "    results: tryte[16] = [" + ", ".join(map(str, encoded["results"])) + "]\n"
        + "    operand_counts: tryte[16] = [" + ", ".join(map(str, encoded["operand_counts"])) + "]\n"
        + "    operands: tryte[64] = [" + ", ".join(map(str, encoded["operands"])) + "]\n"
        + "    immediate_present: tryte[16] = [" + ", ".join(map(str, encoded["immediate_present"])) + "]\n"
        + "    immediates: tryte[16] = [" + ", ".join(map(str, encoded["immediates"])) + "]\n"
        + "    target_counts: tryte[16] = [" + ", ".join(map(str, encoded["target_counts"])) + "]\n"
        + "    targets: tryte[32] = [" + ", ".join(map(str, encoded["targets"])) + "]\n"
        + "    return canonical_ir_model(function_names, return_types, register_counts, register_types, block_counts, block_names, instruction_counts, opcodes, results, operand_counts, operands, immediate_present, immediates, target_counts, targets, " + str(encoded["function_count"]) + ")\n"
    )
    try:
        value = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise CanonicalIRModelError("S3 canonical IR candidate execution failed") from error
    if 0 <= value < M281_IDENTITY_MODULUS:
        return CanonicalIRResult(True, value, 0)
    if M281_STAGE_FUNCTIONS <= value <= M281_STAGE_TARGETS:
        return CanonicalIRResult(False, None, value)
    raise CanonicalIRModelError("S3 canonical IR candidate returned an invalid result")


def run_canonical_ir_differential(program: CanonicalIRProgram) -> CanonicalIREvidence:
    validate_canonical_ir(program)
    reference = CanonicalIRResult(True, canonical_ir_identity(program), 0)
    candidate = candidate_canonical_ir(program)
    differential = DifferentialHarness(max_bytes=8192).run(
        "m2.81-canonical-ir-data-model",
        canonical_ir_to_dict(program),
        lambda value: {"accepted": True, "identity": reference.identity, "diagnostic_code": 0},
        lambda value: {"accepted": candidate.accepted, "identity": candidate.identity, "diagnostic_code": candidate.diagnostic_code},
        provenance={"component_id": "m2.81-canonical-ir-data-model", "source": "selfhost/ir/canonical_ir_data_model_candidate.s3"},
    )
    return CanonicalIREvidence(reference, candidate, differential)
