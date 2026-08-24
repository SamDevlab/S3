"""M2.97 controlled bootstrap admission contracts."""

from dataclasses import replace
from pathlib import Path

import pytest

from bootstrap.s3.bootstrap_admission import (
    BootstrapAdmissionError,
    run_bootstrap_admission_differential,
)
from bootstrap.s3.bounded_compiler_driver import run_bounded_compiler_driver_differential
from bootstrap.s3.canonical_ir_candidate import (
    CanonicalIRBlock,
    CanonicalIRFunction,
    CanonicalIRInstruction,
    CanonicalIRProgram,
)
from bootstrap.s3.driver_artifact_handoff import run_driver_artifact_handoff_differential
from bootstrap.s3.ir import IROpcode, IRType
from bootstrap.s3.source_workspace_boundary import (
    SourceUnit,
    WorkspaceLoadRequest,
    prepare_workspace_reference,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (
    ROOT / "selfhost" / "bootstrap" / "bootstrap_admission_candidate.s3"
).read_text(encoding="utf-8")


def _artifact():
    program = CanonicalIRProgram(
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
    workspace = prepare_workspace_reference(
        WorkspaceLoadRequest((SourceUnit("src/main.s3", "0" * 64),))
    )
    driver, _ = run_bounded_compiler_driver_differential(workspace, program, "x86_64")
    artifact, _ = run_driver_artifact_handoff_differential(driver)
    return artifact


def test_candidate_source_has_one_admission_entrypoint_and_no_main() -> None:
    assert "fn admit_bootstrap" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_bootstrap_admission_matches_and_is_explicit() -> None:
    reference, candidate = run_bootstrap_admission_differential(_artifact())
    assert reference == candidate
    assert reference.bootstrap_allowed
    assert reference.host_tool_required
    assert reference.native_artifact is None


def test_admission_identity_changes_with_artifact_identity() -> None:
    first, _ = run_bootstrap_admission_differential(_artifact())
    changed, _ = run_bootstrap_admission_differential(
        replace(_artifact(), artifact_identity=(first.artifact_identity + 1) % 181)
    )
    assert first.admission_identity != changed.admission_identity


def test_native_artifact_is_not_admitted() -> None:
    with pytest.raises(BootstrapAdmissionError, match="host boundary"):
        run_bootstrap_admission_differential(replace(_artifact(), native_artifact=b"native"))


def test_corrupt_assembly_is_not_admitted() -> None:
    with pytest.raises(BootstrapAdmissionError, match="verification"):
        run_bootstrap_admission_differential(replace(_artifact(), assembly_text="invalid"))
