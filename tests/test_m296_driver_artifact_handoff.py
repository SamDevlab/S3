"""M2.96 deterministic driver artifact handoff contracts."""

from dataclasses import replace
from pathlib import Path

import pytest

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.assembly_verifier import AssemblyVerifier
from bootstrap.s3.bounded_compiler_driver import (
    run_bounded_compiler_driver_differential,
)
from bootstrap.s3.driver_artifact_handoff import (
    DriverArtifactHandoffError,
    run_driver_artifact_handoff_differential,
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
    ROOT / "selfhost" / "driver" / "driver_artifact_handoff_candidate.s3"
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


def _plan(immediate: int = 1):
    workspace = prepare_workspace_reference(
        WorkspaceLoadRequest((SourceUnit("src/main.s3", "0" * 64),))
    )
    return run_bounded_compiler_driver_differential(workspace, _program(immediate), "x86_64")[0]


def test_candidate_source_has_one_handoff_entrypoint_and_no_main() -> None:
    assert "fn compose_driver_handoff" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_handoff_matches_and_revalidates_assembly() -> None:
    reference, candidate = run_driver_artifact_handoff_differential(_plan())
    assert reference == candidate
    assert reference.format == "s3.driver-artifact.v1"
    assert reference.host_tool_required
    assert reference.native_artifact is None
    parsed = parse_assembly(reference.assembly_text)
    AssemblyVerifier().validate(parsed, entry="f0")


def test_handoff_identity_changes_with_driver_artifact_inputs() -> None:
    first, _ = run_driver_artifact_handoff_differential(_plan())
    changed, _ = run_driver_artifact_handoff_differential(_plan(2))
    assert first.artifact_identity != changed.artifact_identity


def test_native_artifact_cannot_cross_handoff() -> None:
    invalid = replace(_plan(), native_artifact=b"native")
    with pytest.raises(DriverArtifactHandoffError, match="native boundary"):
        run_driver_artifact_handoff_differential(invalid)


def test_corrupt_assembly_cannot_cross_handoff() -> None:
    invalid = replace(_plan(), assembly_text="not Assembly")
    with pytest.raises(DriverArtifactHandoffError, match="verification"):
        run_driver_artifact_handoff_differential(invalid)
