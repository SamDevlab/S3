"""M2.69 explicit frontend canary and Python fallback contracts."""

from __future__ import annotations

import pytest

import bootstrap.s3.assembly_frontend_canary as canary
from bootstrap.s3.assembly_frontend_canary import (
    FrontendCanaryError,
    FrontendExecutionMode,
    run_assembly_frontend,
)
from bootstrap.s3.assembly_frontend_closure_candidate import (
    AssemblyFrontendClosureEvidence,
)


VALID_ASSEMBLY = ".s3asm 0.6.0\n\n.function main -> [tryte, trit]\n    .register r0, tryte\n    .register r1, trit\n.label entry\n    TCALL  [r0, r1], pair\n    TRET   [r0, r1]\n.end\n"


def test_python_reference_is_the_default_and_does_not_probe_canary(monkeypatch: pytest.MonkeyPatch) -> None:
    def unexpected_probe(_source: str) -> AssemblyFrontendClosureEvidence:
        raise AssertionError("default path must not probe the canary")

    monkeypatch.setattr(canary, "run_assembly_frontend_closure", unexpected_probe)
    result = run_assembly_frontend(VALID_ASSEMBLY)
    assert result.requested_mode is FrontendExecutionMode.PYTHON_REFERENCE
    assert result.selected_mode is FrontendExecutionMode.PYTHON_REFERENCE
    assert result.used_fallback is False
    assert result.candidate_fingerprint is None


def test_explicit_canary_selects_matching_composed_frontend() -> None:
    result = run_assembly_frontend(
        VALID_ASSEMBLY,
        mode=FrontendExecutionMode.S3_CANARY,
    )
    assert result.requested_mode is FrontendExecutionMode.S3_CANARY
    assert result.selected_mode is FrontendExecutionMode.S3_CANARY
    assert result.candidate_selected is True
    assert result.used_fallback is False
    assert result.candidate_fingerprint == result.reference_fingerprint


def test_canary_error_falls_back_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    def failed_probe(_source: str) -> AssemblyFrontendClosureEvidence:
        raise RuntimeError("candidate unavailable")

    monkeypatch.setattr(canary, "run_assembly_frontend_closure", failed_probe)
    result = run_assembly_frontend(VALID_ASSEMBLY, mode="s3-canary")
    assert result.selected_mode is FrontendExecutionMode.PYTHON_REFERENCE
    assert result.used_fallback is True
    assert result.fallback_reason == "candidate_error:RuntimeError"


def test_canary_mismatch_falls_back_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    reference = canary.reference_assembly_frontend_fingerprint(VALID_ASSEMBLY)
    mismatch = AssemblyFrontendClosureEvidence(
        VALID_ASSEMBLY,
        reference,
        reference + 1,
    )
    monkeypatch.setattr(canary, "run_assembly_frontend_closure", lambda _source: mismatch)
    result = run_assembly_frontend(VALID_ASSEMBLY, mode=FrontendExecutionMode.S3_CANARY)
    assert result.selected_mode is FrontendExecutionMode.PYTHON_REFERENCE
    assert result.used_fallback is True
    assert result.candidate_fingerprint == reference + 1
    assert result.fallback_reason == "candidate_differential_mismatch"


def test_unknown_mode_is_rejected() -> None:
    with pytest.raises(FrontendCanaryError, match="unsupported frontend execution mode"):
        run_assembly_frontend(VALID_ASSEMBLY, mode="unexpected")
