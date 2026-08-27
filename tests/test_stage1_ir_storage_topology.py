from __future__ import annotations

from tools.audit_stage1_ir_storage_topology import (
    COMPACT_BLOCK_CAPACITY,
    audit,
)


def _requirements() -> dict[str, object]:
    return {
        "reference_typed_ir": {
            "status": "MEASURED_HOST_IR_ORACLE_NOT_STAGE1_EVIDENCE",
            "blocks": 2987,
            "max_blocks_per_function": 2175,
            "instructions": 49128,
            "max_instructions_per_function": 45000,
            "registers": 32700,
            "instruction_results": 32630,
            "max_registers_per_function": 29640,
            "memory_objects": 560,
        }
    }


def _value_contract() -> dict[str, object]:
    return {
        "physical_storage": {
            "physical_slots": 1460,
            "silent_reinterpretation_allowed": False,
        }
    }


def test_large_host_oracle_selects_streaming_without_calling_blocks_overflow() -> None:
    result = audit(_requirements(), _value_contract())
    assert result["status"] == "STATIC_IR_STORAGE_TOPOLOGY_PASS"
    assert result["storage"]["blocks"]["classification"] == "REPRESENTATION_NOT_COMPARABLE"
    assert result["storage"]["instructions"]["classification"] == "STREAM_OR_REUSE_REQUIRED"
    assert result["storage"]["semantic_values"]["classification"] == "STREAM_OR_REUSE_REQUIRED"
    assert result["native_evidence"] is False


def test_stage1_structural_measurement_is_checked_only_against_stage1_capacity() -> None:
    result = audit(
        _requirements(),
        _value_contract(),
        stage1_structural_blocks=1334,
    )
    blocks = result["storage"]["blocks"]
    assert blocks["stage1_capacity_fits_measurement"] is True
    assert blocks["stage1_capacity_headroom"] == COMPACT_BLOCK_CAPACITY - 1334 == 126
    assert blocks["classification"] == "REPRESENTATION_NOT_COMPARABLE"


def test_stage1_structural_overflow_is_exposed_without_recalibrating_to_host_oracle() -> None:
    result = audit(
        _requirements(),
        _value_contract(),
        stage1_structural_blocks=COMPACT_BLOCK_CAPACITY + 1,
    )
    blocks = result["storage"]["blocks"]
    assert blocks["stage1_capacity_fits_measurement"] is False
    assert blocks["stage1_capacity_headroom"] == -1
    assert blocks["host_oracle_blocks"] == 2987


def test_oracle_must_remain_explicitly_non_stage1_evidence() -> None:
    requirements = _requirements()
    requirements["reference_typed_ir"]["status"] = "PASS"
    result = audit(requirements, _value_contract())
    assert result["status"] == "STATIC_IR_STORAGE_TOPOLOGY_RECONCILE"
    assert result["guards"]["oracle_is_explicitly_non_stage1"] is False
