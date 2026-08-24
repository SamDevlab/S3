"""M2.81 canonical IR data model contracts."""

from dataclasses import replace
from pathlib import Path

import pytest

from bootstrap.s3.canonical_ir_candidate import (
    CanonicalIRBlock,
    CanonicalIRFunction,
    CanonicalIRInstruction,
    CanonicalIRModelError,
    CanonicalIRProgram,
    M281_MODEL_FORMAT,
    M281_MODEL_VERSION,
    canonical_ir_identity,
    canonical_ir_json,
    run_canonical_ir_differential,
)
from bootstrap.s3.ir import IRType, IROpcode


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (
    ROOT / "selfhost" / "ir" / "canonical_ir_data_model_candidate.s3"
).read_text(encoding="utf-8")


def _program() -> CanonicalIRProgram:
    return CanonicalIRProgram(
        functions=(
            CanonicalIRFunction(
                name_id=7,
                return_type=IRType.TRYTE,
                register_types=(IRType.TRYTE, IRType.TRYTE),
                blocks=(
                    CanonicalIRBlock(
                        name_id=11,
                        instructions=(
                            CanonicalIRInstruction(
                                IROpcode.CONST,
                                result=0,
                                immediate=1,
                            ),
                            CanonicalIRInstruction(
                                IROpcode.ADD,
                                result=1,
                                operands=(0, 0),
                            ),
                            CanonicalIRInstruction(
                                IROpcode.RETURN,
                                operands=(1,),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def test_candidate_source_has_one_canonical_entrypoint_and_no_main() -> None:
    assert "fn canonical_ir_model" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE
    assert "tryte[64]" in SELFHOST_SOURCE


def test_reference_and_s3_candidate_match_for_canonical_program() -> None:
    evidence = run_canonical_ir_differential(_program())
    assert evidence.match
    assert evidence.reference.accepted
    assert evidence.reference.identity == evidence.candidate.identity
    assert evidence.reference.diagnostic_code == 0


def test_canonical_json_is_versioned_and_structural_changes_change_identity() -> None:
    program = _program()
    document = canonical_ir_json(program)
    assert f'"format":"{M281_MODEL_FORMAT}"' in document
    assert f'"version":"{M281_MODEL_VERSION}"' in document
    changed = replace(
        program.functions[0].blocks[0].instructions[1],
        operands=(0, 1),
    )
    changed_program = replace(
        program,
        functions=(
            replace(
                program.functions[0],
                blocks=(replace(program.functions[0].blocks[0], instructions=(program.functions[0].blocks[0].instructions[0], changed, program.functions[0].blocks[0].instructions[2])),),
            ),
        ),
    )
    assert canonical_ir_identity(program) != canonical_ir_identity(changed_program)


def test_model_bounds_fail_before_candidate_execution() -> None:
    instruction = CanonicalIRInstruction(IROpcode.ADD, operands=(0, 0, 0, 0, 0))
    oversized = replace(
        _program(),
        functions=(
            replace(
                _program().functions[0],
                blocks=(CanonicalIRBlock(11, (instruction,)),),
            ),
        ),
    )
    with pytest.raises(CanonicalIRModelError, match="operand count"):
        run_canonical_ir_differential(oversized)
