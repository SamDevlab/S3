from __future__ import annotations

import pytest

from tools.patch_stage1_codegen_ir_v2_locals import SOURCE
from tools.qualify_stage1_codegen_ir_v2_locals import (
    LocalNativeQualificationError,
    _native_count_guards,
    validate_parameter_report_strict,
)


def _stale_parameter_report() -> dict[str, object]:
    return {
        "schema": "s3.selfhost.codegen-ir-v2-parameters-native-candidate.v1",
        "platform": {"system": "Linux", "machine": "x86_64", "compiler": "/usr/bin/cc"},
        "canonical_source_mutated": False,
        "candidate": {"source_sha256": "0" * 64, "source_bytes": 0},
        "qualification": {
            "parameter_ir_v2_candidate": "PASS_NATIVE_CANDIDATE",
        },
    }


def test_strict_parameter_report_rejects_stale_packed_candidate() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    with pytest.raises(LocalNativeQualificationError, match="packed parameter candidate is stale"):
        validate_parameter_report_strict(_stale_parameter_report(), canonical_source=canonical)


def test_strict_parameter_report_does_not_promote_advanced_source() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    report = _stale_parameter_report()
    report["canonical_source_mutated"] = True
    with pytest.raises(LocalNativeQualificationError):
        validate_parameter_report_strict(report, canonical_source=canonical)


def test_strict_parameter_report_requires_linux_boundary_provenance() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    report = _stale_parameter_report()
    with pytest.raises(LocalNativeQualificationError, match="packed parameter candidate is stale"):
        validate_parameter_report_strict(report, canonical_source=canonical)

    report = _stale_parameter_report()
    report["qualification"]["parameter_ir_v2_candidate"] = "FAIL"
    with pytest.raises(LocalNativeQualificationError, match="parameter IR-v2 prerequisite"):
        validate_parameter_report_strict(report, canonical_source=canonical)


def _preflight() -> dict[str, object]:
    return {
        "local_candidate": {
            "required_records_including_candidate_self_source": 120,
            "selected_capacity": 120,
        },
        "native_headroom_projection": {
            "projected_candidate_counts": {
                "events": 900,
                "values": 1200,
                "blocks": 340,
                "calls": 680,
            }
        },
    }


def _parameter_audit() -> dict[str, int]:
    return {
        "function_count": 34,
        "foreign_count": 5,
        "local_function_count": 29,
    }


def _local_audit() -> dict[str, int]:
    return {
        "function_count": 34,
        "foreign_count": 5,
        "local_function_count": 29,
        "parameter_count": 64,
        "ir_parameter_count": 64,
        "local_count": 120,
        "ir_local_count": 120,
        "ir_instruction_count": 900,
        "ir_value_count": 1200,
        "ir_block_count": 340,
        "ast_call_count": 680,
    }


def test_native_count_guards_require_exact_static_projection() -> None:
    guards = _native_count_guards(
        _local_audit(),
        parameter_audit=_parameter_audit(),
        preflight=_preflight(),
    )
    assert all(guards.values())


def test_native_count_guards_fail_on_local_or_projection_drift() -> None:
    audit = _local_audit()
    audit["local_count"] = 119
    audit["ir_instruction_count"] = 901
    guards = _native_count_guards(
        audit,
        parameter_audit=_parameter_audit(),
        preflight=_preflight(),
    )
    assert guards["local_count_exact"] is False
    assert guards["events_exact_projection"] is False
