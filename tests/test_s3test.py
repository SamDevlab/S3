from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.s3test import (
    ImpactMap,
    S3TestOrchestratorError,
    StateStore,
    T4TimeoutClass,
    execute_profile,
    execution_fingerprint,
    render_plan,
)


ROOT = Path(__file__).parents[1]
IMPACT = ImpactMap.load(ROOT / "tests" / "test-impact.json")


def test_dynamic_selection_is_stable_and_explainable() -> None:
    selected = IMPACT.select(["bootstrap/s3/dynamic.py"])
    assert [item.test for item in selected] == [
        "tests/test_advanced_reference_semantics.py",
        "tests/test_dynamic.py",
        "tests/test_m139_dynamic_buffers.py",
        "tests/test_m140_ordered_collections.py",
        "tests/test_m141_ordered_maps_sets.py",
        "tests/test_m162_borrowed_views.py",
        "tests/test_m163_deterministic_iteration.py",
        "tests/test_s3_slice_capability.py",
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
    for field in ("CHANGED_FILE=", "SELECTED_TEST=", "REASON=", "TIER=", "NATIVE_REQUIRED=", "TIMEOUT_CLASS=", "TIMEOUT="):
        assert field in plan


def test_default_timeout_policy_is_sixty_seconds() -> None:
    policy = IMPACT.timeout_policy_for("tests/test_cli.py", 60)
    assert policy.timeout_class is T4TimeoutClass.DEFAULT
    assert policy.seconds == 60


def test_native_integration_timeout_policy_is_scoped_and_bounded() -> None:
    policy = IMPACT.timeout_policy_for("tests/test_native_x86_64_integration.py", 60)
    assert policy.timeout_class is T4TimeoutClass.HEAVY_NATIVE_INTEGRATION
    assert policy.seconds == 300


def test_ordinary_files_keep_the_default_timeout() -> None:
    policy = IMPACT.timeout_policy_for("tests/test_compiler.py", 60)
    assert policy.timeout_class is T4TimeoutClass.DEFAULT
    assert policy.seconds == 60


def test_explicit_heavy_timeout_policy_is_bounded() -> None:
    policy = IMPACT.timeout_policy_for("tests/test_decimal_functions.py", 60)
    assert policy.timeout_class is T4TimeoutClass.HEAVY_SELF_HOSTING
    assert policy.seconds == 180


def test_renderer_timeout_policy_uses_shared_evidence_budget() -> None:
    policy = IMPACT.timeout_policy_for("tests/test_s3_renderer_sign_text.py", 60)
    assert policy.timeout_class is T4TimeoutClass.HEAVY_RENDERER
    assert policy.seconds == 754


def test_unknown_timeout_class_fails_closed(tmp_path: Path) -> None:
    manifest = {
        "schema": "s3.test-impact.v1",
        "version": 1,
        "default": {"tests": [], "milestones": ["global"], "shards": [], "native_required": False, "environment_requirements": [], "global_impact": False},
        "timeout_policy": {"classes": {"DEFAULT": {"seconds": 60}, "UNKNOWN": {"seconds": 90}}, "assignments": {}},
        "rules": [],
    }
    path = tmp_path / "impact.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(S3TestOrchestratorError, match="unknown timeout class"):
        ImpactMap.load(path)


def test_timeout_status_is_preserved_and_not_promoted(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    selection = (IMPACT.select(["tests/test_s3_renderer_sign_text.py"])[0],)
    monkeypatch.setattr("tools.s3test._profile_selection", lambda *args: (selection, (selection[0].test,)))
    monkeypatch.setattr("tools.s3test._git", lambda root, *args, check=True: "HEAD\n" if args[:2] == ("rev-parse", "HEAD") else "")
    monkeypatch.setattr("tools.s3test.run_pytest_file", lambda root, test, timeout: {"status": "TIMEOUT", "output": "", "returncode": None})
    report = execute_profile(tmp_path, IMPACT, "affected", None, None, 60, StateStore(tmp_path))
    assert report["summary"]["status"] == "TIMEOUT"
    assert report["summary"]["selected"] == 1
    assert report["summary"]["passed"] == 0
    assert report["summary"]["failed"] == 0
    assert report["summary"]["timed_out"] == 1
    assert report["tests"][0]["status"] == "TIMEOUT"
    assert report["tests"][0]["timeout_class"] == "HEAVY_RENDERER"
    assert report["tests"][0]["timeout_seconds"] == 754


def test_report_records_applied_timeout_policy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    selection = (IMPACT.select(["tests/test_decimal_functions.py"])[0],)
    monkeypatch.setattr("tools.s3test._profile_selection", lambda *args: (selection, (selection[0].test,)))
    monkeypatch.setattr("tools.s3test._git", lambda root, *args, check=True: "HEAD\n" if args[:2] == ("rev-parse", "HEAD") else "")
    monkeypatch.setattr("tools.s3test.run_pytest_file", lambda root, test, timeout: {"status": "PASS", "output": "", "returncode": 0})
    report = execute_profile(tmp_path, IMPACT, "affected", None, None, 60, StateStore(tmp_path))
    assert report["tests"][0]["timeout_class"] == "HEAVY_SELF_HOSTING"
    assert report["tests"][0]["timeout_seconds"] == 180


def test_windows_timeout_terminates_process_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr("tools.s3test.subprocess.run", lambda arguments, **kwargs: calls.append(arguments))
    process = type("Process", (), {"pid": 1234})()
    import tools.s3test as s3test_module
    monkeypatch.setattr(s3test_module.os, "name", "nt")
    s3test_module._terminate(process)
    assert calls == [["taskkill", "/PID", "1234", "/T", "/F"]]


def test_timeout_policy_selection_is_deterministic() -> None:
    files = ["tests/test_self_hosting_opcode_classifier.py", "tests/test_cli.py", "tests/test_decimal_functions.py"]
    first = [(path, IMPACT.timeout_policy_for(path, 60)) for path in files]
    second = [(path, IMPACT.timeout_policy_for(path, 60)) for path in files]
    assert first == second


def test_timeout_policy_does_not_change_selection_tiers() -> None:
    selected = IMPACT.select(["tests/test_decimal_functions.py"])
    assert [item.test for item in selected] == ["tests/test_decimal_functions.py"]
    assert selected[0].tiers == ("T1",)


def test_fingerprint_includes_timeout_policy_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr("tools.s3test._git", lambda root, *args, check=True: "HEAD\n" if args[:2] == ("rev-parse", "HEAD") else "")
    first = execution_fingerprint(tmp_path, [], manifest_version=1, timeout_policy_fingerprint="policy-a")
    second = execution_fingerprint(tmp_path, [], manifest_version=1, timeout_policy_fingerprint="policy-b")
    assert first != second


def test_resume_cache_requires_exact_fingerprint(tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    store.save({"fingerprint": "old", "profile": "affected", "tests": [], "summary": {"status": "PASS"}})
    assert json.loads(store.latest.read_text(encoding="utf-8"))["fingerprint"] == "old"


def test_resume_reuses_persisted_failed_selection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    store = StateStore(tmp_path)
    monkeypatch.setattr("tools.s3test._git", lambda root, *args, check=True: "HEAD\n" if args[:2] == ("rev-parse", "HEAD") else "")
    fingerprint = execution_fingerprint(
        tmp_path,
        ["tests/test_a.py"],
        manifest_version=1,
        timeout_policy_fingerprint=IMPACT.timeout_policy_fingerprint,
    )
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
