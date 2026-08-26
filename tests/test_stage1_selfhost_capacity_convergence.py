from __future__ import annotations

import json
from pathlib import Path

import pytest

import tools.qualify_stage1_selfhost_capacity_convergence as convergence


pytestmark = pytest.mark.s3_fast
SOURCE_SHA = "a" * 64
STAGE1_SHA = "b" * 64


def _contract() -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-selfhost-capacity-convergence-contract.v1",
        "measurement_schema": "s3.selfhost.stage1-selfhost-capacity-convergence-measurement.v1",
        "output_schema": "s3.selfhost.stage1-selfhost-capacity-convergence.v1",
    }


def _measurement(parameters: int = 70, locals_required: int = 225) -> dict[str, object]:
    run = {
        "source_sha256": SOURCE_SHA,
        "stage1_sha256": STAGE1_SHA,
        "parameters_required": parameters,
        "locals_required": locals_required,
        "overflow_attempted": False,
        "truncation_detected": False,
    }
    return {
        "schema": "s3.selfhost.stage1-selfhost-capacity-convergence-measurement.v1",
        "canonical_source": {"sha256": SOURCE_SHA, "bytes": 1234},
        "stage1": {"sha256": STAGE1_SHA, "bytes": 4321},
        "platform": {"system": "Linux", "machine": "x86_64"},
        "measurement": {
            "native_evidence": True,
            "projection_substituted_for_native_measurement": False,
            "source_mutated_after_measurement": False,
            "capacity_mutated_after_measurement": False,
            "repeated_required_counts_identical": True,
        },
        "lanes": {
            "parameters": {
                "scope": "ALL_DECLARED_PARAMETERS",
                "required": parameters,
                "capacity": parameters,
                "headroom": 0,
                "selection_policy": "EXACT",
                "overflow_attempted": False,
                "truncation_detected": False,
                "guard_probe": "PASS",
            },
            "locals": {
                "scope": "ALL_VARIABLE_DECLARATIONS",
                "required": locals_required,
                "capacity": locals_required,
                "headroom": 0,
                "selection_policy": "EXACT",
                "overflow_attempted": False,
                "truncation_detected": False,
                "guard_probe": "PASS",
            },
        },
        "native_runs": [dict(run), dict(run)],
    }


def _write_json(path: Path, value: dict[str, object]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _patch_bindings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        convergence,
        "_source_inventory",
        lambda path: {
            "path": str(path),
            "sha256": SOURCE_SHA,
            "bytes": 1234,
            "functions_total": 32,
            "parameters_total": 70,
            "local_declarations_total": 225,
        },
    )
    monkeypatch.setattr(
        convergence,
        "_artifact_binding",
        lambda path: {"path": str(path), "sha256": STAGE1_SHA, "bytes": 4321},
    )


def _qualify(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, measurement: dict[str, object]):
    _patch_bindings(monkeypatch)
    contract = _write_json(tmp_path / "contract.json", _contract())
    measured = _write_json(tmp_path / "measurement.json", measurement)
    return convergence.qualify(
        source=tmp_path / "source.s3",
        stage1=tmp_path / "stage1",
        measurement_path=measured,
        contract_path=contract,
        report_path=tmp_path / "report.json",
    )


def test_exact_current_counts_pass_and_never_authorize_stage2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _qualify(tmp_path, monkeypatch, _measurement())
    assert result["status"] == "PASS_SELFHOST_CAPACITY_CONVERGENCE"
    assert result["lanes"]["parameters"]["required"] == 70
    assert result["lanes"]["locals"]["required"] == 225
    assert result["qualification"]["final_capacity_gate_allowed"] is True
    assert result["qualification"]["stage2_allowed_from_this_report_alone"] is False


def test_stale_68_parameter_measurement_is_rejected_when_source_recounts_70(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(convergence.CapacityConvergenceError, match="parameters required count is stale"):
        _qualify(tmp_path, monkeypatch, _measurement(parameters=68))


def test_stale_local_measurement_is_rejected_after_source_instrumentation_growth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(convergence.CapacityConvergenceError, match="locals required count is stale"):
        _qualify(tmp_path, monkeypatch, _measurement(locals_required=206))


def test_exact_capacity_cannot_hide_positive_headroom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    measurement = _measurement()
    measurement["lanes"]["parameters"]["capacity"] = 72
    measurement["lanes"]["parameters"]["headroom"] = 2
    with pytest.raises(convergence.CapacityConvergenceError, match="EXACT capacity must equal required"):
        _qualify(tmp_path, monkeypatch, measurement)


def test_one_native_measurement_is_not_convergence_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    measurement = _measurement()
    measurement["native_runs"] = measurement["native_runs"][:1]
    with pytest.raises(convergence.CapacityConvergenceError, match="at least two native"):
        _qualify(tmp_path, monkeypatch, measurement)


def test_second_native_run_with_stale_required_count_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    measurement = _measurement()
    measurement["native_runs"][1]["locals_required"] = 224
    with pytest.raises(convergence.CapacityConvergenceError, match="stale or nondeterministic"):
        _qualify(tmp_path, monkeypatch, measurement)


def test_source_mutation_after_measurement_is_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    measurement = _measurement()
    measurement["measurement"]["source_mutated_after_measurement"] = True
    with pytest.raises(convergence.CapacityConvergenceError, match="source_mutated_after_measurement"):
        _qualify(tmp_path, monkeypatch, measurement)


def test_banked_capacity_requires_dispatch_and_roundtrip_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    measurement = _measurement()
    lane = measurement["lanes"]["locals"]
    lane.update(
        {
            "selection_policy": "BANKED",
            "capacity": 365,
            "headroom": 140,
            "bank_layout": [365],
            "dispatch_proof": "FAIL",
            "roundtrip_proof": "PASS",
        }
    )
    with pytest.raises(convergence.CapacityConvergenceError, match="bank dispatch proof"):
        _qualify(tmp_path, monkeypatch, measurement)
