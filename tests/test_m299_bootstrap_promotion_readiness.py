"""M2.99 bootstrap promotion-readiness contracts."""

from dataclasses import replace
from pathlib import Path

import pytest

from bootstrap.s3.bootstrap_admission import run_bootstrap_admission_differential
from bootstrap.s3.bootstrap_promotion_readiness import (
    BootstrapPromotionReadinessError,
    run_bootstrap_promotion_readiness_differential,
)
from bootstrap.s3.bootstrap_reproducibility import run_bootstrap_reproducibility_differential
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
    ROOT / "selfhost" / "bootstrap" / "bootstrap_promotion_readiness_candidate.s3"
).read_text(encoding="utf-8")


def _seal():
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
    seal, _ = run_bootstrap_reproducibility_differential(admission)
    return seal


def test_candidate_source_has_one_readiness_entrypoint_and_no_main() -> None:
    assert "fn assess_promotion_readiness" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


def test_readiness_matches_without_promoting_production() -> None:
    reference, candidate = run_bootstrap_promotion_readiness_differential(_seal(), "x86_64")
    assert reference == candidate
    assert reference.candidate_ready
    assert not reference.production_promotion
    assert not reference.full_self_hosting_claim


def test_decision_identity_changes_with_seal() -> None:
    first, _ = run_bootstrap_promotion_readiness_differential(_seal(), "x86_64")
    changed, _ = run_bootstrap_promotion_readiness_differential(
        replace(_seal(), seal_identity=(first.seal_identity + 1) % 181), "x86_64"
    )
    assert first.decision_identity != changed.decision_identity


def test_invalid_reproducibility_seal_is_rejected() -> None:
    with pytest.raises(BootstrapPromotionReadinessError, match="reproducibility"):
        run_bootstrap_promotion_readiness_differential(
            replace(_seal(), reproducible=False), "x86_64"
        )


def test_unknown_target_is_rejected() -> None:
    with pytest.raises(BootstrapPromotionReadinessError, match="unsupported"):
        run_bootstrap_promotion_readiness_differential(_seal(), "wasm32")
