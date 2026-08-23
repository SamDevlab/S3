"""M2.65 bounded diagnostic recovery candidate contracts."""

from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.diagnostic_candidate import (
    DiagnosticCandidateError,
    candidate_diagnostic_fingerprint,
    diagnostic_code_for_source,
    reference_diagnostic_fingerprint,
    run_diagnostic_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (ROOT / "selfhost/frontend/diagnostic_candidate.s3").read_text(
    encoding="utf-8"
)


def test_candidate_source_is_s3_authored_and_closed() -> None:
    assert "fn diagnostic_recovery_contract" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


@pytest.mark.parametrize("code", [1, 2, 3, 4, 5, 6])
def test_candidate_matches_reference_recovery_contract(code: int) -> None:
    evidence = run_diagnostic_differential(code)
    assert evidence.reference_fingerprint == reference_diagnostic_fingerprint(code)
    assert evidence.candidate_fingerprint == candidate_diagnostic_fingerprint(code)
    assert evidence.match is True


def test_invalid_character_source_uses_lexical_recovery() -> None:
    code = diagnostic_code_for_source("@")
    assert code == 1
    assert candidate_diagnostic_fingerprint(code) == reference_diagnostic_fingerprint(code)


def test_candidate_rejects_unknown_diagnostic_code() -> None:
    with pytest.raises(DiagnosticCandidateError, match="rejected"):
        candidate_diagnostic_fingerprint(7)
