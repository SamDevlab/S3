"""M2.95 bounded compiler-driver composition contracts."""

from pathlib import Path

import pytest

from bootstrap.s3.bounded_compiler_driver import (
    BoundedCompilerDriverError,
    run_bounded_compiler_driver_differential,
)
from bootstrap.s3.canonical_ir_candidate import (
    CanonicalIRBlock,
    CanonicalIRFunction,
    CanonicalIRInstruction,
    CanonicalIRProgram,
)
from bootstrap.s3.ir import IROpcode, IRType
from bootstrap.s3.source_workspace_boundary import (
    SourceUnit,
    WorkspaceLoadRequest,
    prepare_workspace_reference,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (
    ROOT / "selfhost" / "driver" / "bounded_compiler_driver_candidate.s3"
).read_text(encoding="utf-8")


def _program(immediate: int = 1) -> CanonicalIRProgram:
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
                            CanonicalIRInstruction(IROpcode.CONST, result=0, immediate=immediate),
                            CanonicalIRInstruction(IROpcode.ADD, result=1, operands=(0, 0)),
                            CanonicalIRInstruction(IROpcode.RETURN, operands=(1,)),
                        ),
                    ),
                ),
            ),
        ),
    )


def _workspace(digest: str = "0" * 64):
    return prepare_workspace_reference(
        WorkspaceLoadRequest((SourceUnit("src/main.s3", digest),))
    )


def test_candidate_source_has_one_driver_entrypoint_and_no_main() -> None:
    assert "fn compose_bounded_plan" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_driver_composes_verified_ir_assembly_and_native_boundary() -> None:
    reference, candidate = run_bounded_compiler_driver_differential(
        _workspace(), _program(), "x86_64"
    )
    assert reference == candidate
    assert reference.host_tool_required
    assert reference.native_artifact is None
    assert reference.assembly_text.startswith(".s3asm 0.6.0\n")


def test_source_metadata_and_ir_both_contribute_to_driver_identity() -> None:
    first, _ = run_bounded_compiler_driver_differential(
        _workspace(), _program(), "x86_64"
    )
    changed_workspace, _ = run_bounded_compiler_driver_differential(
        _workspace("1" * 64), _program(), "x86_64"
    )
    changed_ir, _ = run_bounded_compiler_driver_differential(
        _workspace(), _program(2), "x86_64"
    )
    assert first.plan_identity != changed_workspace.plan_identity
    assert first.plan_identity != changed_ir.plan_identity


def test_unknown_target_fails_closed() -> None:
    with pytest.raises(BoundedCompilerDriverError, match="unsupported native target"):
        run_bounded_compiler_driver_differential(_workspace(), _program(), "wasm32")


def test_invalid_ir_fails_before_driver_plan() -> None:
    invalid = CanonicalIRProgram(
        functions=(
            CanonicalIRFunction(
                name_id=0,
                return_type=IRType.TRYTE,
                register_types=(IRType.TRYTE,),
                blocks=(
                    CanonicalIRBlock(
                        name_id=0,
                        instructions=(CanonicalIRInstruction(IROpcode.CONST, result=0, immediate=1),),
                    ),
                ),
            ),
        ),
    )
    with pytest.raises(BoundedCompilerDriverError, match="emitted Assembly"):
        run_bounded_compiler_driver_differential(_workspace(), invalid, "x86_64")
