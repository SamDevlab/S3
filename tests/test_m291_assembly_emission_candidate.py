"""M2.91 bounded Assembly emission contracts."""

from dataclasses import replace
from pathlib import Path

import pytest

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.assembly_emission_candidate import (
    AssemblyEmissionError,
    run_assembly_emission_differential,
)
from bootstrap.s3.canonical_ir_candidate import (
    CanonicalIRBlock,
    CanonicalIRFunction,
    CanonicalIRInstruction,
    CanonicalIRProgram,
)
from bootstrap.s3.ir import IRType, IROpcode


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (
    ROOT / "selfhost" / "assembly" / "assembly_emission_candidate.s3"
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


def test_candidate_source_has_one_emission_entrypoint_and_no_main() -> None:
    assert "fn emit_linear_assembly" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_emitted_reference_text_is_valid_and_identity_matches_candidate() -> None:
    reference, candidate = run_assembly_emission_differential(_program())
    assert reference == candidate
    assert reference.text.startswith(".s3asm 0.6.0\n")
    assert ".function f0 -> tryte" in reference.text
    assert "TCONST" in reference.text
    assert "TADD" in reference.text
    assert "TRET" in reference.text
    parse_assembly(reference.text)


def test_immediate_change_changes_rendered_text_and_identity() -> None:
    first, _ = run_assembly_emission_differential(_program())
    instruction = _program().functions[0].blocks[0].instructions[0]
    changed = replace(
        _program(),
        functions=(
            replace(
                _program().functions[0],
                blocks=(
                    replace(
                        _program().functions[0].blocks[0],
                        instructions=(replace(instruction, immediate=2),) + instruction_tuple_tail(),
                    ),
                ),
            ),
        ),
    )
    second, _ = run_assembly_emission_differential(changed)
    assert first.text != second.text
    assert first.identity != second.identity


def instruction_tuple_tail() -> tuple[CanonicalIRInstruction, ...]:
    return (
        CanonicalIRInstruction(IROpcode.ADD, result=1, operands=(0, 0)),
        CanonicalIRInstruction(IROpcode.RETURN, operands=(1,)),
    )


def test_invalid_ir_is_rejected_before_emission() -> None:
    block = _program().functions[0].blocks[0]
    invalid = replace(
        _program(),
        functions=(
            replace(_program().functions[0], blocks=(replace(block, instructions=block.instructions[:2]),)),
        ),
    )
    with pytest.raises(AssemblyEmissionError, match="rejected"):
        run_assembly_emission_differential(invalid)
