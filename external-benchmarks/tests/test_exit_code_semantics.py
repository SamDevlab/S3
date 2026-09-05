from __future__ import annotations

import sys
from pathlib import Path

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.core import evaluate_scenario  # noqa: E402
from harness.execution import EXECUTION_PROTOCOL_VERSION  # noqa: E402
from harness.task_pack import attach_task_checks  # noqa: E402


def _scenario(*, semantic_pass: bool = True) -> dict[str, object]:
    oracle = {
        "required_patterns": (
            [{"id": "required", "glob": "src/**/*.py", "pattern": "safe_call"}]
            if semantic_pass
            else [{"id": "required", "glob": "src/**/*.py", "pattern": "missing"}]
        )
    }
    return {
        "schema_version": "1.0.0",
        "scenario_id": "memory.regression.v1",
        "version": "1.0.0",
        "category": "agent-memory",
        "objective": "exit code regression",
        "critical_invariants": [],
        "oracle": oracle,
    }


def _phase(phase: str, returncode: int = 0, *, timed_out: bool = False) -> dict[str, object]:
    return {
        "phase": phase,
        "agent": {"provider": "openai", "model": "fixture", "harness": "codex"},
        "runner": "direct",
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_seconds": 1.0,
    }


def _observation(
    phases: list[dict[str, object]] | None = None,
    *,
    include_process: bool = True,
) -> dict[str, object]:
    observation: dict[str, object] = {
        "provider": {"id": "fixture", "version": "1"},
        "agent": {"provider": "openai", "model": "fixture", "harness": "codex"},
        "execution": {
            "s3_commit": "a" * 40,
            "agent_harness_version": "0.153.1",
            "tool_permissions_profile": "windows-danger-full-access-v1",
            "task_protocol_version": "agent-memory-v1",
            "execution_protocol_version": EXECUTION_PROTOCOL_VERSION,
            "repetition": 1,
        },
        "reported_invariants": [],
    }
    if include_process:
        observation["agent_process"] = {
            "phases": phases or [_phase("single-session")],
            "required_processes": len(phases or [_phase("single-session")]),
        }
    return observation


def _evaluate(
    tmp_path: Path,
    *,
    phases: list[dict[str, object]] | None = None,
    semantic_pass: bool = True,
    include_process: bool = True,
) -> dict[str, object]:
    source = tmp_path / "src" / "module.py"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("def safe_call():\n    return 1\n", encoding="utf-8")
    return evaluate_scenario(
        _scenario(semantic_pass=semantic_pass),
        _observation(phases, include_process=include_process),
        repository_root=tmp_path,
    )


def test_agent_zero_semantic_pass_task_pass_is_valid_pass(tmp_path: Path) -> None:
    result = _evaluate(tmp_path)
    assert result["status"] == "VALID_PASS"
    assert result["dimensions"]["agent_process"]["status"] == "PASS"  # type: ignore[index]
    assert result["dimensions"]["semantic_oracle"]["status"] == "PASS"  # type: ignore[index]
    assert result["dimensions"]["task_artifact"]["status"] == "PASS"  # type: ignore[index]

def test_nonzero_agent_exit_fails_even_when_oracle_and_artifact_pass(tmp_path: Path) -> None:
    result = _evaluate(tmp_path, phases=[_phase("phase-b", 1)])
    assert result["status"] == "VALID_FAIL"
    assert result["dimensions"]["agent_process"]["status"] == "FAIL"  # type: ignore[index]
    assert result["dimensions"]["semantic_oracle"]["status"] == "PASS"  # type: ignore[index]
    assert result["dimensions"]["task_artifact"]["status"] == "PASS"  # type: ignore[index]


def test_phase_b_nonzero_exit_fails_two_phase_run(tmp_path: Path) -> None:
    result = _evaluate(tmp_path, phases=[_phase("phase-a"), _phase("phase-b", 1)])
    assert result["status"] == "VALID_FAIL"


def test_phase_a_nonzero_exit_is_not_hidden_by_phase_b_success(tmp_path: Path) -> None:
    result = _evaluate(tmp_path, phases=[_phase("phase-a", 1), _phase("phase-b")])
    assert result["status"] == "VALID_FAIL"
    assert result["dimensions"]["agent_process"]["nonzero_exits"] == [  # type: ignore[index]
        {"phase": "phase-a", "returncode": 1}
    ]


def test_semantic_failure_is_separate_and_fails_overall(tmp_path: Path) -> None:
    result = _evaluate(tmp_path, semantic_pass=False)
    assert result["status"] == "VALID_FAIL"
    assert result["dimensions"]["agent_process"]["status"] == "PASS"  # type: ignore[index]
    assert result["dimensions"]["semantic_oracle"]["status"] == "FAIL"  # type: ignore[index]


def test_task_artifact_failure_is_separate_and_fails_overall(tmp_path: Path) -> None:
    result = _evaluate(tmp_path)
    attach_task_checks(
        result,
        [{"id": "task-required:missing.py", "kind": "task_artifact", "passed": False, "detail": "missing"}],
    )
    assert result["status"] == "VALID_FAIL"
    assert result["dimensions"]["agent_process"]["status"] == "PASS"  # type: ignore[index]
    assert result["dimensions"]["task_artifact"]["status"] == "FAIL"  # type: ignore[index]


def test_timeout_is_invalid_operational_run_not_valid_fail(tmp_path: Path) -> None:
    result = _evaluate(tmp_path, phases=[_phase("phase-b", 124, timed_out=True)])
    assert result["status"] == "INVALID_OPERATIONAL_RUN"
    assert result["dimensions"]["agent_process"]["status"] == "INVALID_OPERATIONAL_RUN"  # type: ignore[index]


def test_missing_required_execution_evidence_fails_closed(tmp_path: Path) -> None:
    result = _evaluate(tmp_path, include_process=False)
    assert result["status"] == "INVALID_EXECUTION_EVIDENCE"
    assert result["dimensions"]["agent_process"]["status"] == "INVALID_EXECUTION_EVIDENCE"  # type: ignore[index]


def test_auxiliary_nonzero_is_not_agent_process_failure(tmp_path: Path) -> None:
    result = _evaluate(tmp_path)
    result["auxiliary_commands"] = [{"id": "pytest", "returncode": 1}]
    assert result["status"] == "VALID_PASS"
    assert result["dimensions"]["agent_process"]["status"] == "PASS"  # type: ignore[index]


def test_historical_stale_memory_shape_cannot_become_pass(tmp_path: Path) -> None:
    result = _evaluate(tmp_path, phases=[_phase("phase-b", 1)])
    assert result["status"] != "PASS"
    assert result["status"] == "VALID_FAIL"
    assert result["dimensions"]["semantic_oracle"]["status"] == "PASS"  # type: ignore[index]
    assert result["dimensions"]["task_artifact"]["status"] == "PASS"  # type: ignore[index]
