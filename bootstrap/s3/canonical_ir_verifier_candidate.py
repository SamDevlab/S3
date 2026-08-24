"""M2.84 bounded verifier candidate for linear canonical IR."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .canonical_ir_candidate import (
    CanonicalIRModelError,
    CanonicalIRProgram,
    M281_OPCODE_IDS,
    canonical_ir_to_dict,
    validate_canonical_ir,
)
from .differential import DifferentialHarness, DifferentialResult
from .ir import TERMINATOR_OPCODES
from .lexer import SyntaxMode
from .pipeline import run_source


M284_STAGE_SHAPE = 201
M284_STAGE_STRUCTURE = 202
M284_STAGE_RESULT = 203
M284_STAGE_OPERAND = 204
M284_STAGE_TERMINATOR = 205
M284_MAX_REGISTERS = 8
M284_MAX_INSTRUCTIONS = 4

_ROOT = Path(__file__).resolve().parents[2]
_CANDIDATE_SOURCE = (
    _ROOT / "selfhost" / "verifier" / "canonical_ir_verifier_candidate.s3"
).read_text(encoding="utf-8")


class IRVerifierCandidateError(ValueError):
    """Raised when the bounded verifier candidate cannot run safely."""


@dataclass(frozen=True, slots=True)
class IRVerificationResult:
    accepted: bool
    diagnostic_code: int


@dataclass(frozen=True, slots=True)
class IRVerifierEvidence:
    reference: IRVerificationResult
    candidate: IRVerificationResult
    differential: DifferentialResult

    @property
    def match(self) -> bool:
        return self.differential.match


def verify_ir_reference(program: CanonicalIRProgram) -> IRVerificationResult:
    try:
        validate_canonical_ir(program)
    except (CanonicalIRModelError, TypeError):
        return IRVerificationResult(False, M284_STAGE_SHAPE)
    if len(program.functions) != 1 or len(program.functions[0].blocks) != 1:
        return IRVerificationResult(False, M284_STAGE_STRUCTURE)
    function = program.functions[0]
    if len(function.register_types) > M284_MAX_REGISTERS:
        return IRVerificationResult(False, M284_STAGE_STRUCTURE)
    instructions = function.blocks[0].instructions
    if not 1 <= len(instructions) <= M284_MAX_INSTRUCTIONS:
        return IRVerificationResult(False, M284_STAGE_STRUCTURE)
    defined: set[int] = set()
    for index, instruction in enumerate(instructions):
        if instruction.opcode in TERMINATOR_OPCODES and index != len(instructions) - 1:
            return IRVerificationResult(False, M284_STAGE_TERMINATOR)
        if any(target != 0 for target in instruction.targets):
            return IRVerificationResult(False, M284_STAGE_STRUCTURE)
        for operand in instruction.operands:
            if operand >= len(function.register_types) or operand not in defined:
                return IRVerificationResult(False, M284_STAGE_OPERAND)
        if instruction.result is not None:
            if instruction.result >= len(function.register_types):
                return IRVerificationResult(False, M284_STAGE_RESULT)
            if instruction.result in defined:
                return IRVerificationResult(False, M284_STAGE_RESULT)
            defined.add(instruction.result)
    if instructions[-1].opcode not in TERMINATOR_OPCODES:
        return IRVerificationResult(False, M284_STAGE_TERMINATOR)
    return IRVerificationResult(True, 0)


def _encode(program: CanonicalIRProgram) -> tuple[list[int], list[int], list[int], list[int], int, int]:
    validate_canonical_ir(program)
    function = program.functions[0]
    if len(program.functions) != 1 or len(function.blocks) != 1:
        raise IRVerifierCandidateError("M2.84 candidate requires one linear function")
    instructions = function.blocks[0].instructions
    if len(function.register_types) > M284_MAX_REGISTERS or len(instructions) > M284_MAX_INSTRUCTIONS:
        raise IRVerifierCandidateError("M2.84 candidate shape exceeds its bound")
    opcodes = [M281_OPCODE_IDS[item.opcode] for item in instructions]
    results = [(item.result + 1) if item.result is not None else 0 for item in instructions]
    operand_counts = [len(item.operands) for item in instructions]
    operands: list[int] = []
    for item in instructions:
        operands.extend(item.operands)
        operands.extend([0] * (4 - len(item.operands)))
    opcodes.extend([0] * (M284_MAX_INSTRUCTIONS - len(opcodes)))
    results.extend([0] * (M284_MAX_INSTRUCTIONS - len(results)))
    operand_counts.extend([0] * (M284_MAX_INSTRUCTIONS - len(operand_counts)))
    operands.extend([0] * (M284_MAX_INSTRUCTIONS * 4 - len(operands)))
    return opcodes, results, operand_counts, operands, len(function.register_types), len(instructions)


def verify_ir_candidate(program: CanonicalIRProgram) -> IRVerificationResult:
    opcodes, results, operand_counts, operands, register_count, instruction_count = _encode(program)
    source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    opcodes: tryte[4] = [{', '.join(map(str, opcodes))}]\n"
        + f"    results: tryte[4] = [{', '.join(map(str, results))}]\n"
        + f"    operand_counts: tryte[4] = [{', '.join(map(str, operand_counts))}]\n"
        + f"    operands: tryte[16] = [{', '.join(map(str, operands))}]\n"
        + f"    return verify_linear_ir(opcodes, results, operand_counts, operands, {register_count}, {instruction_count})\n"
    )
    try:
        value = run_source(source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise IRVerifierCandidateError("S3 IR verifier candidate failed") from error
    if value == 0:
        return IRVerificationResult(True, 0)
    if value in {M284_STAGE_SHAPE, M284_STAGE_STRUCTURE, M284_STAGE_RESULT, M284_STAGE_OPERAND, M284_STAGE_TERMINATOR}:
        return IRVerificationResult(False, value)
    raise IRVerifierCandidateError("S3 IR verifier returned an invalid result")


def run_ir_verifier_differential(program: CanonicalIRProgram) -> IRVerifierEvidence:
    reference = verify_ir_reference(program)
    candidate = verify_ir_candidate(program)
    differential = DifferentialHarness(max_bytes=8192).run(
        "m2.84-canonical-ir-verifier",
        canonical_ir_to_dict(program),
        lambda _value: {"accepted": reference.accepted, "diagnostic_code": reference.diagnostic_code},
        lambda _value: {"accepted": candidate.accepted, "diagnostic_code": candidate.diagnostic_code},
        provenance={"component_id": "m2.84-canonical-ir-verifier", "source": "selfhost/verifier/canonical_ir_verifier_candidate.s3"},
    )
    return IRVerifierEvidence(reference, candidate, differential)
