"""M2.92 emitted Assembly verification closure contracts."""

from dataclasses import replace
from pathlib import Path

import pytest

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.assembly_verifier import AssemblyVerifier
from bootstrap.s3.assembly_verification_closure import (
    AssemblyVerificationClosureError,
    run_assembly_verification_differential,
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
    ROOT / "selfhost" / "assembly" / "assembly_verification_closure.s3"
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


def test_candidate_source_has_one_verification_entrypoint_and_no_main() -> None:
    assert "fn verify_emitted_assembly" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_emitted_text_is_parsed_and_verified_before_candidate_match() -> None:
    reference, candidate = run_assembly_verification_differential(_program())
    assert reference == candidate
    assert reference.verified
    parsed = parse_assembly(reference.emission.text)
    AssemblyVerifier().validate(parsed, entry="f0")


def test_changed_ir_changes_verification_identity() -> None:
    first, _ = run_assembly_verification_differential(_program())
    instruction = _program().functions[0].blocks[0].instructions[0]
    changed = replace(
        _program(),
        functions=(
            replace(
                _program().functions[0],
                blocks=(
                    replace(
                        _program().functions[0].blocks[0],
                        instructions=(replace(instruction, immediate=2),) + _program().functions[0].blocks[0].instructions[1:],
                    ),
                ),
            ),
        ),
    )
    second, _ = run_assembly_verification_differential(changed)
    assert first.verification_identity != second.verification_identity


def test_invalid_ir_is_rejected_before_assembly_verification() -> None:
    block = _program().functions[0].blocks[0]
    invalid = replace(
        _program(),
        functions=(replace(_program().functions[0], blocks=(replace(block, instructions=block.instructions[:2]),)),),
    )
    with pytest.raises(AssemblyVerificationClosureError, match="emitted Assembly"):
        run_assembly_verification_differential(invalid)
