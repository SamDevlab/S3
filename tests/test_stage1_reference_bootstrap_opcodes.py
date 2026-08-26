from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from bootstrap.s3.ir import IROpcode
import tools.audit_stage1_reference_bootstrap_opcodes as oracle


pytestmark = pytest.mark.s3_fast


def _load(name: str) -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    return json.loads(
        (root / "reports" / "selfhost" / "stage1" / name).read_text(
            encoding="utf-8"
        )
    )


def test_contract_maps_every_current_reference_ir_opcode() -> None:
    contract = _load("reference-bootstrap-opcode-contract.json")
    capabilities = contract["opcode_capabilities"]
    assert set(capabilities) == {opcode.value for opcode in IROpcode}
    assert contract["rules"]["stage2_allowed_from_this_report"] is False
    assert contract["rules"]["native_stage1_evidence_required_for_final_pass"] is True


def test_reference_convert_rejects_historical_cast_zero_claim(monkeypatch) -> None:
    contract = _load("reference-bootstrap-opcode-contract.json")
    legacy = _load("general-emitter-required-ops.json")
    source = (
        "fn id(value: i64) -> i64:\n"
        "    return value\n\n"
        "fn main() -> tryte:\n"
        "    mut values: i64[2] = [1, 2]\n"
        "    values[0] = id(values[1])\n"
        "    return to_tryte(values[0])\n"
    ).encode("utf-8")

    monkeypatch.setattr(
        oracle,
        "_canonical_source",
        lambda _path: (
            Path("/tmp/reference-opcode-fixture.s3"),
            source,
            {
                "schema": "s3.compiler.sources.v1",
                "source_count": 1,
                "total_bytes": len(source),
            },
        ),
    )
    result = oracle.audit(contract, copy.deepcopy(legacy), Path("unused.json"))
    assert result["status"] == "BLOCKED_LEGACY_EMITTER_REQUIREMENTS_STALE"
    assert result["reference_ir"]["opcode_histogram"]["convert"] > 0
    conflicts = result["reconciliation"]["historical_zero_count_conflicts"]
    assert any(
        item["opcode"] == "convert"
        and item["historical_shape"] == "CAST"
        and item["historical_count"] == 0
        for item in conflicts
    )
    assert result["qualification"]["stage2_allowed"] is False
    assert result["qualification"]["general_emitter_certified"] is False


def test_reference_oracle_never_treats_physical_stage0_shape_as_stage1_authority() -> None:
    contract = _load("reference-bootstrap-opcode-contract.json")
    assert contract["rules"]["reference_ir_shape_is_not_stage1_physical_encoding_authority"] is True
