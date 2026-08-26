from __future__ import annotations

import hashlib

from tools.audit_stage1_checkpoint_consistency import audit


def test_current_source_can_coexist_with_historical_handoffs() -> None:
    source = b"fn main() -> tryte:\n    return 0\n"
    source_sha = hashlib.sha256(source).hexdigest()
    result = audit(
        source_bytes=source,
        requirements={"source": {"sha256": source_sha, "bytes": len(source)}},
        final_report="CANONICAL_SOURCE_SHA256=" + "0" * 64,
        handoff="CANONICAL_SOURCE_SHA256=" + "1" * 64,
        blocker="CURRENT_SOURCE_SHA256=" + source_sha,
    )

    assert result["status"] == "CURRENT_CHECKPOINT_IDENTIFIED_HISTORICAL_HANDOFFS_PRESENT"
    assert result["semantic_requirements_source"]["matches_current"] is True
    assert set(result["historical_or_stale_handoffs"]) == {
        "FINAL_STAGE1_REPORT.md",
        "FINAL_AUTONOMOUS_HANDOFF.txt",
    }


def test_missing_current_blocker_reference_requires_reconciliation() -> None:
    source = b"source"
    source_sha = hashlib.sha256(source).hexdigest()
    result = audit(
        source_bytes=source,
        requirements={"source": {"sha256": source_sha, "bytes": len(source)}},
        final_report=source_sha,
        handoff=source_sha,
        blocker="historical only " + "2" * 64,
    )

    assert result["status"] == "CURRENT_CHECKPOINT_PROVENANCE_RECONCILIATION_REQUIRED"
    assert result["guards"]["general_blocker_contains_current_sha"] is False
