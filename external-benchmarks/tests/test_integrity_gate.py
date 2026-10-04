from __future__ import annotations

import io
import json
import sys
from pathlib import Path

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = EXTERNAL_ROOT.parent
sys.path.insert(0, str(EXTERNAL_ROOT))

from providers.ai_memory.integrity_gate import (  # noqa: E402
    default_registry_path,
    evaluate_proposal,
    load_registry,
    main,
    validate_registry_evidence,
)


def _proposal(after_body: str, *, before_body: str = "") -> dict[str, object]:
    return {
        "path": "_rules/s3-semantics.md",
        "kind": "rule",
        "operation": "update",
        "edit_mode": "patch",
        "title": "S3 semantics",
        "confidence": 0.95,
        "rationale": "Benchmark fixture",
        "before_body": before_body,
        "after_body": after_body,
        "expected_base_body_sha256": "fixture",
    }


def test_integrity_registry_matches_current_s3_checkout() -> None:
    registry = load_registry(default_registry_path(REPOSITORY_ROOT))

    assert validate_registry_evidence(registry, repository_root=REPOSITORY_ROOT) == []


def test_integrity_gate_allows_explicit_correct_negations() -> None:
    result = evaluate_proposal(
        _proposal(
            """# Current S3 rules

Balanced ternary subtraction does not use TNDIFF.
i64 overflow does not wrap.
&mut does not imply noalias.
Do not use shell=True or os.system().
FFI is not future work; the boundary exists today.
"""
        ),
        repository_root=REPOSITORY_ROOT,
    )

    assert result["passed"] is True
    assert result["score_after"] == 1.0


def test_integrity_gate_rejects_stale_ffi_claim() -> None:
    result = evaluate_proposal(
        _proposal("FFI is future work and should be treated as unavailable."),
        repository_root=REPOSITORY_ROOT,
    )

    assert result["passed"] is False
    assert "ffi-boundary-exists" in str(result["reason"])


def test_integrity_gate_rejects_wrapping_i64_claim() -> None:
    result = evaluate_proposal(
        _proposal("S3 i64 uses wrapping arithmetic for overflow."),
        repository_root=REPOSITORY_ROOT,
    )

    assert result["passed"] is False
    assert "i64-is-checked-not-wrapping" in str(result["reason"])


def test_integrity_gate_rejects_balanced_tndiff_claim() -> None:
    result = evaluate_proposal(
        _proposal("Balanced ternary subtraction uses TNDIFF in the compiler."),
        repository_root=REPOSITORY_ROOT,
    )

    assert result["passed"] is False
    assert "balanced-subtraction-is-not-tndiff" in str(result["reason"])


def test_integrity_gate_rejects_mut_noalias_claim() -> None:
    result = evaluate_proposal(
        _proposal("An &mut reference guarantees machine noalias semantics."),
        repository_root=REPOSITORY_ROOT,
    )

    assert result["passed"] is False
    assert "mut-does-not-imply-noalias" in str(result["reason"])


def test_integrity_gate_rewards_removing_a_contradiction() -> None:
    result = evaluate_proposal(
        _proposal(
            "i64 overflow is checked and fails instead of wrapping.",
            before_body="S3 i64 uses wrapping arithmetic for overflow.",
        ),
        repository_root=REPOSITORY_ROOT,
    )

    assert result["passed"] is True
    assert float(result["score_after"]) > float(result["score_before"])


def test_integrity_gate_fails_closed_when_registry_evidence_is_stale(tmp_path: Path) -> None:
    result = evaluate_proposal(
        _proposal("A harmless proposal."),
        repository_root=tmp_path,
        registry_path=default_registry_path(REPOSITORY_ROOT),
    )

    assert result["passed"] is False
    assert "evidence mismatch" in str(result["reason"])


def test_integrity_gate_stdin_contract_fails_closed_on_invalid_json() -> None:
    stdout = io.StringIO()

    assert main(stdin=io.StringIO("not-json"), stdout=stdout, repository_root=REPOSITORY_ROOT) == 0

    response = json.loads(stdout.getvalue())
    assert response["passed"] is False
    assert "reason" in response
