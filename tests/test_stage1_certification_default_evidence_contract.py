from __future__ import annotations

import json

import pytest

from tools.emit_stage1_certification_gate import (
    DEFAULT_CONTRACT,
    DEFAULT_EVIDENCE_PATHS,
)


pytestmark = pytest.mark.s3_fast


def test_default_evidence_roles_exactly_match_current_contract() -> None:
    contract = json.loads(DEFAULT_CONTRACT.read_text(encoding="utf-8"))
    roles = contract["required_evidence_roles"]
    assert isinstance(roles, dict)
    assert set(DEFAULT_EVIDENCE_PATHS) == set(roles)


def test_default_semantic_ir_is_native_call_bound() -> None:
    semantic_path = DEFAULT_EVIDENCE_PATHS["final_semantic_ir_verifier"]
    assert semantic_path.endswith("stage1-final-semantic-ir-verifier-call-bound.json")
    assert "native_call_reconciliation" in DEFAULT_EVIDENCE_PATHS
    assert "representation_epoch" in DEFAULT_EVIDENCE_PATHS
    assert "reference_current_call_inventory" in DEFAULT_EVIDENCE_PATHS
