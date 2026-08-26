from __future__ import annotations

import hashlib

import pytest

from tools.audit_stage1_representation_epoch import (
    RepresentationEpochError,
    classify_source,
    validate_epoch_report_for_source,
)


pytestmark = pytest.mark.s3_fast


def _contract() -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-representation-epoch-contract.v1",
        "output_schema": "s3.selfhost.stage1-representation-epoch.v1",
        "explicit_parameter_arrays_required": [
            "ir_parameter_owner",
            "ir_parameter_name",
            "ir_parameter_ordinal",
            "ir_parameter_type",
        ],
        "packed_parameter_marker": "ir_parameter_records",
        "packed_local_marker": "ir_local_records",
        "explicit_local_array_minimum": 8,
        "local_array_prefix": "ir_local_",
        "local_array_exclusions": ["ir_local_records"],
    }


def _arrays(names: list[str], size: int = 16) -> str:
    init = ", ".join("0" for _ in range(size))
    return "\n".join(f"    mut {name}: i64[{size}] = [{init}]" for name in names)


def _classify(source: str) -> dict[str, object]:
    return classify_source(source, contract=_contract())


def test_epoch_zero_has_no_materialized_parameter_metadata() -> None:
    report = _classify("fn main() -> tryte:\n    return 0\n")
    assert report["status"] == "PASS_REPRESENTATION_EPOCH_CLASSIFIED"
    assert report["representation"]["epoch"] == 0
    assert report["historical_transform_compatibility"]["legacy_packed_parameter_transform_applicable"] is True


def test_epoch_one_is_legacy_packed_parameter_record() -> None:
    source = "fn main() -> tryte:\n" + _arrays(["ir_parameter_records"]) + "\n    return 0\n"
    report = _classify(source)
    assert report["representation"]["epoch"] == 1
    assert report["representation"]["packed_parameter_record_present"] is True
    assert report["historical_transform_compatibility"]["legacy_packed_local_transform_directly_applicable"] is True


def test_epoch_two_detects_explicit_parameter_lanes() -> None:
    names = ["ir_parameter_owner", "ir_parameter_name", "ir_parameter_ordinal", "ir_parameter_type"]
    source = "fn main() -> tryte:\n" + _arrays(names) + "\n    return 0\n"
    report = _classify(source)
    assert report["representation"]["epoch"] == 2
    assert report["representation"]["explicit_parameter_metadata_complete"] is True
    assert report["historical_transform_compatibility"]["newer_epoch_requires_migration_not_reapplication"] is True
    assert report["historical_transform_compatibility"]["legacy_packed_parameter_transform_applicable"] is False


def test_epoch_three_detects_eight_explicit_local_lanes() -> None:
    parameter_names = ["ir_parameter_owner", "ir_parameter_name", "ir_parameter_ordinal", "ir_parameter_type"]
    local_names = [
        "ir_local_owner",
        "ir_local_name",
        "ir_local_type",
        "ir_local_mutability",
        "ir_local_storage_kind",
        "ir_local_ordinal",
        "ir_local_extent",
        "ir_local_value_id",
    ]
    source = "fn main() -> tryte:\n" + _arrays(parameter_names + local_names, size=32) + "\n    return 0\n"
    report = _classify(source)
    assert report["representation"]["epoch"] == 3
    assert report["representation"]["explicit_local_array_count"] == 8
    assert report["representation"]["explicit_local_metadata_complete"] is True


def test_scalar_local_record_count_is_not_a_metadata_lane() -> None:
    parameter_names = ["ir_parameter_owner", "ir_parameter_name", "ir_parameter_ordinal", "ir_parameter_type"]
    source = (
        "fn main() -> tryte:\n"
        + _arrays(parameter_names)
        + "\n    mut ir_local_record_count: i64 = 0\n    return 0\n"
    )
    report = _classify(source)
    assert report["representation"]["epoch"] == 2
    assert report["representation"]["explicit_local_array_count"] == 0


def test_packed_and_explicit_parameter_metadata_is_blocked() -> None:
    names = [
        "ir_parameter_records",
        "ir_parameter_owner",
        "ir_parameter_name",
        "ir_parameter_ordinal",
        "ir_parameter_type",
    ]
    report = _classify("fn main() -> tryte:\n" + _arrays(names) + "\n    return 0\n")
    assert report["status"] == "BLOCKED_REPRESENTATION_EPOCH_INCONSISTENT"
    assert "PACKED_AND_EXPLICIT_PARAMETER_METADATA_COEXIST" in report["representation"]["conflicts"]


def test_partial_explicit_parameter_metadata_is_blocked() -> None:
    report = _classify(
        "fn main() -> tryte:\n"
        + _arrays(["ir_parameter_owner", "ir_parameter_name"])
        + "\n    return 0\n"
    )
    assert report["status"] == "BLOCKED_REPRESENTATION_EPOCH_INCONSISTENT"
    assert "PARTIAL_EXPLICIT_PARAMETER_METADATA" in report["representation"]["conflicts"]


def test_partial_explicit_local_metadata_is_blocked() -> None:
    parameter_names = ["ir_parameter_owner", "ir_parameter_name", "ir_parameter_ordinal", "ir_parameter_type"]
    report = _classify(
        "fn main() -> tryte:\n"
        + _arrays(parameter_names + ["ir_local_owner", "ir_local_name"])
        + "\n    return 0\n"
    )
    assert report["status"] == "BLOCKED_REPRESENTATION_EPOCH_INCONSISTENT"
    assert "PARTIAL_EXPLICIT_LOCAL_METADATA" in report["representation"]["conflicts"]


def test_epoch_report_is_hash_bound_to_source() -> None:
    source = "fn main() -> tryte:\n    return 0\n"
    report = _classify(source)
    validate_epoch_report_for_source(report, source.encode("utf-8"), minimum_epoch=0)
    with pytest.raises(RepresentationEpochError, match="stale"):
        validate_epoch_report_for_source(report, (source + "\n").encode("utf-8"))


def test_minimum_epoch_requirement_is_fail_closed() -> None:
    source = "fn main() -> tryte:\n    return 0\n"
    report = _classify(source)
    with pytest.raises(RepresentationEpochError, match="older than required"):
        validate_epoch_report_for_source(report, source.encode("utf-8"), minimum_epoch=2)
