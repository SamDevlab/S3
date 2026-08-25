"""Build the parameter-metadata phase of Stage1 codegen IR v2.

This is a candidate-source transform, not a canonical promotion tool. It expects
that the compaction-first transform has already removed the redundant discard
event, then adds a single packed i64[64] parameter lane. Packing all five
required fields into one lane avoids the self-bootstrap value-capacity cost of
five separately initialized arrays.

Packed base-1000 layout (high to low):
    owner+1, name_identity+1, type_id+1, abi_index+1, value_id+1

Parameter value IDs reserve the deterministic range [0, parameter_count). The
later unified-value phase must preserve that reservation or explicitly migrate
it under a separately qualified transform.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from tools.patch_stage1_codegen_ir_v2_capacity import (
    BASELINE_SOURCE_SHA256,
    transform as compact_discard_events,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"

PARAMETER_CAPACITY = 64
PACK_OWNER_BASE = 1_000_000_000_000
PACK_NAME_BASE = 1_000_000_000
PACK_TYPE_BASE = 1_000_000
PACK_ABI_BASE = 1_000


def _sha256_text(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _replace_once(source: str, old: str, new: str, *, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected exactly one anchor, found {count}")
    return source.replace(old, new, 1)


def _zero_array(size: int) -> str:
    return "[" + ", ".join("0" for _ in range(size)) + "]"


def transform_parameters(compacted_source: str) -> str:
    """Add packed parameter metadata and fail-closed verifier checks."""

    if "ir_ast_event_opcode = 5" in compacted_source:
        raise ValueError("parameter IR-v2 transform requires discard-event compaction first")
    if "mut ir_parameter_records:" in compacted_source:
        raise ValueError("parameter IR-v2 lane already exists")

    source = compacted_source

    return_type_anchor = "    mut ir_function_return_type: tryte[64] = "
    parameter_decl = (
        "    mut ir_parameter_records: i64[64] = "
        + _zero_array(PARAMETER_CAPACITY)
        + "\n"
    )
    source = _replace_once(
        source,
        return_type_anchor,
        parameter_decl + return_type_anchor,
        label="parameter-record declaration",
    )

    state_anchor = "    mut signature_expected: trit = 0\n"
    state_insert = (
        state_anchor
        + "    mut signature_function_active: trit = 0\n"
        + "    mut pending_parameter_index: i64 = -1\n"
        + "    mut pending_parameter_name: i64 = 0\n"
    )
    source = _replace_once(
        source,
        state_anchor,
        state_insert,
        label="parameter parser state",
    )

    signature_open_old = (
        "                                match signature_expected == -1:\n"
        "                                    -1:\n"
        "                                        signature_paren_depth = 1\n"
        "                                        signature_expected = 0\n"
    )
    signature_open_new = (
        "                                match signature_expected == -1:\n"
        "                                    -1:\n"
        "                                        signature_paren_depth = 1\n"
        "                                        signature_function_active = -1\n"
        "                                        signature_expected = 0\n"
    )
    source = _replace_once(
        source,
        signature_open_old,
        signature_open_new,
        label="function-signature open",
    )

    parameter_count_old = (
        "                                                match parameter_count < 64:\n"
        "                                                    -1:\n"
        "                                                        parameter_count += 1\n"
        "                                                    0:\n"
        "                                                        ir_capacity_ok = 0\n"
        "                                                    1:\n"
        "                                                        ir_capacity_ok = 0\n"
    )
    parameter_count_new = (
        "                                                match parameter_count < 64:\n"
        "                                                    -1:\n"
        "                                                        pending_parameter_index = parameter_count\n"
        "                                                        pending_parameter_name = previous_value\n"
        "                                                        parameter_count += 1\n"
        "                                                    0:\n"
        "                                                        ir_capacity_ok = 0\n"
        "                                                    1:\n"
        "                                                        ir_capacity_ok = 0\n"
    )
    source = _replace_once(
        source,
        parameter_count_old,
        parameter_count_new,
        label="parameter declaration capture",
    )

    # Match the outer argument-capture block as a complete line pair. A bare
    # indentation prefix also occurs in nested match branches and is not a
    # unique transform boundary.
    type_capture_anchor = (
        "        argument_possible = 0\n"
        "        match kind == 1:\n"
    )
    type_capture = (
        "        match pending_parameter_index >= 0:\n"
        "            -1:\n"
        "                match kind == 1:\n"
        "                    -1:\n"
        "                        match signature_function_active == -1:\n"
        "                            -1:\n"
        "                                match current_function >= 0:\n"
        "                                    -1:\n"
        "                                        ir_parameter_records[pending_parameter_index] = (current_function + 1) * 1000000000000 + (pending_parameter_name + 1) * 1000000000 + (value + 1) * 1000000 + (pending_parameter_index - ir_function_param_start[current_function] + 1) * 1000 + (pending_parameter_index + 1)\n"
        "                                        pending_parameter_index = -1\n"
        "                                    0:\n"
        "                                        ir_capacity_ok = 0\n"
        "                                    1:\n"
        "                                        ir_capacity_ok = 0\n"
        "                            0:\n"
        "                                discard 0\n"
        "                            1:\n"
        "                                discard 0\n"
        "                    0:\n"
        "                        discard 0\n"
        "                    1:\n"
        "                        discard 0\n"
        "            0:\n"
        "                discard 0\n"
        "            1:\n"
        "                discard 0\n"
        + type_capture_anchor
    )
    source = _replace_once(
        source,
        type_capture_anchor,
        type_capture,
        label="parameter type/value-id capture",
    )

    signature_close_old = (
        "                        match value == 2:\n"
        "                            -1:\n"
        "                                signature_paren_depth = 0\n"
    )
    signature_close_new = (
        "                        match value == 2:\n"
        "                            -1:\n"
        "                                match signature_function_active == -1:\n"
        "                                    -1:\n"
        "                                        match current_function >= 0:\n"
        "                                            -1:\n"
        "                                                ir_function_param_count[current_function] = parameter_count - ir_function_param_start[current_function]\n"
        "                                            0:\n"
        "                                                ir_capacity_ok = 0\n"
        "                                            1:\n"
        "                                                ir_capacity_ok = 0\n"
        "                                        signature_function_active = 0\n"
        "                                    0:\n"
        "                                        discard 0\n"
        "                                    1:\n"
        "                                        discard 0\n"
        "                                signature_paren_depth = 0\n"
    )
    source = _replace_once(
        source,
        signature_close_old,
        signature_close_new,
        label="function-signature close",
    )

    verifier_anchor = "            mut verify_index: i64 = 0\n"
    verifier = (
        "            mut parameter_verify_index: i64 = 0\n"
        "            while parameter_verify_index < parameter_count:\n"
        "                mut parameter_verify_record: i64 = ir_parameter_records[parameter_verify_index]\n"
        "                match parameter_verify_record > 0:\n"
        "                    -1:\n"
        "                        mut parameter_verify_owner_encoded: i64 = parameter_verify_record / 1000000000000\n"
        "                        mut parameter_verify_remainder: i64 = parameter_verify_record - parameter_verify_owner_encoded * 1000000000000\n"
        "                        mut parameter_verify_name_encoded: i64 = parameter_verify_remainder / 1000000000\n"
        "                        parameter_verify_remainder = parameter_verify_remainder - parameter_verify_name_encoded * 1000000000\n"
        "                        mut parameter_verify_type_encoded: i64 = parameter_verify_remainder / 1000000\n"
        "                        parameter_verify_remainder = parameter_verify_remainder - parameter_verify_type_encoded * 1000000\n"
        "                        mut parameter_verify_abi_encoded: i64 = parameter_verify_remainder / 1000\n"
        "                        mut parameter_verify_value_encoded: i64 = parameter_verify_remainder - parameter_verify_abi_encoded * 1000\n"
        "                        mut parameter_verify_owner: i64 = parameter_verify_owner_encoded - 1\n"
        "                        mut parameter_verify_name: i64 = parameter_verify_name_encoded - 1\n"
        "                        mut parameter_verify_type: i64 = parameter_verify_type_encoded - 1\n"
        "                        mut parameter_verify_abi: i64 = parameter_verify_abi_encoded - 1\n"
        "                        mut parameter_verify_value: i64 = parameter_verify_value_encoded - 1\n"
        "                        match parameter_verify_owner >= 0:\n"
        "                            -1:\n"
        "                                match parameter_verify_owner < function_count:\n"
        "                                    -1:\n"
        "                                        discard 0\n"
        "                                    0:\n"
        "                                        verifier_ok = 0\n"
        "                                    1:\n"
        "                                        verifier_ok = 0\n"
        "                            0:\n"
        "                                verifier_ok = 0\n"
        "                            1:\n"
        "                                verifier_ok = 0\n"
        "                        match parameter_verify_name >= 0:\n"
        "                            -1:\n"
        "                                match parameter_verify_name < 365:\n"
        "                                    -1:\n"
        "                                        discard 0\n"
        "                                    0:\n"
        "                                        verifier_ok = 0\n"
        "                                    1:\n"
        "                                        verifier_ok = 0\n"
        "                            0:\n"
        "                                verifier_ok = 0\n"
        "                            1:\n"
        "                                verifier_ok = 0\n"
        "                        match valid_type_name(parameter_verify_type):\n"
        "                            -1:\n"
        "                                discard 0\n"
        "                            0:\n"
        "                                verifier_ok = 0\n"
        "                            1:\n"
        "                                verifier_ok = 0\n"
        "                        match parameter_verify_value == parameter_verify_index:\n"
        "                            -1:\n"
        "                                discard 0\n"
        "                            0:\n"
        "                                verifier_ok = 0\n"
        "                            1:\n"
        "                                verifier_ok = 0\n"
        "                        match parameter_verify_owner >= 0:\n"
        "                            -1:\n"
        "                                match parameter_verify_owner < function_count:\n"
        "                                    -1:\n"
        "                                        match parameter_verify_index >= ir_function_param_start[parameter_verify_owner]:\n"
        "                                            -1:\n"
        "                                                match parameter_verify_index < ir_function_param_start[parameter_verify_owner] + ir_function_param_count[parameter_verify_owner]:\n"
        "                                                    -1:\n"
        "                                                        match parameter_verify_abi == parameter_verify_index - ir_function_param_start[parameter_verify_owner]:\n"
        "                                                            -1:\n"
        "                                                                discard 0\n"
        "                                                            0:\n"
        "                                                                verifier_ok = 0\n"
        "                                                            1:\n"
        "                                                                verifier_ok = 0\n"
        "                                                    0:\n"
        "                                                        verifier_ok = 0\n"
        "                                                    1:\n"
        "                                                        verifier_ok = 0\n"
        "                                            0:\n"
        "                                                verifier_ok = 0\n"
        "                                            1:\n"
        "                                                verifier_ok = 0\n"
        "                                    0:\n"
        "                                        verifier_ok = 0\n"
        "                                    1:\n"
        "                                        verifier_ok = 0\n"
        "                            0:\n"
        "                                verifier_ok = 0\n"
        "                            1:\n"
        "                                verifier_ok = 0\n"
        "                    0:\n"
        "                        verifier_ok = 0\n"
        "                    1:\n"
        "                        verifier_ok = 0\n"
        "                parameter_verify_index += 1\n"
        + verifier_anchor
    )
    source = _replace_once(
        source,
        verifier_anchor,
        verifier,
        label="parameter metadata verifier",
    )

    required = (
        "mut ir_parameter_records: i64[64]",
        "pending_parameter_index = parameter_count",
        "ir_function_param_count[current_function] = parameter_count - ir_function_param_start[current_function]",
        "parameter_verify_value == parameter_verify_index",
    )
    for marker in required:
        if marker not in source:
            raise ValueError(f"parameter IR-v2 transform missing required marker: {marker}")

    return source


def build_candidate(baseline_source: str) -> str:
    """Apply compaction then the parameter-metadata phase deterministically."""

    compacted = compact_discard_events(baseline_source)
    return transform_parameters(compacted)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source_path = args.source.resolve()
    baseline = source_path.read_text(encoding="utf-8")
    before_sha = _sha256_text(baseline)
    if before_sha != BASELINE_SOURCE_SHA256:
        parser.error(
            "source SHA does not match the qualified pre-IR-v2 baseline; "
            "parameter candidate construction is intentionally baseline-locked"
        )

    candidate = build_candidate(baseline)
    destination = (
        args.output.resolve()
        if args.output is not None
        else source_path.with_suffix(".ir-v2-parameters.s3")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(candidate, encoding="utf-8", newline="\n")

    print(f"SOURCE_BEFORE_SHA256={before_sha}")
    print(f"SOURCE_AFTER_SHA256={_sha256_text(candidate)}")
    print("TRANSFORMS=DROP_REDUNDANT_DISCARD_KEYWORD_EVENT,ADD_PACKED_PARAMETER_IR_V2")
    print("PARAMETER_RECORD_CAPACITY=64")
    print("PARAMETER_RECORD_STORAGE=ONE_I64_PER_PARAMETER")
    print("PARAMETER_VALUE_ID_RESERVATION=0..parameter_count-1")
    print("STATUS=NATIVE_QUALIFICATION_REQUIRED")
    print(f"OUTPUT={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
