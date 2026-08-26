from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.audit_stage1_codegen_fixture_opcode_coverage import audit


pytestmark = pytest.mark.s3_fast


def _load(path: str) -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    return json.loads((root / path).read_text(encoding="utf-8"))


def _reference(*opcodes: str) -> dict[str, object]:
    return {
        "schema": "s3.selfhost.reference-bootstrap-opcode-inventory.v1",
        "reference_ir": {"observed_opcodes": list(opcodes)},
    }


def test_existing_fixture_corpus_covers_basic_const_and_return() -> None:
    fixtures = _load("tests/stage1_codegen_complete_fixtures.json")
    contract = _load("reports/selfhost/stage1/reference-bootstrap-opcode-contract.json")
    result = audit(fixtures, _reference("const", "return"), contract)
    assert result["status"] == "PASS_HOSTED_FIXTURE_OPCODE_COVERAGE"
    assert result["missing_required_opcodes"] == []
    assert result["qualification"]["native_fixture_execution"] == "NOT_RUN_BY_THIS_TOOL"
    assert result["qualification"]["stage2_allowed"] is False


def test_missing_reference_opcode_blocks_hosted_fixture_coverage() -> None:
    fixtures = _load("tests/stage1_codegen_complete_fixtures.json")
    contract = _load("reports/selfhost/stage1/reference-bootstrap-opcode-contract.json")
    # Current bootstrap-complete fixtures deliberately do not exercise
    # reference_store.  If the canonical compiler later requires it, the
    # fixture suite must grow before Stage1 certification.
    result = audit(fixtures, _reference("const", "return", "reference_store"), contract)
    assert result["status"] == "BLOCKED_FIXTURE_OPCODE_COVERAGE_GAP"
    assert "reference_store" in result["missing_required_opcodes"]
    assert "REFERENCE_STORE" in result["missing_required_capabilities"]
    assert result["qualification"]["next"] == "ADD_MINIMAL_NATIVE_FIXTURES_FOR_MISSING_BOOTSTRAP_OPCODES"


def test_unknown_required_opcode_fails_closed_as_unmapped() -> None:
    fixtures = _load("tests/stage1_codegen_complete_fixtures.json")
    contract = _load("reports/selfhost/stage1/reference-bootstrap-opcode-contract.json")
    result = audit(fixtures, _reference("const", "return", "future_opcode"), contract)
    assert result["status"] == "BLOCKED_FIXTURE_OPCODE_COVERAGE_GAP"
    assert "future_opcode" in result["unmapped_required_opcodes"]
    assert result["qualification"]["stage1_certified_for_stage2"] is False
