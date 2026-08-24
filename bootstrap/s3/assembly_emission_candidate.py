"""M2.91 bounded Assembly emission reference and S3 plan candidate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyParameter,
    AssemblyProgram,
    AssemblyType,
    parse_assembly,
)
from .assembly_program_text_adapter import render_supported_program
from .canonical_ir_candidate import CanonicalIRProgram
from .canonical_ir_verifier_candidate import verify_ir_reference
from .ir import IRType, IROpcode
from .lexer import SyntaxMode
from .pipeline import run_source


M291_MAX_INSTRUCTIONS = 4
M291_OPCODE_IDS = {IROpcode.CONST: 1, IROpcode.ADD: 2, IROpcode.RETURN: 3}
M291_TYPE_IDS = {IRType.TRIT: 1, IRType.TRYTE: 2, IRType.I64: 3, IRType.F64: 4}
_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "assembly" / "assembly_emission_candidate.s3"
).read_text(encoding="utf-8")


class AssemblyEmissionError(ValueError):
    """Raised when the bounded Assembly emission contract is not met."""


@dataclass(frozen=True, slots=True)
class AssemblyEmissionResult:
    text: str
    identity: int


def _add_mod(left: int, right: int) -> int:
    value = left + right
    while value > 364:
        value -= 729
    while value < -364:
        value += 729
    return value


def _fold(values: tuple[int, ...]) -> int:
    result = 0
    for value in values:
        result = _add_mod(result, value)
        while result < 0:
            result += 181
        while result > 180:
            result -= 181
    return result


def _assembly_type(value: IRType) -> AssemblyType:
    try:
        return {
            IRType.TRIT: AssemblyType.TRIT,
            IRType.TRYTE: AssemblyType.TRYTE,
            IRType.I64: AssemblyType.I64,
            IRType.F64: AssemblyType.F64,
        }[value]
    except KeyError as error:
        raise AssemblyEmissionError("IR type is outside the M2.91 Assembly subset") from error


def emit_assembly_reference(program: CanonicalIRProgram) -> AssemblyEmissionResult:
    verification = verify_ir_reference(program)
    if not verification.accepted:
        raise AssemblyEmissionError(
            f"canonical IR rejected before Assembly emission: {verification.diagnostic_code}"
        )
    if len(program.functions) != 1 or len(program.functions[0].blocks) != 1:
        raise AssemblyEmissionError("M2.91 requires one linear function")
    function = program.functions[0]
    if len(function.blocks[0].instructions) > M291_MAX_INSTRUCTIONS:
        raise AssemblyEmissionError("M2.91 instruction bound exceeded")
    instructions: list[AssemblyInstruction] = []
    identity_values = [function.name_id, M291_TYPE_IDS[function.return_type], 0]
    for instruction in function.blocks[0].instructions:
        try:
            opcode_id = M291_OPCODE_IDS[instruction.opcode]
        except KeyError as error:
            raise AssemblyEmissionError("IR opcode is outside the M2.91 Assembly subset") from error
        if instruction.opcode is IROpcode.CONST:
            if instruction.result is None or instruction.immediate is None:
                raise AssemblyEmissionError("CONST requires a result and immediate")
            emitted = AssemblyInstruction(
                AssemblyOpcode.TCONST,
                registers=(instruction.result,),
                immediate=instruction.immediate,
            )
        elif instruction.opcode is IROpcode.ADD:
            if instruction.result is None or len(instruction.operands) != 2:
                raise AssemblyEmissionError("ADD requires a result and two operands")
            emitted = AssemblyInstruction(
                AssemblyOpcode.TADD,
                registers=(instruction.result, *instruction.operands),
            )
        elif instruction.opcode is IROpcode.RETURN:
            emitted = AssemblyInstruction(
                AssemblyOpcode.TRET,
                registers=instruction.operands,
            )
        else:
            raise AssemblyEmissionError("unsupported M2.91 opcode")
        instructions.append(emitted)
        identity_values.extend(
            (
                opcode_id,
                instruction.result if instruction.result is not None else -1,
                instruction.operands[0] if instruction.operands else -1,
                instruction.operands[1] if len(instruction.operands) > 1 else -1,
                instruction.immediate if instruction.immediate is not None else 0,
            )
        )
    identity_values[2] = len(instructions)
    assembly = AssemblyProgram(
        functions=(
            AssemblyFunction(
                name=f"f{function.name_id}",
                return_type=_assembly_type(function.return_type),
                parameters=(),
                register_types=tuple(
                    (index, _assembly_type(register_type))
                    for index, register_type in enumerate(function.register_types)
                ),
                blocks=(AssemblyBlock("entry", tuple(instructions)),),
            ),
        ),
    )
    text = render_supported_program(assembly).text
    parse_assembly(text)
    return AssemblyEmissionResult(text, _fold(tuple(identity_values)))


def _candidate(program: CanonicalIRProgram) -> AssemblyEmissionResult:
    reference = emit_assembly_reference(program)
    function = program.functions[0]
    encoded_opcodes: list[int] = []
    encoded_results: list[int] = []
    encoded_operand0: list[int] = []
    encoded_operand1: list[int] = []
    encoded_immediates: list[int] = []
    for instruction in function.blocks[0].instructions:
        encoded_opcodes.append(M291_OPCODE_IDS[instruction.opcode])
        encoded_results.append(instruction.result if instruction.result is not None else -1)
        encoded_operand0.append(instruction.operands[0] if instruction.operands else -1)
        encoded_operand1.append(instruction.operands[1] if len(instruction.operands) > 1 else -1)
        encoded_immediates.append(instruction.immediate if instruction.immediate is not None else 0)
    padding = M291_MAX_INSTRUCTIONS - len(encoded_opcodes)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    opcodes: tryte[4] = [{', '.join(map(str, encoded_opcodes + [0] * padding))}]\n"
        + f"    results: tryte[4] = [{', '.join(map(str, encoded_results + [0] * padding))}]\n"
        + f"    operand0: tryte[4] = [{', '.join(map(str, encoded_operand0 + [0] * padding))}]\n"
        + f"    operand1: tryte[4] = [{', '.join(map(str, encoded_operand1 + [0] * padding))}]\n"
        + f"    immediates: tryte[4] = [{', '.join(map(str, encoded_immediates + [0] * padding))}]\n"
        + f"    return emit_linear_assembly({function.name_id}, {M291_TYPE_IDS[function.return_type]}, opcodes, results, operand0, operand1, immediates, {len(encoded_opcodes)})\n"
    )
    try:
        identity = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise AssemblyEmissionError("S3 Assembly emission candidate failed") from error
    if not 0 <= identity < 181:
        raise AssemblyEmissionError("S3 Assembly emission returned invalid identity")
    return AssemblyEmissionResult(reference.text, identity)


def run_assembly_emission_differential(
    program: CanonicalIRProgram,
) -> tuple[AssemblyEmissionResult, AssemblyEmissionResult]:
    return emit_assembly_reference(program), _candidate(program)
