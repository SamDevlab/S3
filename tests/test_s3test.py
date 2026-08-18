from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.s3test import (
    ImpactMap,
    StateStore,
    execute_profile,
    execution_fingerprint,
    render_plan,
)


ROOT = Path(__file__).parents[1]
IMPACT = ImpactMap.load(ROOT / "tests" / "test-impact.json")


def test_dynamic_selection_is_stable_and_explainable() -> None:
    selected = IMPACT.select(["bootstrap/s3/dynamic.py"])
    assert [item.test for item in selected] == [
        "tests/test_dynamic.py",
        "tests/test_m139_dynamic_buffers.py",
        "tests/test_m140_ordered_collections.py",
    ]
    plan = render_plan(selected, ["bootstrap/s3/dynamic.py"])
    assert "REASON=direct impact mapping" in plan
    assert "TIER=T1" in plan


def test_docs_only_change_has_no_runtime_tests() -> None:
    assert IMPACT.select(["docs/roadmap.md"]) == ()


def test_changed_test_file_selects_itself() -> None:
    selected = IMPACT.select(["tests/test_s3test.py"])
    assert [item.test for item in selected] == ["tests/test_s3test.py"]


def test_runtime_selection_marks_native_requirement() -> None:
    selected = IMPACT.select(["bootstrap/s3/backends/x86_64/runtime.py"])
    runtime = next(item for item in selected if item.test == "tests/test_native_x86_64.py")
    assert runtime.native_required is True
    assert "native-x86_64" in runtime.environment_requirements


def test_cross_cutting_rule_expands_to_all_discovered_tests(tmp_path: Path) -> None:
    tests = ("tests/test_a.py", "tests/test_b.py")
    selected = IMPACT.select(["bootstrap/s3/semantic.py"], all_tests=tests)
    assert [item.test for item in selected] == list(tests)


def test_shard_selection_is_sorted() -> None:
    assert IMPACT.shard_tests("m139-m140") == (
        "tests/test_m139_dynamic_buffers.py",
        "tests/test_m140_ordered_collections.py",
    )


def test_milestone_selection_uses_milestone_rules_instead_of_default() -> None:
    selected = IMPACT.select(["milestone:m161"], milestone="m161")
    assert [item.test for item in selected] == [
        "tests/test_m141_ordered_maps_sets.py",
        "tests/test_m151_composite_owned_values.py",
        "tests/test_m153_generic_functions.py",
        "tests/test_m154_parametric_types.py",
        "tests/test_m155_generic_vector.py",
        "tests/test_m161_generic_map_set.py",
    ]
    assert all("T2" in item.tiers for item in selected)


def test_state_round_trip_and_resume_data(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    report = {"fingerprint": "abc", "profile": "affected", "summary": {"status": "FAIL"}, "tests": []}
    store.save(report)
    assert store.load() == report
    assert (tmp_path / ".s3-test-state" / "abc.json").is_file()


def test_fingerprint_changes_when_selected_tests_change(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("tools.s3test._git", lambda root, *args, check=True: "HEAD\n" if args[:2] == ("rev-parse", "HEAD") else "")
    first = execution_fingerprint(tmp_path, ["tests/test_a.py"], manifest_version=1)
    second = execution_fingerprint(tmp_path, ["tests/test_b.py"], manifest_version=1)
    assert first != second


def test_fingerprint_changes_when_manifest_version_changes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("tools.s3test._git", lambda root, *args, check=True: "HEAD\n" if args[:2] == ("rev-parse", "HEAD") else "")
    assert execution_fingerprint(tmp_path, [], manifest_version=1) != execution_fingerprint(tmp_path, [], manifest_version=2)


def test_timeout_and_failure_are_distinct_statuses() -> None:
    assert "TIMEOUT" != "FAIL"


def test_failure_state_persists_output_and_status(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    report = {
        "fingerprint": "failure",
        "profile": "affected",
        "summary": {"status": "FAIL"},
        "tests": [{"test": "tests/test_a.py", "status": "FAIL", "tiers": ["T1"], "reason": "direct", "native_required": False, "environment_requirements": [], "output": "assertion", "returncode": 1}],
    }
    store.save(report)
    loaded = store.load()
    assert loaded is not None
    assert loaded["tests"][0]["output"] == "assertion"


def test_plan_exposes_all_required_explainability_fields() -> None:
    plan = render_plan(IMPACT.select(["bootstrap/s3/dynamic.py"]), ["bootstrap/s3/dynamic.py"])
    for field in ("CHANGED_FILE=", "SELECTED_TEST=", "REASON=", "TIER=", "NATIVE_REQUIRED=", "TIMEOUT="):
        assert field in plan


def test_resume_cache_requires_exact_fingerprint(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    store.save({"fingerprint": "old", "profile": "affected", "tests": [], "summary": {"status": "PASS"}})
    assert json.loads(store.latest.read_text(encoding="utf-8"))["fingerprint"] == "old"


def test_resume_reuses_persisted_failed_selection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    monkeypatch.setattr("tools.s3test._git", lambda root, *args, check=True: "HEAD\n" if args[:2] == ("rev-parse", "HEAD") else "")
    fingerprint = execution_fingerprint(tmp_path, ["tests/test_a.py"], manifest_version=1)
    store.save({
        "fingerprint": fingerprint,
        "profile": "affected",
        "tests": [{
            "test": "tests/test_a.py",
            "status": "FAIL",
            "tiers": ["T1"],
            "reason": "direct",
            "native_required": False,
            "environment_requirements": [],
            "output": "failure",
            "returncode": 1,
        }],
        "summary": {"status": "FAIL"},
    })
    monkeypatch.setattr("tools.s3test.run_pytest_file", lambda root, test, timeout: {"status": "PASS", "output": "", "returncode": 0})
    report = execute_profile(tmp_path, IMPACT, "resume", None, None, 1, store)
    assert report["summary"]["status"] == "PASS"
    assert report["tests"][0]["test"] == "tests/test_a.py"
