from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.core import load_scenario  # noqa: E402
from harness.provider_profile import build_provider_profile  # noqa: E402
from harness.task_pack import (  # noqa: E402
    attach_task_checks,
    load_task_pack,
    render_phase_prompt,
    task_for_scenario,
    validate_task_artifacts,
)


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _init_repo(root: Path, extra_files: tuple[str, ...] = ()) -> str:
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "fixture@example.invalid")
    _git(root, "config", "user.name", "Fixture")
    files = {"bootstrap/s3/numeric.py", "tests/test_numeric_domains.py", *extra_files}
    for relative in files:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("before\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "fixture")
    return _git(root, "rev-parse", "HEAD")


def _validate_real_task(
    tmp_path: Path,
    task_pack: dict[str, object],
    scenario_id: str,
    changed_files: tuple[str, ...],
) -> list[dict[str, object]]:
    repository = tmp_path / scenario_id.replace(".", "-")
    base = _init_repo(repository, changed_files)
    for relative in changed_files:
        (repository / relative).write_text("after\n", encoding="utf-8")
    task = task_for_scenario(task_pack, scenario_id)
    return validate_task_artifacts(task, repository_root=repository, base_commit=base)


def test_real_task_pack_covers_every_agent_memory_scenario() -> None:
    task_pack = load_task_pack(EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json")
    assert task_pack["version"] == "1.0.1"
    task_ids = {row["scenario_id"] for row in task_pack["scenarios"]}
    scenario_ids = {
        load_scenario(path)["scenario_id"]
        for path in (EXTERNAL_ROOT / "scenarios").glob("*.json")
    }
    assert scenario_ids.issubset(task_ids)
    assert len(task_ids) == 7


@pytest.mark.parametrize(
    ("case_id", "scenario_id", "changed_files"),
    [
        (
            "no-memory-host",
            "memory.host-shell-policy.v1",
            ("bootstrap/s3/os_services.py", "tests/test_m166_cross_platform_os_services.py"),
        ),
        (
            "context-only-host",
            "memory.host-shell-policy.v1",
            ("bootstrap/s3/os_services.py", "tests/test_m166_cross_platform_os_services.py"),
        ),
        (
            "no-memory-checked-i64",
            "memory.checked-i64.v1",
            ("bootstrap/s3/numeric.py", "tests/test_numeric_closure.py"),
        ),
        (
            "context-only-checked-i64",
            "memory.checked-i64.v1",
            ("bootstrap/s3/numeric.py", "tests/test_numeric_closure.py"),
        ),
        (
            "no-memory-cross-session",
            "memory.cross-session.v1",
            (
                "bootstrap/s3/alias_analysis.py",
                "bootstrap/s3/host_services.py",
                "bootstrap/s3/numeric.py",
                "bootstrap/s3/os_services.py",
                "tests/test_host_services.py",
                "tests/test_m166_cross_platform_os_services.py",
                "tests/test_numeric_closure.py",
                "tests/test_s3_alias_analysis.py",
            ),
        ),
        (
            "no-memory-cross-agent",
            "memory.cross-agent.v1",
            (
                "bootstrap/s3/alias_analysis.py",
                "bootstrap/s3/host_services.py",
                "bootstrap/s3/lowering.py",
                "bootstrap/s3/os_services.py",
                "tests/test_host_services.py",
                "tests/test_memory_lowering.py",
                "tests/test_s3_alias_analysis.py",
            ),
        ),
    ],
    ids=lambda row: row if isinstance(row, str) else None,
)
def test_v1_0_1_accepts_audited_valid_solution_patterns(
    tmp_path: Path,
    case_id: str,
    scenario_id: str,
    changed_files: tuple[str, ...],
) -> None:
    del case_id
    task_pack = load_task_pack(EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json")
    checks = _validate_real_task(tmp_path, task_pack, scenario_id, changed_files)
    assert all(row["passed"] for row in checks), checks


@pytest.mark.parametrize(
    ("scenario_id", "alternative_file"),
    [
        ("memory.host-shell-policy.v1", "tests/test_host_services.py"),
        ("memory.host-shell-policy.v1", "tests/test_m166_cross_platform_os_services.py"),
        ("memory.checked-i64.v1", "tests/test_numeric_domains.py"),
        ("memory.checked-i64.v1", "tests/test_numeric_closure.py"),
        ("memory.cross-session.v1", "tests/test_numeric_domains.py"),
        ("memory.cross-session.v1", "tests/test_numeric_closure.py"),
        ("memory.cross-agent.v1", "tests/test_compiler.py"),
        ("memory.cross-agent.v1", "tests/test_memory_lowering.py"),
    ],
)
def test_v1_0_1_accepts_each_declared_test_alternative(
    tmp_path: Path,
    scenario_id: str,
    alternative_file: str,
) -> None:
    task_pack = load_task_pack(EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json")
    required = {
        "memory.host-shell-policy.v1": ("bootstrap/s3/os_services.py",),
        "memory.checked-i64.v1": ("bootstrap/s3/numeric.py",),
        "memory.cross-session.v1": (
            "bootstrap/s3/numeric.py",
            "bootstrap/s3/alias_analysis.py",
            "bootstrap/s3/os_services.py",
            "tests/test_s3_alias_analysis.py",
            "tests/test_host_services.py",
        ),
        "memory.cross-agent.v1": (
            "bootstrap/s3/lowering.py",
            "bootstrap/s3/alias_analysis.py",
            "bootstrap/s3/os_services.py",
            "tests/test_s3_alias_analysis.py",
            "tests/test_host_services.py",
        ),
    }[scenario_id]
    changed_files = tuple(dict.fromkeys((*required, alternative_file)))
    checks = _validate_real_task(tmp_path, task_pack, scenario_id, changed_files)
    assert all(row["passed"] for row in checks), checks


@pytest.mark.parametrize(
    ("scenario_id", "changed_files"),
    [
        (
            "memory.cross-session.v1",
            (
                "bootstrap/s3/alias_analysis.py",
                "bootstrap/s3/host_services.py",
                "bootstrap/s3/numeric.py",
                "tests/test_host_services.py",
                "tests/test_numeric_domains.py",
                "tests/test_s3_alias_analysis.py",
            ),
        ),
        (
            "memory.cross-agent.v1",
            (
                "bootstrap/s3/alias_analysis.py",
                "bootstrap/s3/host_services.py",
                "bootstrap/s3/lowering.py",
                "tests/test_compiler.py",
                "tests/test_host_services.py",
                "tests/test_s3_alias_analysis.py",
            ),
        ),
    ],
)
def test_audited_agent_failures_still_require_cross_platform_implementation(
    tmp_path: Path,
    scenario_id: str,
    changed_files: tuple[str, ...],
) -> None:
    task_pack = load_task_pack(EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json")
    checks = _validate_real_task(tmp_path, task_pack, scenario_id, changed_files)
    failed_ids = {row["id"] for row in checks if row["passed"] is not True}
    assert failed_ids == {"task-required:bootstrap/s3/os_services.py"}, checks


def test_phase_a_exposes_contracts_but_phase_b_does_not_restate_ids() -> None:
    task_pack = load_task_pack(EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json")
    scenario = load_scenario(EXTERNAL_ROOT / "scenarios" / "memory.checked-i64.v1.json")
    profile = build_provider_profile("ai-memory", repository_root=EXTERNAL_ROOT.parent)
    phase_a = render_phase_prompt(task_pack, scenario, profile, phase="a")
    phase_b = render_phase_prompt(task_pack, scenario, profile, phase="b")
    assert "i64-overflow-no-wrap" in phase_a
    assert "i64-division-failures" in phase_a
    assert "i64-overflow-no-wrap" not in phase_b
    assert "AI-MEMORY is the only permitted durable handoff channel" in phase_a
    assert "current checkout is authoritative" in phase_b


def test_stale_memory_phase_a_does_not_reveal_current_ffi_answer() -> None:
    task_pack = load_task_pack(EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json")
    scenario = load_scenario(EXTERNAL_ROOT / "scenarios" / "memory.stale-memory.v1.json")
    profile = build_provider_profile("ai-memory", repository_root=EXTERNAL_ROOT.parent)
    phase_a = render_phase_prompt(task_pack, scenario, profile, phase="a")
    assert "FFI is future work and unavailable in S3" in phase_a
    assert "current-ffi-boundary-exists" not in phase_a
    assert "repository-state-outranks-stale-memory" not in phase_a
    assert "foreign fn" not in phase_a


def test_task_artifact_validation_rejects_noop_then_accepts_expected_diff(tmp_path: Path) -> None:
    repository = tmp_path / "subject"
    base = _init_repo(repository)
    task = {
        "expected_artifacts": {
            "required_changed": ["bootstrap/s3/numeric.py", "tests/test_numeric_domains.py"],
            "forbidden_changed": ["external-benchmarks/**"],
            "max_changed_files": 4,
        }
    }
    checks = validate_task_artifacts(task, repository_root=repository, base_commit=base)
    assert any(row["id"] == "task-nonempty-change" and not row["passed"] for row in checks)

    (repository / "bootstrap/s3/numeric.py").write_text("after\n", encoding="utf-8")
    (repository / "tests/test_numeric_domains.py").write_text("after\n", encoding="utf-8")
    checks = validate_task_artifacts(task, repository_root=repository, base_commit=base)
    assert all(row["passed"] for row in checks)


def test_agent_report_sidecar_does_not_count_as_task_change(tmp_path: Path) -> None:
    repository = tmp_path / "subject"
    base = _init_repo(repository)
    task = {
        "expected_artifacts": {
            "required_changed": ["bootstrap/s3/numeric.py"],
            "forbidden_changed": [],
            "max_changed_files": 1,
        }
    }
    (repository / "bootstrap/s3/numeric.py").write_text("after\n", encoding="utf-8")
    (repository / ".s3-agent-memory-report.json").write_text(
        '{"schema_version":"1.0.0","reported_invariants":[]}\n',
        encoding="utf-8",
    )
    checks = validate_task_artifacts(task, repository_root=repository, base_commit=base)
    assert all(row["passed"] for row in checks)


def test_task_artifact_validation_keeps_change_budget(tmp_path: Path) -> None:
    repository = tmp_path / "subject"
    base = _init_repo(repository, ("tests/test_numeric_closure.py",))
    task = {
        "expected_artifacts": {
            "required_changed": ["bootstrap/s3/numeric.py"],
            "forbidden_changed": [],
            "max_changed_files": 1,
        }
    }
    (repository / "bootstrap/s3/numeric.py").write_text("after\n", encoding="utf-8")
    (repository / "tests/test_numeric_closure.py").write_text("after\n", encoding="utf-8")
    checks = validate_task_artifacts(task, repository_root=repository, base_commit=base)
    assert any(row["id"] == "task-change-budget" and not row["passed"] for row in checks)


def test_task_artifact_validation_rejects_benchmark_tampering(tmp_path: Path) -> None:
    repository = tmp_path / "subject"
    base = _init_repo(repository)
    task_pack = load_task_pack(EXTERNAL_ROOT / "task-packs" / "agent-memory-v1.json")
    task = task_for_scenario(task_pack, "memory.checked-i64.v1")
    (repository / "bootstrap/s3/numeric.py").write_text("after\n", encoding="utf-8")
    (repository / "tests/test_numeric_domains.py").write_text("after\n", encoding="utf-8")
    (repository / "external-benchmarks").mkdir()
    (repository / "external-benchmarks/cheat.txt").write_text("tamper\n", encoding="utf-8")
    checks = validate_task_artifacts(task, repository_root=repository, base_commit=base)
    assert any(
        row["id"].startswith("task-forbidden:external-benchmarks") and not row["passed"]
        for row in checks
    )


def test_attached_task_failure_forces_scenario_failure() -> None:
    result = {
        "status": "PASS",
        "metrics": {
            "oracle_checks_total": 1,
            "oracle_checks_passed": 1,
            "critical_oracle_failures": 0,
        },
        "oracle": [],
    }
    attach_task_checks(
        result,
        [{"id": "task", "kind": "task_artifact", "passed": False, "detail": "missing"}],
    )
    assert result["status"] == "FAIL"
    assert result["metrics"]["critical_oracle_failures"] == 1
