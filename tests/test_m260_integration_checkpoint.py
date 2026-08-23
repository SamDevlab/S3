"""M2.60 full-cycle Level-C profile contracts."""

from __future__ import annotations

from pathlib import Path

from tools.s3test import ImpactMap, _profile_selection


ROOT = Path(__file__).parents[1]
IMPACT = ImpactMap.load(ROOT / "tests" / "test-impact.json")


EXPECTED = (
    "tests/test_m241_workspace_semantic_graph.py",
    "tests/test_m242_lsp_project_intelligence.py",
    "tests/test_m243_linux_native_conformance.py",
    "tests/test_m244_http2_dynamic_hpack.py",
    "tests/test_m245_signed_registry.py",
    "tests/test_m246_async_network_soak.py",
    "tests/test_m248_experiment_promotion.py",
    "tests/test_m249_cross_target_evidence.py",
    "tests/test_m250_integration_checkpoint.py",
    "tests/test_m251_dynamic_text.py",
    "tests/test_m252_deterministic_collections.py",
    "tests/test_m253_arena_memory.py",
    "tests/test_m254_recursive_substrate.py",
    "tests/test_m255_source_manager.py",
    "tests/test_m256_structured_diagnostics.py",
    "tests/test_m257_canonical_serialization.py",
    "tests/test_m258_differential_harness.py",
    "tests/test_m259_candidate_promotion.py",
    "tests/test_s3bench_repeatability.py",
)


def test_level_c_full_covers_m241_through_m259_in_order() -> None:
    selections, tests = _profile_selection(
        ROOT, IMPACT, "level-c-full", None, None
    )
    assert tests == EXPECTED
    assert tuple(selection.test for selection in selections) == EXPECTED
    assert all(selection.tiers == ("LEVEL-C",) for selection in selections)


def test_level_c_full_is_not_t4() -> None:
    selections, _ = _profile_selection(ROOT, IMPACT, "level-c-full", None, None)
    assert all("T4" not in selection.tiers for selection in selections)
