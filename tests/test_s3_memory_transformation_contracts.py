from __future__ import annotations

import json
from pathlib import Path


def test_memory_transformation_contracts_are_explicit_and_research_only() -> None:
    path = (
        Path(__file__).resolve().parents[1]
        / "reports/s3-1.10-memory-intelligence-value-locality/TRANSFORMATION_CONTRACTS.json"
    )
    document = json.loads(path.read_text(encoding="utf-8"))

    assert document["schema_version"] == "1.0.0"
    assert document["pipeline_effect"] == "NONE_RESEARCH_ONLY"
    contracts = document["contracts"]
    assert {item["id"] for item in contracts} == {
        "EXP-S3-110-STORE-LOAD-001",
        "EXP-S3-110-LOAD-001",
        "EXP-S3-110-LOAD-SSA-001",
    }
    assert len({item["id"] for item in contracts}) == len(contracts)
    for contract in contracts:
        assert contract["status"] == "RESEARCH_ONLY"
        assert contract["production_default"] is False
        assert contract["required_facts"]
        assert contract["proof_checks"]
        assert contract["rewrite"]
        assert contract["postconditions"]
        assert "KEEP_BASELINE_IR" in contract["fallback"]
