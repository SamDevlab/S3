"""Prepare the Stage1 IR-v2 local-metadata source candidate.

This module is intentionally candidate-only. The pure ``transform_locals``
function exists for tests/preflight, but the CLI refuses to materialize a
candidate unless it consumes a PASS native parameter report whose source SHA
matches the exact compaction+parameter candidate rebuilt from the canonical
baseline.

The local record preserves scalar-vs-fixed-array shape. Physical stack/static
layout remains emitter-owned; semantic IR stores a deterministic local ordinal,
not a prematurely frozen byte offset.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.audit_stage1_codegen_ir_v2_local_metadata import MAX_LOCAL_RECORDS
from tools.patch_stage1_codegen_ir_v2_parameters import build_candidate as build_parameter_candidate


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_PARAMETER_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-parameters-native-candidate.json"
)


class LocalCandidateError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _replace_once(source: str, old: str, new: str, *, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise LocalCandidateError(f"{label}: expected exactly one anchor, found {count}")
    return source.replace(old, new, 1)


def _zero_array(size: int) -> str:
    return "[" + ", ".join("0" for _ in range(size)) + "]"


def _load_report(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise LocalCandidateError(f"cannot read native parameter report: {error}") from error
    if not isinstance(value, dict):
        raise LocalCandidateError("native parameter report must be a JSON object")
    return value


def validate_parameter_prerequisite(
    report: dict[str, Any],
    *,
    canonical_source: str,
) -> tuple[str, dict[str, int]]:
    """Return exact parameter-candidate source + native audit on valid evidence."""

    if report.get("schema") != "s3.selfhost.codegen-ir-v2-parameters-native-candidate.v1":
        raise LocalCandidateError("unexpected native parameter report schema")
    if report.get("canonical_source_mutated") is not False:
        raise LocalCandidateError("parameter report must come from non-mutating qualification")
    qualification = report.get("qualification")
    if not isinstance(qualification, dict):
        raise LocalCandidateError("parameter report qualification is missing")
    if qualification.get("parameter_ir_v2_candidate") != "PASS_NATIVE_CANDIDATE":
        raise LocalCandidateError("parameter IR-v2 prerequisite is not a native PASS candidate")

    parameter_source = build_parameter_candidate(canonical_source)
    parameter_bytes = parameter_source.encode("utf-8")
    candidate = report.get("candidate")
    if not isinstance(candidate, dict):
        raise LocalCandidateError("parameter report candidate metadata is missing")
    if candidate.get("source_sha256") != _sha256(parameter_bytes):
        raise LocalCandidateError("parameter report source SHA does not match rebuilt exact candidate")
    if candidate.get("source_bytes") != len(parameter_bytes):
        raise LocalCandidateError("parameter report source byte count does not match rebuilt exact candidate")

    self_source = report.get("self_source")
    if not isinstance(self_source, dict):
        raise LocalCandidateError("parameter report self_source evidence is missing")
    audit = self_source.get("audit")
    if not isinstance(audit, dict):
        raise LocalCandidateError("parameter report native self-source audit is missing")
    required_native_fields = (
        "parameter_count",
        "local_count",
        "ir_instruction_count",
        "ir_value_count",
        "ir_block_count",
        "ast_call_count",
    )
    normalized: dict[str, int] = {}
    for field in required_native_fields:
        value = audit.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise LocalCandidateError(f"invalid native parameter audit field: {field}")
        normalized[field] = value
    return parameter_source, normalized


def transform_locals(parameter_source: str, *, local_capacity: int) -> str:
    """Add packed, shape-preserving local metadata to a parameter candidate."""

    if not isinstance(local_capacity, int) or isinstance(local_capacity, bool):
        raise LocalCandidateError("local capacity must be an integer")
    if local_capacity < 1 or local_capacity > MAX_LOCAL_RECORDS:
        raise LocalCandidateError(
            f"local capacity must be in 1..{MAX_LOCAL_RECORDS}; got {local_capacity}"
        )
    if "mut ir_parameter_records: i64[64]" not in parameter_source:
        raise LocalCandidateError("local transform requires the packed-parameter candidate first")
    if "mut ir_local_records:" in parameter_source:
        raise LocalCandidateError("local IR-v2 lane already exists")

    source = parameter_source

    parameter_decl_anchor = "    mut ir_parameter_records: i64[64] = "
    parameter_decl_index = source.find(parameter_decl_anchor)
    if parameter_decl_index < 0:
        raise LocalCandidateError("parameter record declaration anchor not found")
    parameter_decl_end = source.find("\n", parameter_decl_index)
    if parameter_decl_end < 0:
        raise LocalCandidateError("parameter record declaration line is unterminated")
    local_decl = (
        f"    mut ir_local_records: i64[{local_capacity}] = "
        + _zero_array(local_capacity)
        + "\n"
    )
    source = source[: parameter_decl_end + 1] + local_decl + source[parameter_decl_end + 1 :]

    state_anchor = "    mut pending_parameter_name: i64 = 0\n"
    state_insert = (
        state_anchor
        + "    mut local_capture_state: i64 = 0\n"
        + "    mut local_state_before: i64 = 0\n"
        + "    mut local_capture_index: i64 = -1\n"
        + "    mut local_capture_name: i64 = 0\n"
        + "    mut local_capture_type: i64 = 0\n"
        + "    mut local_capture_extent: i64 = 1\n"
        + "    mut local_capture_storage_kind: i64 = 1\n"
        + "    mut local_capture_owner: i64 = -1\n"
        + "    mut local_ordinal_owner: i64 = -1\n"
        + "    mut local_ordinal: i64 = 0\n"
        + "    mut local_finalize: trit = 0\n"
    )
    source = _replace_once(
        source,
        state_anchor,
        state_insert,
        label="local parser state",
    )

    parser_anchor = (
        "        match kind == 1:\n"
        "            -1:\n"
        "                match value == 311:\n"
        "                    -1:\n"
        "                        pending_foreign = -1\n"
    )
    local_progress = (
        "        local_state_before = local_capture_state\n"
        "        local_finalize = 0\n"
        "        match local_state_before == 1:\n"
        "            -1:\n"
        "                match kind == 1:\n"
        "                    -1:\n"
        "                        local_capture_name = value\n"
        "                        local_capture_state = 2\n"
        "                    0:\n"
        "                        ir_capacity_ok = 0\n"
        "                    1:\n"
        "                        ir_capacity_ok = 0\n"
        "            0:\n"
        "                discard 0\n"
        "            1:\n"
        "                discard 0\n"
        "        match local_state_before == 2:\n"
        "            -1:\n"
        "                match kind == 4:\n"
        "                    -1:\n"
        "                        match value == 3:\n"
        "                            -1:\n"
        "                                local_capture_state = 3\n"
        "                            0:\n"
        "                                ir_capacity_ok = 0\n"
        "                            1:\n"
        "                                ir_capacity_ok = 0\n"
        "                    0:\n"
        "                        ir_capacity_ok = 0\n"
        "                    1:\n"
        "                        ir_capacity_ok = 0\n"
        "            0:\n"
        "                discard 0\n"
        "            1:\n"
        "                discard 0\n"
        "        match local_state_before == 3:\n"
        "            -1:\n"
        "                match kind == 1:\n"
        "                    -1:\n"
        "                        match valid_type_name(value):\n"
        "                            -1:\n"
        "                                local_capture_type = value\n"
        "                                local_capture_state = 4\n"
        "                            0:\n"
        "                                ir_capacity_ok = 0\n"
        "                            1:\n"
        "                                ir_capacity_ok = 0\n"
        "                    0:\n"
        "                        ir_capacity_ok = 0\n"
        "                    1:\n"
        "                        ir_capacity_ok = 0\n"
        "            0:\n"
        "                discard 0\n"
        "            1:\n"
        "                discard 0\n"
        "        match local_state_before == 4:\n"
        "            -1:\n"
        "                match kind == 4:\n"
        "                    -1:\n"
        "                        match value == 5:\n"
        "                            -1:\n"
        "                                local_capture_storage_kind = 1\n"
        "                                local_capture_extent = 1\n"
        "                                local_finalize = -1\n"
        "                            0:\n"
        "                                match value == 10:\n"
        "                                    -1:\n"
        "                                        local_capture_storage_kind = 2\n"
        "                                        local_capture_state = 5\n"
        "                                    0:\n"
        "                                        ir_capacity_ok = 0\n"
        "                                    1:\n"
        "                                        ir_capacity_ok = 0\n"
        "                            1:\n"
        "                                ir_capacity_ok = 0\n"
        "                    0:\n"
        "                        ir_capacity_ok = 0\n"
        "                    1:\n"
        "                        ir_capacity_ok = 0\n"
        "            0:\n"
        "                discard 0\n"
        "            1:\n"
        "                discard 0\n"
        "        match local_state_before == 5:\n"
        "            -1:\n"
        "                match kind == 2:\n"
        "                    -1:\n"
        "                        match value > 0:\n"
        "                            -1:\n"
        "                                match value < 1461:\n"
        "                                    -1:\n"
        "                                        local_capture_extent = value\n"
        "                                        local_capture_state = 6\n"
        "                                    0:\n"
        "                                        ir_capacity_ok = 0\n"
        "                                    1:\n"
        "                                        ir_capacity_ok = 0\n"
        "                            0:\n"
        "                                ir_capacity_ok = 0\n"
        "                            1:\n"
        "                                ir_capacity_ok = 0\n"
        "                    0:\n"
        "                        ir_capacity_ok = 0\n"
        "                    1:\n"
        "                        ir_capacity_ok = 0\n"
        "            0:\n"
        "                discard 0\n"
        "            1:\n"
        "                discard 0\n"
        "        match local_state_before == 6:\n"
        "            -1:\n"
        "                match kind == 4:\n"
        "                    -1:\n"
        "                        match value == 11:\n"
        "                            -1:\n"
        "                                local_capture_state = 7\n"
        "                            0:\n"
        "                                ir_capacity_ok = 0\n"
        "                            1:\n"
        "                                ir_capacity_ok = 0\n"
        "                    0:\n"
        "                        ir_capacity_ok = 0\n"
        "                    1:\n"
        "                        ir_capacity_ok = 0\n"
        "            0:\n"
        "                discard 0\n"
        "            1:\n"
        "                discard 0\n"
        "        match local_state_before == 7:\n"
        "            -1:\n"
        "                match kind == 4:\n"
        "                    -1:\n"
        "                        match value == 5:\n"
        "                            -1:\n"
        "                                local_finalize = -1\n"
        "                            0:\n"
        "                                ir_capacity_ok = 0\n"
        "                            1:\n"
        "                                ir_capacity_ok = 0\n"
        "                    0:\n"
        "                        ir_capacity_ok = 0\n"
        "                    1:\n"
        "                        ir_capacity_ok = 0\n"
        "            0:\n"
        "                discard 0\n"
        "            1:\n"
        "                discard 0\n"
        "        match local_finalize == -1:\n"
        "            -1:\n"
        f"                match local_capture_index < {local_capacity}:\n"
        "                    -1:\n"
        "                        match local_capture_index >= 0:\n"
        "                            -1:\n"
        "                                match local_capture_owner >= 0:\n"
        "                                    -1:\n"
        "                                        match local_ordinal < 365:\n"
        "                                            -1:\n"
        "                                                ir_local_records[local_capture_index] = (((((((local_capture_owner + 1) * 366 + (local_capture_name + 1)) * 366 + (local_capture_type + 1)) * 2 + 1) * 3 + local_capture_storage_kind) * 366 + (local_ordinal + 1)) * 1461 + local_capture_extent) * 1461 + (64 + local_capture_index + 1)\n"
        "                                                ir_local_record_count += 1\n"
        "                                                local_ordinal += 1\n"
        "                                                local_capture_state = 0\n"
        "                                                local_capture_index = -1\n"
        "                                            0:\n"
        "                                                ir_capacity_ok = 0\n"
        "                                            1:\n"
        "                                                ir_capacity_ok = 0\n"
        "                                    0:\n"
        "                                        ir_capacity_ok = 0\n"
        "                                    1:\n"
        "                                        ir_capacity_ok = 0\n"
        "                            0:\n"
        "                                ir_capacity_ok = 0\n"
        "                            1:\n"
        "                                ir_capacity_ok = 0\n"
        "                    0:\n"
        "                        ir_capacity_ok = 0\n"
        "                    1:\n"
        "                        ir_capacity_ok = 0\n"
        "            0:\n"
        "                discard 0\n"
        "            1:\n"
        "                discard 0\n"
    )
    source = _replace_once(
        source,
        parser_anchor,
        local_progress + parser_anchor,
        label="local declaration state machine",
    )

    mut_old = (
        "                match value == 87:\n"
        "                    -1:\n"
        "                        local_count += 1\n"
        "                        ast_assignment_count += 1\n"
        "                        ir_ast_event_opcode = 6\n"
        "                        ir_ast_event_operand = value\n"
    )
    mut_new = (
        mut_old
        + "                        match signature_function_active == -1:\n"
        "                            -1:\n"
        "                                ir_capacity_ok = 0\n"
        "                            0:\n"
        "                                match current_function >= 0:\n"
        "                                    -1:\n"
        f"                                        match ir_local_record_count < {local_capacity}:\n"
        "                                            -1:\n"
        "                                                match local_capture_state == 0:\n"
        "                                                    -1:\n"
        "                                                        match local_ordinal_owner == current_function:\n"
        "                                                            -1:\n"
        "                                                                discard 0\n"
        "                                                            0:\n"
        "                                                                local_ordinal_owner = current_function\n"
        "                                                                local_ordinal = 0\n"
        "                                                            1:\n"
        "                                                                local_ordinal_owner = current_function\n"
        "                                                                local_ordinal = 0\n"
        "                                                        local_capture_index = ir_local_record_count\n"
        "                                                        local_capture_owner = current_function\n"
        "                                                        local_capture_extent = 1\n"
        "                                                        local_capture_storage_kind = 1\n"
        "                                                        local_capture_state = 1\n"
        "                                                    0:\n"
        "                                                        ir_capacity_ok = 0\n"
        "                                                    1:\n"
        "                                                        ir_capacity_ok = 0\n"
        "                                            0:\n"
        "                                                ir_capacity_ok = 0\n"
        "                                            1:\n"
        "                                                ir_capacity_ok = 0\n"
        "                                    0:\n"
        "                                        ir_capacity_ok = 0\n"
        "                                    1:\n"
        "                                        ir_capacity_ok = 0\n"
        "                            1:\n"
        "                                ir_capacity_ok = 0\n"
    )
    source = _replace_once(
        source,
        mut_old,
        mut_new,
        label="mut local capture",
    )

    verifier_anchor = "            mut parameter_verify_index: i64 = 0\n"
    verifier = (
        "            match local_capture_state == 0:\n"
        "                -1:\n"
        "                    discard 0\n"
        "                0:\n"
        "                    verifier_ok = 0\n"
        "                1:\n"
        "                    verifier_ok = 0\n"
        "            match ir_local_record_count == local_count:\n"
        "                -1:\n"
        "                    discard 0\n"
        "                0:\n"
        "                    verifier_ok = 0\n"
        "                1:\n"
        "                    verifier_ok = 0\n"
        f"            match ir_local_record_count < {local_capacity + 1}:\n"
        "                -1:\n"
        "                    discard 0\n"
        "                0:\n"
        "                    verifier_ok = 0\n"
        "                1:\n"
        "                    verifier_ok = 0\n"
        "            mut local_verify_index: i64 = 0\n"
        "            mut local_verify_previous_owner: i64 = -1\n"
        "            mut local_verify_expected_ordinal: i64 = 0\n"
        "            while local_verify_index < ir_local_record_count:\n"
        "                mut local_verify_remainder: i64 = ir_local_records[local_verify_index]\n"
        "                mut local_verify_quotient: i64 = local_verify_remainder / 1461\n"
        "                mut local_verify_field: i64 = local_verify_remainder - local_verify_quotient * 1461\n"
        "                match local_verify_field == 64 + local_verify_index + 1:\n"
        "                    -1:\n"
        "                        discard 0\n"
        "                    0:\n"
        "                        verifier_ok = 0\n"
        "                    1:\n"
        "                        verifier_ok = 0\n"
        "                local_verify_remainder = local_verify_quotient\n"
        "                local_verify_quotient = local_verify_remainder / 1461\n"
        "                local_verify_field = local_verify_remainder - local_verify_quotient * 1461\n"
        "                mut local_verify_extent: i64 = local_verify_field\n"
        "                match local_verify_extent > 0:\n"
        "                    -1:\n"
        "                        match local_verify_extent < 1461:\n"
        "                            -1:\n"
        "                                discard 0\n"
        "                            0:\n"
        "                                verifier_ok = 0\n"
        "                            1:\n"
        "                                verifier_ok = 0\n"
        "                    0:\n"
        "                        verifier_ok = 0\n"
        "                    1:\n"
        "                        verifier_ok = 0\n"
        "                local_verify_remainder = local_verify_quotient\n"
        "                local_verify_quotient = local_verify_remainder / 366\n"
        "                local_verify_field = local_verify_remainder - local_verify_quotient * 366\n"
        "                mut local_verify_ordinal: i64 = local_verify_field - 1\n"
        "                match local_verify_ordinal >= 0:\n"
        "                    -1:\n"
        "                        match local_verify_ordinal < 365:\n"
        "                            -1:\n"
        "                                discard 0\n"
        "                            0:\n"
        "                                verifier_ok = 0\n"
        "                            1:\n"
        "                                verifier_ok = 0\n"
        "                    0:\n"
        "                        verifier_ok = 0\n"
        "                    1:\n"
        "                        verifier_ok = 0\n"
        "                local_verify_remainder = local_verify_quotient\n"
        "                local_verify_quotient = local_verify_remainder / 3\n"
        "                local_verify_field = local_verify_remainder - local_verify_quotient * 3\n"
        "                mut local_verify_storage_kind: i64 = local_verify_field\n"
        "                match local_verify_storage_kind == 1:\n"
        "                    -1:\n"
        "                        match local_verify_extent == 1:\n"
        "                            -1:\n"
        "                                discard 0\n"
        "                            0:\n"
        "                                verifier_ok = 0\n"
        "                            1:\n"
        "                                verifier_ok = 0\n"
        "                    0:\n"
        "                        match local_verify_storage_kind == 2:\n"
        "                            -1:\n"
        "                                discard 0\n"
        "                            0:\n"
        "                                verifier_ok = 0\n"
        "                            1:\n"
        "                                verifier_ok = 0\n"
        "                    1:\n"
        "                        verifier_ok = 0\n"
        "                local_verify_remainder = local_verify_quotient\n"
        "                local_verify_quotient = local_verify_remainder / 2\n"
        "                local_verify_field = local_verify_remainder - local_verify_quotient * 2\n"
        "                match local_verify_field == 1:\n"
        "                    -1:\n"
        "                        discard 0\n"
        "                    0:\n"
        "                        verifier_ok = 0\n"
        "                    1:\n"
        "                        verifier_ok = 0\n"
        "                local_verify_remainder = local_verify_quotient\n"
        "                local_verify_quotient = local_verify_remainder / 366\n"
        "                local_verify_field = local_verify_remainder - local_verify_quotient * 366\n"
        "                match local_verify_field > 0:\n"
        "                    -1:\n"
        "                        match valid_type_name(local_verify_field - 1):\n"
        "                            -1:\n"
        "                                discard 0\n"
        "                            0:\n"
        "                                verifier_ok = 0\n"
        "                            1:\n"
        "                                verifier_ok = 0\n"
        "                    0:\n"
        "                        verifier_ok = 0\n"
        "                    1:\n"
        "                        verifier_ok = 0\n"
        "                local_verify_remainder = local_verify_quotient\n"
        "                local_verify_quotient = local_verify_remainder / 366\n"
        "                local_verify_field = local_verify_remainder - local_verify_quotient * 366\n"
        "                match local_verify_field > 0:\n"
        "                    -1:\n"
        "                        discard 0\n"
        "                    0:\n"
        "                        verifier_ok = 0\n"
        "                    1:\n"
        "                        verifier_ok = 0\n"
        "                local_verify_remainder = local_verify_quotient\n"
        "                mut local_verify_owner: i64 = local_verify_remainder - 1\n"
        "                match local_verify_owner >= 0:\n"
        "                    -1:\n"
        "                        match local_verify_owner < function_count:\n"
        "                            -1:\n"
        "                                discard 0\n"
        "                            0:\n"
        "                                verifier_ok = 0\n"
        "                            1:\n"
        "                                verifier_ok = 0\n"
        "                    0:\n"
        "                        verifier_ok = 0\n"
        "                    1:\n"
        "                        verifier_ok = 0\n"
        "                match local_verify_owner == local_verify_previous_owner:\n"
        "                    -1:\n"
        "                        discard 0\n"
        "                    0:\n"
        "                        local_verify_previous_owner = local_verify_owner\n"
        "                        local_verify_expected_ordinal = 0\n"
        "                    1:\n"
        "                        local_verify_previous_owner = local_verify_owner\n"
        "                        local_verify_expected_ordinal = 0\n"
        "                match local_verify_ordinal == local_verify_expected_ordinal:\n"
        "                    -1:\n"
        "                        local_verify_expected_ordinal += 1\n"
        "                    0:\n"
        "                        verifier_ok = 0\n"
        "                    1:\n"
        "                        verifier_ok = 0\n"
        "                local_verify_index += 1\n"
    )
    source = _replace_once(
        source,
        verifier_anchor,
        verifier + verifier_anchor,
        label="local metadata verifier",
    )

    required_markers = (
        f"mut ir_local_records: i64[{local_capacity}]",
        "local_capture_storage_kind = 2",
        "local_capture_extent = value",
        "64 + local_capture_index + 1",
        "ir_local_record_count == local_count",
        "local_verify_storage_kind",
        "local_verify_extent",
    )
    for marker in required_markers:
        if marker not in source:
            raise LocalCandidateError(f"local transform missing required marker: {marker}")
    return source


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameter-report", type=Path, default=DEFAULT_PARAMETER_REPORT)
    parser.add_argument("--capacity", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    canonical = SOURCE.read_text(encoding="utf-8")
    report = _load_report(args.parameter_report.resolve())
    parameter_source, _ = validate_parameter_prerequisite(report, canonical_source=canonical)
    candidate = transform_locals(parameter_source, local_capacity=args.capacity)
    destination = args.output.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(candidate, encoding="utf-8", newline="\n")
    print(f"PARAMETER_REPORT={args.parameter_report.resolve()}")
    print(f"LOCAL_CAPACITY={args.capacity}")
    print(f"PARAMETER_SOURCE_SHA256={_sha256(parameter_source.encode('utf-8'))}")
    print(f"LOCAL_CANDIDATE_SHA256={_sha256(candidate.encode('utf-8'))}")
    print(f"LOCAL_CANDIDATE_BYTES={len(candidate.encode('utf-8'))}")
    print("CANONICAL_SOURCE_MUTATED=False")
    print("STATUS=STATIC_PREFLIGHT_REQUIRED_BEFORE_NATIVE_QUALIFICATION")
    print(f"OUTPUT={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
