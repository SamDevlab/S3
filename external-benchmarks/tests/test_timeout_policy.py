from __future__ import annotations

import sys
from pathlib import Path

import pytest

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.core import ExternalBenchmarkError  # noqa: E402
from harness.timeout_policy import (  # noqa: E402
    TIMEOUT_EXIT_CODE,
    TIMEOUT_POLICY_ID,
    TIMEOUT_SECONDS,
    TimeoutPolicy,
    load_timeout_policy,
    run_controlled_process,
)


def test_frozen_timeout_policy_is_versioned_and_fixed() -> None:
    policy = load_timeout_policy()
    assert policy.policy_id == TIMEOUT_POLICY_ID
    assert policy.timeout_seconds == TIMEOUT_SECONDS
    assert policy.on_timeout == "INVALID_OPERATIONAL_RUN"
    assert policy.dynamic_adjustment is False


def test_controlled_process_returns_timeout_exit_code_and_kills_tree(tmp_path: Path) -> None:
    policy = TimeoutPolicy(
        policy_id=TIMEOUT_POLICY_ID,
        timeout_seconds=0.05,
        on_timeout="INVALID_OPERATIONAL_RUN",
        dynamic_adjustment=False,
    )
    result = run_controlled_process(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        cwd=tmp_path,
        policy=policy,
    )
    assert result.returncode == TIMEOUT_EXIT_CODE
    assert result.timed_out is True
    assert result.elapsed_seconds < 1


def test_policy_loader_rejects_modified_timeout(tmp_path: Path) -> None:
    path = tmp_path / "policy.json"
    path.write_text(
        '{"schema_version":"1.0.0","policy_id":"windows-agent-memory-timeout-v1",'
        '"scope":"agent-memory-v1","platform":"windows","timeout_seconds":900,'
        '"unit":"seconds","applies_to":"each controlled process or phase",'
        '"on_timeout":"INVALID_OPERATIONAL_RUN","dynamic_adjustment":false}',
        encoding="utf-8",
    )
    with pytest.raises(ExternalBenchmarkError, match="1800"):
        load_timeout_policy(path)
