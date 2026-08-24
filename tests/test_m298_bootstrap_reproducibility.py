"""M2.98 bootstrap reproducibility seal contracts."""

from dataclasses import replace
from pathlib import Path

import pytest

from bootstrap.s3.bootstrap_admission import run_bootstrap_admission_differential
from bootstrap.s3.bootstrap_reproducibility import (
    BootstrapReproducibilityError,
    run_bootstrap_reproducibility_differential,
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
    ROOT / "selfhost" / "bootstrap" / "bootstrap_reproducibility_candidate.s3"
).read_text(encoding="utf-8")


def _admission():
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
    admission, _ = run_bootstrap_admission_differential(artifact)
    return admission


def test_candidate_source_has_one_seal_entrypoint_and_no_main() -> None:
    assert "fn seal_bootstrap" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_reproducibility_seal_matches_and_is_positive() -> None:
    reference, candidate = run_bootstrap_reproducibility_differential(_admission())
    assert reference == candidate
    assert reference.reproducible
    assert reference.first_identity == reference.second_identity
    assert reference.host_tool_required
    assert reference.native_artifact is None


def test_seal_identity_changes_with_admission_identity() -> None:
    first, _ = run_bootstrap_reproducibility_differential(_admission())
    changed, _ = run_bootstrap_reproducibility_differential(
        replace(_admission(), admission_identity=(first.admission_identity + 1) % 181)
    )
    assert first.seal_identity != changed.seal_identity


def test_disallowed_admission_is_rejected() -> None:
    with pytest.raises(BootstrapReproducibilityError, match="not allowed"):
        run_bootstrap_reproducibility_differential(
            replace(_admission(), bootstrap_allowed=False)
        )


def test_native_artifact_is_rejected() -> None:
    with pytest.raises(BootstrapReproducibilityError, match="native boundary"):
        run_bootstrap_reproducibility_differential(
            replace(_admission(), native_artifact=b"native")
        )
