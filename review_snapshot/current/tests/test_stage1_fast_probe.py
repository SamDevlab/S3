"""Focused contracts for the compile-once Stage1 probe harness."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import tools.stage1_fast_probe as fast_probe


MILESTONE_SOURCE = (
    b"fn alpha() -> i64:\n"
    b"    return 1\n"
    b"fn beta() -> i64:\n"
    b"    return 2\n"
    b"fn gamma() -> i64:\n"
    b"    return 3\n"
)


def test_record_counts_uses_the_complete_v3_record_alphabet() -> None:
    records = {kind: [(1,)] for kind in "FBDVMICRAOTZ"}
    assert fast_probe._record_counts(records) == {
        kind: 1 for kind in "FBDVMICRAOTZ"
    }


def test_candidate_cache_is_keyed_by_source_optimization_and_mode(
    tmp_path: Path, monkeypatch
) -> None:
    first_path = tmp_path / "first.s3"
    second_path = tmp_path / "second.s3"
    first_path.write_bytes(b"same source")
    second_path.write_bytes(b"same source")
    calls: list[tuple[Path, str, object]] = []

    class FakeCandidate:
        def __init__(self, path, optimization, *, mode):
            calls.append((path, optimization, mode))

    monkeypatch.setattr(fast_probe, "Stage1Candidate", FakeCandidate)
    fast_probe.clear_candidate_cache()

    first_key = fast_probe.candidate_cache_key(first_path)
    second_key = fast_probe.candidate_cache_key(second_path)
    assert first_key.source_sha256 == sha256(b"same source").hexdigest()
    assert first_key == second_key
    assert first_key.optimization == "O0"

    first = fast_probe.get_cached_candidate(first_path)
    reused = fast_probe.get_cached_candidate(second_path)
    different_optimization = fast_probe.get_cached_candidate(second_path, "O1")

    assert first is reused
    assert different_optimization is not first
    assert len(calls) == 2
    assert fast_probe.candidate_cache_size() == 2


def test_fixture_set_covers_simple_mutable_call_and_nested_control() -> None:
    fixtures = fast_probe._fixture_sources()
    assert tuple(fixtures) == (
        "smoke",
        "mutable",
        "call",
        "match",
        "nested-match-while",
    )
    assert all(isinstance(source, bytes) and source for source in fixtures.values())


def test_real_candidate_reuse_has_fresh_execution_state_and_stable_ir() -> None:
    candidate = fast_probe.get_cached_candidate()
    first, _ = candidate.run_stream(fast_probe._fixture_sources()["smoke"])
    first_runtime = candidate.last_resource_runtime
    first_output = candidate.last_output_buffer
    first_error = candidate.last_error_buffer
    first_hook = candidate.last_io_hook

    second, _ = candidate.run_stream(fast_probe._fixture_sources()["smoke"])

    assert first == second
    assert candidate.last_ir_digest_before == candidate.last_ir_digest_after
    assert first_runtime is not candidate.last_resource_runtime
    assert first_output is not candidate.last_output_buffer
    assert first_error is not candidate.last_error_buffer
    assert first_hook is not candidate.last_io_hook


def test_milestone_mode_stops_at_target_and_default_mode_reaches_full_source() -> None:
    candidate = fast_probe.get_cached_candidate()

    milestone, _ = candidate.run_stream(MILESTONE_SOURCE, stop_after_f=2)
    assert len(milestone["F"]) == 2
    assert candidate.last_run_metadata["milestone_reached"] is True
    assert candidate.last_run_metadata["partial_stream"] is True
    assert candidate.last_run_metadata["qualification_complete"] is False
    assert len(candidate.last_run_metadata["function_emission_elapsed_seconds"]) == 2

    qualified, _ = candidate.run_stream(MILESTONE_SOURCE)
    assert len(qualified["F"]) == 3
    assert candidate.last_run_metadata["milestone_reached"] is False
    assert candidate.last_run_metadata["partial_stream"] is False
    assert candidate.last_run_metadata["qualification_complete"] is True


def test_milestone_cli_contract_and_progress_keep_semantic_output_separate(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    candidate = fast_probe.get_cached_candidate()
    source_path = tmp_path / "milestone.s3"
    source_path.write_bytes(MILESTONE_SOURCE)
    monkeypatch.setattr(
        fast_probe,
        "get_cached_candidate",
        lambda *args, **kwargs: candidate,
    )

    assert (
        fast_probe.main(
            [
                "--source",
                str(source_path),
                "--stop-after-f",
                "2",
                "--progress-functions",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert payload["PROBE_MODE"] == "MILESTONE"
    assert payload["CANDIDATE_SHA"] == candidate.source_sha256
    assert payload["CANONICAL_SHA"] == ""
    assert payload["TARGET_F"] == 2
    assert payload["F_OBSERVED"] == 2
    assert payload["MILESTONE_REACHED"] == "YES"
    assert payload["PARTIAL_STREAM"] == "YES"
    assert payload["QUALIFICATION_COMPLETE"] == "NO"
    assert payload["LAST_FUNCTION_NAME"] == "beta"
    assert captured.err.splitlines() == [
        line for line in captured.err.splitlines() if line.startswith("[stage1] F=")
    ]
    assert [line.split()[1] for line in captured.err.splitlines()] == ["F=1", "F=2"]

    default, _ = candidate.run_stream(MILESTONE_SOURCE)
    progress, _ = candidate.run_stream(MILESTONE_SOURCE, progress_functions=True)
    assert default == progress
    capsys.readouterr()
