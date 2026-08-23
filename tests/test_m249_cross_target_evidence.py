"""M2.49 cross-target evidence classification contracts."""

from __future__ import annotations

import pytest

from bootstrap.s3.cross_target_evidence import (
    CrossTargetEvidenceError,
    CrossTargetObservation,
    EvidenceClass,
    analyze_cross_target_evidence,
    classify_target_observation,
)


def _observation(target: str, mode: str, **changes: object) -> CrossTargetObservation:
    values: dict[str, object] = {
        "target": target,
        "execution_mode": mode,
        "target_host_match": mode == "NATIVE",
        "correctness": "PASS",
        "structural": "PASS",
    }
    values.update(changes)
    return CrossTargetObservation(**values)


def test_native_execution_requires_matching_target_host() -> None:
    evidence = classify_target_observation(
        _observation("linux-x86-64", "NATIVE", target_host_match=True)
    )
    assert evidence.classification is EvidenceClass.NATIVE

    deferred = classify_target_observation(
        _observation("linux-x86-64", "NATIVE", target_host_match=False)
    )
    assert deferred.classification is EvidenceClass.DEFERRED
    assert deferred.reason == "native_target_host_mismatch"


def test_structural_output_never_becomes_native() -> None:
    evidence = classify_target_observation(
        _observation("linux-aarch64", "STRUCTURAL_ONLY")
    )
    assert evidence.classification is EvidenceClass.STRUCTURAL_ONLY
    assert evidence.reason == "artifact_structure_verified_without_native_execution"


def test_emulated_execution_is_distinct_from_native() -> None:
    evidence = classify_target_observation(
        _observation("macos-arm64", "EMULATED", target_host_match=False)
    )
    assert evidence.classification is EvidenceClass.EMULATED
    assert evidence.classification is not EvidenceClass.NATIVE


def test_failed_execution_evidence_is_deferred() -> None:
    evidence = classify_target_observation(
        _observation("linux-aarch64", "NATIVE", correctness="FAIL")
    )
    assert evidence.classification is EvidenceClass.DEFERRED


def test_report_contains_missing_targets_as_deferred() -> None:
    report = analyze_cross_target_evidence(
        [_observation("linux-x86-64", "NATIVE")]
    )
    assert [entry["target"] for entry in report["targets"]] == [
        "linux-x86-64",
        "linux-aarch64",
        "macos-arm64",
    ]
    assert report["counts"]["NATIVE"] == 1
    assert report["counts"]["DEFERRED"] == 2
    assert report["structural_output_is_native"] is False


def test_report_is_deterministic_independent_of_input_order() -> None:
    observations = [
        _observation("macos-arm64", "EMULATED"),
        _observation("linux-aarch64", "STRUCTURAL_ONLY"),
    ]
    first = analyze_cross_target_evidence(observations)
    second = analyze_cross_target_evidence(reversed(observations))
    assert first == second


def test_duplicate_target_evidence_fails() -> None:
    with pytest.raises(CrossTargetEvidenceError, match="duplicate target"):
        analyze_cross_target_evidence(
            [_observation("linux-x86-64", "NATIVE"), _observation("linux-x86-64", "NATIVE")]
        )


def test_unknown_target_fails() -> None:
    with pytest.raises(CrossTargetEvidenceError, match="unsupported target"):
        classify_target_observation(_observation("windows-x86-64", "NATIVE"))

