from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tools.reconcile_stage1_native_calls import (
    NativeCallReconciliationError,
    reconcile,
)


pytestmark = pytest.mark.s3_fast


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _contract() -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-native-call-reconciliation-contract.v1",
        "measurement_schema": "s3.selfhost.stage1-native-call-measurement.v1",
        "hosted_inventory_schema": "s3.selfhost.reference-current-call-inventory.v1",
        "output_schema": "s3.selfhost.stage1-native-call-reconciliation.v1",
        "measurement_requirements": {
            "native_evidence": True,
            "projection_substituted_for_native_measurement": False,
            "canonical_source_sha_matches_runtime_input": True,
            "stage1_artifact_sha_matches_executed_binary": True,
            "all_call_slices_in_range": True,
            "all_argument_slices_in_range": True,
            "all_recorded_arguments_addressable": True,
        },
    }


def _fixture(tmp_path: Path):
    source = tmp_path / "compiler.s3"
    source_bytes = b"fn main() -> tryte:\n    return 0\n"
    source.write_bytes(source_bytes)
    stage1 = tmp_path / "stage1"
    stage1_bytes = b"stage1"
    stage1.write_bytes(stage1_bytes)

    hosted = {
        "schema": "s3.selfhost.reference-current-call-inventory.v1",
        "status": "PASS_HOSTED_CURRENT_SOURCE_CALL_INVENTORY",
        "source": {"sha256": _sha(source_bytes), "bytes": len(source_bytes)},
        "ast": {"total_call_expressions": 4, "total_argument_occurrences": 7},
        "o0_ir": {"total_call_instructions": 3, "total_operand_uses": 5},
    }
    measurement = {
        "schema": "s3.selfhost.stage1-native-call-measurement.v1",
        "native_evidence": True,
        "projection_substituted_for_native_measurement": False,
        "canonical_source_sha_matches_runtime_input": True,
        "stage1_artifact_sha_matches_executed_binary": True,
        "all_call_slices_in_range": True,
        "all_argument_slices_in_range": True,
        "all_recorded_arguments_addressable": True,
        "platform": {"system": "Linux", "machine": "x86_64"},
        "canonical_source": {
            "sha256": _sha(source_bytes),
            "bytes": len(source_bytes),
            "runtime_input_sha256": _sha(source_bytes),
        },
        "stage1": {
            "sha256": _sha(stage1_bytes),
            "bytes": len(stage1_bytes),
            "executed_sha256": _sha(stage1_bytes),
        },
        "audit": {
            "ir_call_count": 5,
            "ir_call_arg_pool_count": 9,
            "ir_internal_call_count": 4,
            "ir_foreign_call_count": 1,
        },
        "call_records": {
            "high_water": 5,
            "capacity": 10,
            "max_written_index": 4,
            "overflow_attempted": False,
            "truncation_detected": False,
            "guard_probe": "PASS",
        },
        "call_arguments": {
            "high_water": 9,
            "capacity": 12,
            "max_written_index": 8,
            "overflow_attempted": False,
            "truncation_detected": False,
            "guard_probe": "PASS",
        },
    }
    return source, stage1, hosted, measurement


def test_native_high_water_is_authority_and_hosted_counts_are_diagnostic(tmp_path: Path) -> None:
    source, stage1, hosted, measurement = _fixture(tmp_path)
    result = reconcile(
        measurement,
        hosted,
        source_path=source,
        stage1_path=stage1,
        contract=_contract(),
    )
    assert result["status"] == "PASS_NATIVE_CURRENT_SOURCE_CALL_RECONCILIATION"
    assert result["native"]["call_records"]["high_water"] == 5
    assert result["native"]["call_arguments"]["high_water"] == 9
    assert result["hosted_diagnostics"]["native_minus_ast_calls"] == 1
    assert result["hosted_diagnostics"]["native_minus_o0_ir_calls"] == 2
    assert result["hosted_diagnostics"]["equality_required"] is False
    assert result["historical_closure"]["calls_656_arguments_736_reused"] is False


def test_internal_foreign_must_close_total_native_call_count(tmp_path: Path) -> None:
    source, stage1, hosted, measurement = _fixture(tmp_path)
    measurement["audit"]["ir_foreign_call_count"] = 0
    with pytest.raises(NativeCallReconciliationError, match="classification is incomplete"):
        reconcile(measurement, hosted, source_path=source, stage1_path=stage1, contract=_contract())


def test_call_record_high_water_must_match_native_audit(tmp_path: Path) -> None:
    source, stage1, hosted, measurement = _fixture(tmp_path)
    measurement["call_records"]["high_water"] = 4
    with pytest.raises(NativeCallReconciliationError, match="high-water disagrees"):
        reconcile(measurement, hosted, source_path=source, stage1_path=stage1, contract=_contract())


def test_call_argument_high_water_must_match_native_audit(tmp_path: Path) -> None:
    source, stage1, hosted, measurement = _fixture(tmp_path)
    measurement["call_arguments"]["high_water"] = 8
    with pytest.raises(NativeCallReconciliationError, match="high-water disagrees"):
        reconcile(measurement, hosted, source_path=source, stage1_path=stage1, contract=_contract())


def test_capacity_overflow_or_truncation_blocks(tmp_path: Path) -> None:
    source, stage1, hosted, measurement = _fixture(tmp_path)
    measurement["call_records"]["capacity"] = 4
    with pytest.raises(NativeCallReconciliationError, match="exceeds capacity"):
        reconcile(measurement, hosted, source_path=source, stage1_path=stage1, contract=_contract())

    _source, _stage1, hosted, measurement = _fixture(tmp_path)
    measurement["call_arguments"]["truncation_detected"] = True
    with pytest.raises(NativeCallReconciliationError, match="truncation"):
        reconcile(measurement, hosted, source_path=source, stage1_path=stage1, contract=_contract())


def test_hosted_inventory_stale_for_source_is_rejected(tmp_path: Path) -> None:
    source, stage1, hosted, measurement = _fixture(tmp_path)
    source.write_bytes(source.read_bytes() + b"\n")
    with pytest.raises(NativeCallReconciliationError, match="stale"):
        reconcile(measurement, hosted, source_path=source, stage1_path=stage1, contract=_contract())


def test_stage1_artifact_binding_is_revalidated(tmp_path: Path) -> None:
    source, stage1, hosted, measurement = _fixture(tmp_path)
    stage1.write_bytes(b"different-stage1")
    with pytest.raises(NativeCallReconciliationError, match="stage1 binding is stale"):
        reconcile(measurement, hosted, source_path=source, stage1_path=stage1, contract=_contract())
