from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from tools.qualify_stage1_final_capacity import FinalCapacityError, finalize_capacity


pytestmark = pytest.mark.s3_fast
ROOT = Path(__file__).resolve().parents[1]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _contract() -> dict[str, object]:
    return json.loads(
        (ROOT / "reports" / "selfhost" / "stage1" / "final-capacity-contract.json").read_text(
            encoding="utf-8"
        )
    )


def _lane(*, required: int = 3, capacity: int = 8, banked: bool = False) -> dict[str, object]:
    return {
        "required": required,
        "capacity": capacity,
        "headroom": capacity - required,
        "max_written_index": None if required == 0 else required - 1,
        "sparse": False,
        "overflow_attempted": False,
        "truncation_detected": False,
        "guard_probe": "PASS",
        "dispatch_proof": "PASS" if banked else "NOT_BANKED",
        "roundtrip_proof": "PASS" if banked else "NOT_BANKED",
        "provenance": "native qualification high-water counter",
    }


def _measurement(source: Path, stage1: Path) -> dict[str, object]:
    contract = _contract()
    source_sha = _sha(source.read_bytes())
    stage1_sha = _sha(stage1.read_bytes())
    lanes = {
        name: _lane(banked=name in {"tokens", "events", "semantic_values", "call_arguments"})
        for name in contract["minimum_required_lanes"]  # type: ignore[index]
    }
    return {
        "schema": "s3.selfhost.stage1-capacity-measurement.v1",
        "platform": {"system": "Linux", "machine": "x86_64"},
        "native_evidence": True,
        "projection_substituted_for_native_measurement": False,
        "bounded_lane_inventory_complete": True,
        "bounded_write_sites_accounted_exactly": True,
        "all_banked_dispatch_proofs_pass": True,
        "all_banked_roundtrip_proofs_pass": True,
        "all_lane_overflow_guards_exercised": True,
        "canonical_source_sha_matches_runtime_input": True,
        "stage1_artifact_sha_matches_executed_binary": True,
        "canonical_source": {
            "sha256": source_sha,
            "bytes": source.stat().st_size,
            "runtime_input_sha256": source_sha,
        },
        "stage1": {
            "sha256": stage1_sha,
            "bytes": stage1.stat().st_size,
            "executed_sha256": stage1_sha,
        },
        "bounded_lane_inventory": {
            "complete": True,
            "bounded_write_sites_total": 41,
            "accounted_write_sites": 41,
            "source_sha256": source_sha,
        },
        "lanes": lanes,
    }


def _files(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "compiler.s3"
    stage1 = tmp_path / "s3c-stage1"
    source.write_bytes(b"fn main() -> tryte:\n    return 0\n")
    stage1.write_bytes(b"\x7fELFsynthetic-stage1")
    return source, stage1


def test_valid_native_measurement_finalizes_without_authorizing_stage2(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    result = finalize_capacity(
        _measurement(source, stage1),
        source_path=source,
        stage1_path=stage1,
        contract=_contract(),
        measurement_sha256="a" * 64,
    )
    assert result["schema"] == "s3.selfhost.stage1-final-capacity.v1"
    assert result["qualification"]["all_capacities_no_truncation"] == "PASS"
    assert result["qualification"]["stage2_allowed_from_this_report_alone"] is False
    assert result["qualification"]["full_self_hosting"] is False
    assert result["summary"]["truncation_detected"] is False


def test_missing_required_lane_fails_closed(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    del measurement["lanes"]["semantic_values"]  # type: ignore[index]
    with pytest.raises(FinalCapacityError, match="missing required lanes"):
        finalize_capacity(measurement, source_path=source, stage1_path=stage1, contract=_contract())


def test_required_over_capacity_or_fake_headroom_fails_closed(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    measurement["lanes"]["events"].update(  # type: ignore[index]
        {"required": 9, "capacity": 8, "headroom": -1, "max_written_index": 8}
    )
    with pytest.raises(FinalCapacityError, match="exceeds capacity"):
        finalize_capacity(measurement, source_path=source, stage1_path=stage1, contract=_contract())

    measurement = _measurement(source, stage1)
    measurement["lanes"]["events"]["headroom"] = 99  # type: ignore[index]
    with pytest.raises(FinalCapacityError, match="headroom mismatch"):
        finalize_capacity(measurement, source_path=source, stage1_path=stage1, contract=_contract())


def test_truncation_or_missing_overflow_guard_fails_closed(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    measurement["lanes"]["instructions"]["truncation_detected"] = True  # type: ignore[index]
    with pytest.raises(FinalCapacityError, match="reports truncation"):
        finalize_capacity(measurement, source_path=source, stage1_path=stage1, contract=_contract())

    measurement = _measurement(source, stage1)
    measurement["lanes"]["instructions"]["guard_probe"] = "NOT_RUN"  # type: ignore[index]
    with pytest.raises(FinalCapacityError, match="overflow-guard probe"):
        finalize_capacity(measurement, source_path=source, stage1_path=stage1, contract=_contract())


def test_partial_bounded_write_site_inventory_fails_closed(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    measurement["bounded_lane_inventory"]["accounted_write_sites"] = 40  # type: ignore[index]
    with pytest.raises(FinalCapacityError, match="write-site inventory mismatch"):
        finalize_capacity(measurement, source_path=source, stage1_path=stage1, contract=_contract())


def test_stale_source_or_stage1_binding_fails_closed(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    source.write_bytes(source.read_bytes() + b"# changed\n")
    with pytest.raises(FinalCapacityError, match="canonical_source SHA mismatch"):
        finalize_capacity(measurement, source_path=source, stage1_path=stage1, contract=_contract())

    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    stage1.write_bytes(stage1.read_bytes() + b"changed")
    with pytest.raises(FinalCapacityError, match="stage1 SHA mismatch"):
        finalize_capacity(measurement, source_path=source, stage1_path=stage1, contract=_contract())


def test_banked_dispatch_and_roundtrip_must_both_pass(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    measurement["lanes"]["call_arguments"]["roundtrip_proof"] = "NOT_BANKED"  # type: ignore[index]
    with pytest.raises(FinalCapacityError, match="must agree"):
        finalize_capacity(measurement, source_path=source, stage1_path=stage1, contract=_contract())


def test_static_or_projection_only_measurement_is_rejected(tmp_path: Path) -> None:
    source, stage1 = _files(tmp_path)
    measurement = _measurement(source, stage1)
    measurement["native_evidence"] = False
    with pytest.raises(FinalCapacityError, match="native_evidence"):
        finalize_capacity(measurement, source_path=source, stage1_path=stage1, contract=_contract())

    measurement = _measurement(source, stage1)
    measurement["projection_substituted_for_native_measurement"] = True
    with pytest.raises(FinalCapacityError, match="projection_substituted"):
        finalize_capacity(measurement, source_path=source, stage1_path=stage1, contract=_contract())
