"""Focused contracts for the V2.1 attribution laboratory."""

from __future__ import annotations

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64.features import extract_function_features
from bootstrap.s3.backends.x86_64.policy import BASELINE_NATIVE_POLICY
from bootstrap.s3.backends.x86_64.shadow_governor import ShadowGovernor
from tools.native_policy_search_v21 import (
    _ablation_policies,
    _active_genes,
    _estimate_split_cost,
    attribution_polarity,
    build_attribution_corpus,
)


def test_attribution_corpus_has_all_families_and_polarities() -> None:
    cases = build_attribution_corpus()
    assert len(cases) == 60
    assert {case.family for case in cases} == {
        "indexed_memory",
        "scalar_replacement",
        "register_pressure",
        "localized_pressure",
        "constant_rematerialization",
        "loop_live_range",
        "calls_abi",
        "references_aliasing",
        "mixed_realistic",
        "negative_control",
    }
    assert {attribution_polarity(case) for case in cases} == {"positive", "negative"}
    assert len({case.case_id for case in cases}) == 60


def test_ablation_matrix_is_complete_and_baseline_is_explicit() -> None:
    policies = _ablation_policies()
    assert tuple(policies) == ("000", "001", "010", "011", "100", "101", "110", "111")
    assert policies["000"].to_dict() == BASELINE_NATIVE_POLICY.to_dict() | {"name": "abl_000"}
    assert policies["111"].indexed_memory_policy == "compact_ea"
    assert policies["111"].scalar_promotion == "conservative_mem2reg"
    assert policies["111"].spill_policy == "region_aware"


def test_genome_identity_comes_from_policy_config() -> None:
    config = BASELINE_NATIVE_POLICY.to_dict()
    config["name"] = "historical_label_must_not_control_identity"
    active, inactive, canonical = _active_genes(config)
    assert active == []
    assert "COMPACT_INDEXED_MEMORY" in inactive
    assert canonical == "BASELINE"


def test_shadow_governor_falls_back_for_reference_escape() -> None:
    program = parse_assembly(
        """
.function main -> tryte
    .register r0, tryte
    .register r1, reference
.label entry
    TCONST r0, 4
    TADDR r1, r0
    TRET r0
.end
"""
    )
    function = program.functions[0]
    features = extract_function_features(function)
    policies = {"BASELINE": BASELINE_NATIVE_POLICY}
    decision = ShadowGovernor("BASELINE").recommend(features, policies)
    assert decision.policy_id == "BASELINE"
    assert decision.fallback_used is True


def test_live_range_cost_gate_is_deterministic_and_fail_closed_on_equal_cost() -> None:
    program = parse_assembly(
        """
.function main -> tryte
    .register r0, trit
    .register r1, tryte
.label entry
    TCONST r0, -1
    TCONST r1, 1
    TJMP loop
.label loop
    TBR3 r0, body, exit, exit
.label body
    TCONST r0, 0
    TJMP loop
.label exit
    TRET r1
.end
"""
    )
    first = _estimate_split_cost(program.functions[0], BASELINE_NATIVE_POLICY)
    second = _estimate_split_cost(program.functions[0], BASELINE_NATIVE_POLICY)
    assert first == second
    assert first["decision"] in {"APPLY", "BORDERLINE", "SPLIT_REJECTED_BY_COST"}
    if first["prediction"]["estimated_benefit"] <= first["prediction"]["estimated_cost"]:
        assert first["decision"] != "APPLY"
