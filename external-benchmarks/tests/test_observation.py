from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTERNAL_ROOT))

from harness.core import ExternalBenchmarkError  # noqa: E402
from harness.observation import materialize_observation  # noqa: E402


def _plan(mode: str, *, stale_claim_id: str | None = None) -> dict[str, object]:
    scenario: dict[str, object] = {
        "scenario_id": "scenario",
        "mode": mode,
        "template": "fixture.json",
        "worktree_key": "fixture",
        "observation_path": "fixture.observation.json",
        "result_path": "fixture.json",
        "required_evidence": [],
    }
    if stale_claim_id is not None:
        scenario["stale_claim_id"] = stale_claim_id
    return {
        "provider": {"id": "ai-memory", "version": "2.x"},
        "agent": {"provider": "openai", "model": "fixture", "harness": "codex"},
        "execution": {
            "s3_commit": "abc123",
            "agent_harness_version": "1",
            "tool_permissions_profile": "standard",
            "task_protocol_version": "agent-memory-v1",
            "repetition": 1,
        },
        "scenarios": [scenario],
    }


def test_single_session_observation_copies_controlled_metadata() -> None:
    observation = materialize_observation(
        _plan("single-session"),
        scenario_id="scenario",
        reported_invariants=("b", "a", "a"),
    )

    assert observation["provider"] == {"id": "ai-memory", "version": "2.x"}
    assert observation["reported_invariants"] == ["a", "b"]
    assert observation["execution"]["s3_commit"] == "abc123"
    assert "handoff" not in observation


def test_cross_session_defaults_to_same_agent_identity_without_transcript_reuse() -> None:
    observation = materialize_observation(
        _plan("cross-session"),
        scenario_id="scenario",
    )

    assert observation["handoff"]["kind"] == "cross-session"
    assert observation["handoff"]["transcript_reused"] is False
    assert observation["handoff"]["source_agent"] == observation["handoff"]["target_agent"]


def test_cross_agent_requires_distinct_explicit_identities() -> None:
    with pytest.raises(ExternalBenchmarkError, match="requires source and target"):
        materialize_observation(_plan("cross-agent"), scenario_id="scenario")

    source = {"provider": "openai", "model": "a", "harness": "codex", "secret": "drop"}
    target = {"provider": "openai", "model": "b", "harness": "codex"}
    observation = materialize_observation(
        _plan("cross-agent"),
        scenario_id="scenario",
        source_agent=source,
        target_agent=target,
    )

    assert observation["handoff"]["source_agent"] == {
        "provider": "openai",
        "model": "a",
        "harness": "codex",
    }
    assert "secret" not in json.dumps(observation)


def test_stale_memory_observation_uses_normative_claim_id() -> None:
    observation = materialize_observation(
        _plan("stale-memory", stale_claim_id="ffi-is-future-work"),
        scenario_id="scenario",
    )

    assert observation["stale_memory"] == {
        "claim_id": "ffi-is-future-work",
        "injected": True,
    }
