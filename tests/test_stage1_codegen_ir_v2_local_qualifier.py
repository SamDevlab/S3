from __future__ import annotations

import hashlib

import pytest

from tools.patch_stage1_codegen_ir_v2_locals import SOURCE
from tools.patch_stage1_codegen_ir_v2_parameters import build_candidate as build_parameter_candidate
from tools.preflight_stage1_codegen_ir_v2_locals import source_metrics
from tools.qualify_stage1_codegen_ir_v2_locals import (
    LocalNativeQualificationError,
    _native_count_guards,
    validate_parameter_report_strict,
)


def _complete_parameter_report() -> dict[str, object]:
    canonical = SOURCE.read_text(encoding="utf-8")
    parameter_source = build_parameter_candidate(canonical)
    encoded = parameter_source.encode("utf-8")
    metrics = source_metrics(parameter_source)
    audit = {
        "function_count": 34,
        "foreign_count": 5,
        "parameter_count": 64,
        "local_count": int(metrics["mut_hash_tokens"]),
        "ast_assignment_count": 100,
        "ast_call_count": int(metrics["call_syntax_count"]),
        "ast_return_count": 100,
        "ast_match_count": int(metrics["match_hash_tokens"]),
        "ast_while_count": int(metrics["while_hash_tokens"]),
        "ast_break_count": 0,
        "ast_binop_count": 100,
        "ast_comparison_count": 50,
        "ast_cast_count": 0,
        "ast_discard_count": 100,
        "local_function_count": 29,
        "ir_foreign_function_count": 5,
        "ir_parameter_count": 64,
        "ir_local_count": int(metrics["mut_hash_tokens"]),
        "ir_block_count": 320,
        "ir_instruction_count": int(metrics["structural_event_tokens"]),
        "ir_value_count": int(metrics["numeric_tokens"]),
        "ir_internal_call_count": max(0, int(metrics["call_syntax_count"]) - 3),
        "ir_foreign_call_count": min(3, int(metrics["call_syntax_count"])),
        "ir_branch_count": 100,
        "ir_loop_count": int(metrics["while_hash_tokens"]),
        "ir_return_count": 100,
    }
    return {
        "schema": "s3.selfhost.codegen-ir-v2-parameters-native-candidate.v1",
        "platform": {"system": "Linux", "machine": "x86_64", "compiler": "/usr/bin/cc"},
        "canonical_source_mutated": False,
        "candidate": {
            "source_sha256": hashlib.sha256(encoded).hexdigest(),
            "source_bytes": len(encoded),
        },
        "self_source": {
            "status": "PASS_PARAMETER_VERIFIER_TO_EXPECTED_EMITTER_BOUNDARY",
            "returncode": 2,
            "stdout_bytes": 0,
            "audit": audit,
            "final_marker": "S3_STAGE1_EMITTER_BLOCKED",
        },
        "qualification": {
            "static_preflight": "PASS",
            "prerequisite_capacity_report": "PASS_VALIDATED",
            "candidate_build": "PASS",
            "trivial_compile": "PASS",
            "parameter_verifier_to_emitter_boundary": "PASS",
            "capacity_guards": "PASS",
            "parameter_ir_v2_candidate": "PASS_NATIVE_CANDIDATE",
            "canonical_commit_allowed": False,
        },
    }


def test_strict_parameter_report_requires_every_subgate() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    report = _complete_parameter_report()
    parameter_source, normalized, audit = validate_parameter_report_strict(
        report,
        canonical_source=canonical,
    )
    assert hashlib.sha256(parameter_source.encode("utf-8")).hexdigest() == report["candidate"]["source_sha256"]
    assert normalized["parameter_count"] == 64
    assert audit["function_count"] == 34

    report["qualification"]["capacity_guards"] = "FAIL"
    with pytest.raises(LocalNativeQualificationError, match="capacity_guards"):
        validate_parameter_report_strict(report, canonical_source=canonical)


def test_strict_parameter_report_requires_linux_boundary_provenance() -> None:
    canonical = SOURCE.read_text(encoding="utf-8")
    report = _complete_parameter_report()
    report["platform"]["system"] = "Windows"
    with pytest.raises(LocalNativeQualificationError, match="Linux x86-64"):
        validate_parameter_report_strict(report, canonical_source=canonical)

    report = _complete_parameter_report()
    report["self_source"]["final_marker"] = "S3_STAGE1_ERROR"
    with pytest.raises(LocalNativeQualificationError, match="final marker"):
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
