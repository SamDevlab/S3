"""M3.00 final bounded self-hosting checkpoint contracts."""

from pathlib import Path

from bootstrap.s3.bootstrap_promotion_readiness import (
    BootstrapPromotionReadiness,
)
from tools.s3test import ImpactMap, _profile_selection


ROOT = Path(__file__).parents[1]
IMPACT = ImpactMap.load(ROOT / "tests" / "test-impact.json")
EXPECTED = (
    "tests/test_m281_canonical_ir_data_model.py",
    "tests/test_m282_expression_lowering_candidate.py",
    "tests/test_m283_call_aggregate_lowering_candidate.py",
    "tests/test_m284_ir_verifier_candidate.py",
    "tests/test_m285_composed_ir_closure_candidate.py",
    "tests/test_m286_ir_verifier_canary.py",
    "tests/test_m287_lowering_checkpoint_candidate.py",
    "tests/test_m288_composed_lowering_closure_candidate.py",
    "tests/test_m289_lowering_canary.py",
    "tests/test_m290_ir_lowering_checkpoint.py",
    "tests/test_m291_assembly_emission_candidate.py",
    "tests/test_m292_assembly_verification_closure.py",
    "tests/test_m293_native_emission_boundary.py",
    "tests/test_m294_source_workspace_boundary.py",
    "tests/test_m295_bounded_compiler_driver.py",
    "tests/test_m296_driver_artifact_handoff.py",
    "tests/test_m297_bootstrap_admission.py",
    "tests/test_m298_bootstrap_reproducibility.py",
    "tests/test_m299_bootstrap_promotion_readiness.py",
)


def test_bootstrap_level_c_profile_covers_m281_through_m299_in_order() -> None:
    selections, tests = _profile_selection(ROOT, IMPACT, "level-c-bootstrap", None, None)
    assert tests == EXPECTED
    assert tuple(selection.test for selection in selections) == EXPECTED
    assert all(selection.tiers == ("LEVEL-C",) for selection in selections)


def test_bootstrap_level_c_profile_is_not_t4() -> None:
    selections, _ = _profile_selection(ROOT, IMPACT, "level-c-bootstrap", None, None)
    assert all("T4" not in selection.tiers for selection in selections)


def test_final_checkpoint_keeps_production_promotion_disabled() -> None:
    decision = BootstrapPromotionReadiness(
        seal_identity=1,
        admission_identity=2,
        target="x86_64",
        candidate_ready=True,
        production_promotion=False,
        full_self_hosting_claim=False,
        decision_identity=3,
    )
    assert decision.candidate_ready
    assert not decision.production_promotion
    assert not decision.full_self_hosting_claim


def test_final_checkpoint_is_explicitly_bounded() -> None:
    selections, _ = _profile_selection(ROOT, IMPACT, "level-c-bootstrap", None, None)
    assert len(selections) == 19
    assert all(selection.native_required is False for selection in selections)
