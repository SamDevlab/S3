"""M2.50 Level-C integration profile contracts."""

from __future__ import annotations

from pathlib import Path

from tools.s3test import ImpactMap, _profile_selection


ROOT = Path(__file__).parents[1]
IMPACT = ImpactMap.load(ROOT / "tests" / "test-impact.json")


def test_level_c_contains_exactly_m241_through_m249_shards() -> None:
    selections, tests = _profile_selection(
        ROOT, IMPACT, "level-c", None, None
    )
    assert list(tests) == [
        "tests/test_m241_workspace_semantic_graph.py",
        "tests/test_m242_lsp_project_intelligence.py",
        "tests/test_m243_linux_native_conformance.py",
        "tests/test_m244_http2_dynamic_hpack.py",
        "tests/test_m245_signed_registry.py",
        "tests/test_m246_async_network_soak.py",
        "tests/test_m248_experiment_promotion.py",
        "tests/test_m249_cross_target_evidence.py",
        "tests/test_s3bench_repeatability.py",
    ]
    assert [selection.test for selection in selections] == list(tests)
    assert all(selection.tiers == ("LEVEL-C",) for selection in selections)


def test_level_c_is_not_full_t4() -> None:
    selections, _ = _profile_selection(ROOT, IMPACT, "level-c", None, None)
    assert all("T4" not in selection.tiers for selection in selections)
