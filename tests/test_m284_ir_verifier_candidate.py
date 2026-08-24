"""M2.84 bounded canonical IR verifier contracts."""

from dataclasses import replace
from pathlib import Path

import pytest

from bootstrap.s3.canonical_ir_candidate import (
    CanonicalIRBlock,
    CanonicalIRFunction,
    CanonicalIRInstruction,
    CanonicalIRProgram,
)
from bootstrap.s3.canonical_ir_verifier_candidate import (
    IRVerifierCandidateError,
    run_ir_verifier_differential,
    verify_ir_reference,
)
from bootstrap.s3.ir import IRType, IROpcode


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (
    ROOT / "selfhost" / "verifier" / "canonical_ir_verifier_candidate.s3"
).read_text(encoding="utf-8")


def _program() -> CanonicalIRProgram:
    return CanonicalIRProgram(
        functions=(
            CanonicalIRFunction(
                name_id=0,
                return_type=IRType.TRYTE,
                register_types=(IRType.TRYTE, IRType.TRYTE),
                blocks=(
                    CanonicalIRBlock(
                        name_id=0,
                        instructions=(
                            CanonicalIRInstruction(IROpcode.CONST, result=0, immediate=1),
                            CanonicalIRInstruction(IROpcode.ADD, result=1, operands=(0, 0)),
                            CanonicalIRInstruction(IROpcode.RETURN, operands=(1,)),
                        ),
                    ),
                ),
            ),
        ),
    )


def test_candidate_source_has_one_verifier_entrypoint_and_no_main() -> None:
    assert "fn verify_linear_ir" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE
    assert "defined" in SELFHOST_SOURCE


def test_valid_linear_ir_matches_candidate() -> None:
    evidence = run_ir_verifier_differential(_program())
    assert evidence.match
    assert evidence.reference.accepted
    assert evidence.candidate.accepted


def test_use_before_definition_is_rejected_with_stable_stage() -> None:
    program = _program()
    block = program.functions[0].blocks[0]
    changed = replace(
        block.instructions[1],
        operands=(1, 0),
    )
    invalid = replace(
        program,
        functions=(
            replace(program.functions[0], blocks=(replace(block, instructions=(block.instructions[0], changed, block.instructions[2])),)),
        ),
    )
    evidence = run_ir_verifier_differential(invalid)
    assert evidence.match
    assert not evidence.reference.accepted
    assert evidence.reference.diagnostic_code == 204


def test_missing_terminator_is_rejected_by_reference() -> None:
    program = _program()
    block = program.functions[0].blocks[0]
    invalid = replace(
        program,
        functions=(replace(program.functions[0], blocks=(replace(block, instructions=block.instructions[:2]),)),),
    )
    evidence = run_ir_verifier_differential(invalid)
    assert evidence.match
    assert not evidence.reference.accepted
    assert evidence.reference.diagnostic_code == 205
