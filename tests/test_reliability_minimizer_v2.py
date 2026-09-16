from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.reliability_contract_v2 import canonical_json_document, sha256_hex
from tools.reliability_minimizer_v2 import (
    MinimizationObservation,
    minimize_failure,
    minimize_source,
)
from tools.reliability_triage_v2 import minimize_replay_bundle


pytestmark = pytest.mark.s3_contract


def _stable_failure(source: bytes) -> MinimizationObservation:
    if b"TRIGGER" in source:
        return MinimizationObservation("MISCOMPILE", "miscompile:synthetic-trigger")
    return MinimizationObservation("PASS", None)


def test_reducer_finds_smaller_deterministic_source() -> None:
    source = b"discard-one\nTRIGGER\ndiscard-two\n"
    first = minimize_source(
        source,
        _stable_failure,
        expected_outcome="MISCOMPILE",
        expected_failure_signature="miscompile:synthetic-trigger",
    )
    second = minimize_source(
        source,
        _stable_failure,
        expected_outcome="MISCOMPILE",
        expected_failure_signature="miscompile:synthetic-trigger",
    )

    assert first.minimized_source == b"TRIGGER"
    assert first.minimized_source == second.minimized_source
    assert first.to_dict() == second.to_dict()
    assert first.minimized_bytes < first.initial_bytes
    assert first.minimized_lines < first.initial_lines
    assert first.accepted_reductions > 0
    assert first.evaluations <= 10_000


def test_reducer_preserves_exact_failure_signature_not_only_outcome() -> None:
    source = b"noise\nTRIGGER\nTARGET\n"

    def evaluator(candidate: bytes) -> MinimizationObservation:
        if b"TRIGGER" not in candidate:
            return MinimizationObservation("PASS", None)
        if b"TARGET" in candidate:
            return MinimizationObservation("MISCOMPILE", "miscompile:target")
        return MinimizationObservation("MISCOMPILE", "miscompile:other")

    result = minimize_source(
        source,
        evaluator,
        expected_outcome="MISCOMPILE",
        expected_failure_signature="miscompile:target",
    )
    assert result.minimized_source == b"TRIGGERTARGET"
    assert b"TARGET" in result.minimized_source
    assert result.expected_failure_signature == "miscompile:target"


def test_reducer_is_bounded_and_reports_budget_exhaustion() -> None:
    result = minimize_source(
        b"TRIGGER\nextra\n",
        _stable_failure,
        expected_outcome="MISCOMPILE",
        expected_failure_signature="miscompile:synthetic-trigger",
        max_evaluations=1,
    )
    assert result.evaluations == 1
    assert result.budget_exhausted is True
    assert result.minimized_source == b"TRIGGER\nextra\n"


def test_reducer_rejects_initial_identity_mismatch() -> None:
    with pytest.raises(ValueError, match="does not reproduce"):
        minimize_source(
            b"no failure\n",
            _stable_failure,
            expected_outcome="MISCOMPILE",
            expected_failure_signature="miscompile:synthetic-trigger",
        )


def test_minimize_failure_rejects_non_failure_outcomes() -> None:
    with pytest.raises(ValueError, match="failure outcome"):
        minimize_failure(
            b"source",
            lambda source: ("PASS", None),
            expected_outcome="PASS",
            expected_failure_signature=None,
        )


def test_replay_minimization_verifies_hashes_and_preserves_original(tmp_path: Path) -> None:
    bundle = tmp_path / "case"
    bundle.mkdir()
    case_id = "a" * 64
    head = "b" * 40
    source = b"noise\nTRIGGER\n"
    metadata = {"case_id": case_id, "source_sha256": sha256_hex(source)}
    result = {
        "schema": "s3.reliability.differential-case.v1",
        "case_id": case_id,
        "outcome": "MISCOMPILE",
        "failure_signature": "miscompile:synthetic-trigger",
    }
    (bundle / "input.s3").write_bytes(source)
    metadata_bytes = canonical_json_document(metadata)
    result_bytes = canonical_json_document(result)
    (bundle / "metadata.json").write_bytes(metadata_bytes)
    (bundle / "result.json").write_bytes(result_bytes)
    manifest = {
        "schema": "s3.reliability.replay.v2",
        "replay_version": "s3.reliability.replay.v2-r3",
        "case_id": case_id,
        "compiler_head": head,
        "source_path": "input.s3",
        "source_sha256": sha256_hex(source),
        "metadata_path": "metadata.json",
        "metadata_sha256": sha256_hex(metadata_bytes),
        "result_path": "result.json",
        "result_sha256": sha256_hex(result_bytes),
        "expected_failure_signature": "miscompile:synthetic-trigger",
    }
    (bundle / "replay.json").write_bytes(canonical_json_document(manifest))

    output = tmp_path / "reduced"
    minimized = minimize_replay_bundle(bundle, _stable_failure, output_dir=output)

    assert (bundle / "input.s3").read_bytes() == source
    assert (output / "input.s3").read_bytes() == b"TRIGGER"
    evidence = json.loads((output / "minimization.json").read_text(encoding="utf-8"))
    assert evidence["case_id"] == case_id
    assert evidence["compiler_head"] == head
    assert evidence["replay_source_sha256"] == sha256_hex(source)
    assert minimized.minimization.minimized_source == b"TRIGGER"


def test_replay_minimization_rejects_escaping_artifact_path(tmp_path: Path) -> None:
    bundle = tmp_path / "case"
    bundle.mkdir()
    (bundle / "replay.json").write_bytes(
        canonical_json_document(
            {
                "schema": "s3.reliability.replay.v2",
                "source_path": "../input.s3",
            }
        )
    )
    with pytest.raises(ValueError, match="normalized relative"):
        minimize_replay_bundle(bundle, _stable_failure)
