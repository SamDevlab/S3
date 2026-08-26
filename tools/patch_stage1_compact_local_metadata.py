"""Prepare a compact post-promotion Stage1 local-metadata candidate.

The candidate is deliberately non-promoting. It first applies the prepared
parameter semantic-value-ID transform, then adds a compact local metadata lane
that matches the current 68-slot parameter representation instead of the
historical packed 64-slot lane.

Local declarations are recognized from the existing 16-token ring at the final
``=`` token. This avoids the historical large declaration state machine:

    mut name : type =
    mut name : type [ extent ] =

A local semantic Value ID is implicit and needs no extra storage:
``parameter_count + global_local_record_slot``. Physical frame layout remains
emitter-owned. The candidate installs a fail-closed verifier requiring every
lexically counted ``mut`` local in the complete input to have a positive local
metadata record.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from tools.patch_stage1_parameter_semantic_value_ids import transform as transform_parameter_values


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
EXPECTED_SOURCE_SHA256 = "ec6bef92782fe253f4b1c1390d90f95017670a3cbb65497eff9dba12a2e7623c"
LOCAL_CAPACITY = 365
VALUE_CAPACITY = 1460


def _sha256_text(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _zero_array(size: int) -> str:
    return "[" + ", ".join("0" for _ in range(size)) + "]"


def _replace_once(source: str, old: str, new: str, *, label: str) -> str:
    observed = source.count(old)
    if observed != 1:
        raise ValueError(f"{label}: expected exactly one anchor, found {observed}")
    return source.replace(old, new, 1)


def transform(source: str) -> str:
    """Return the compact local candidate without mutating canonical source."""

    source_sha = _sha256_text(source)
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise ValueError(
            "source SHA does not match the promoted parameter checkpoint; "
            f"expected {EXPECTED_SOURCE_SHA256}, got {source_sha}"
        )

    candidate = transform_parameter_values(source)
    if "mut ir_local_records:" in candidate:
        raise ValueError("local metadata lane already exists")
    if "ir_return_operand[current_function] = parameter_scan" not in candidate:
        raise ValueError("parameter semantic-value prerequisite is missing")

    parameter_decl_anchor = "    mut ir_parameter_type: i64[68] = "
    parameter_decl_index = candidate.find(parameter_decl_anchor)
    if parameter_decl_index < 0:
        raise ValueError("promoted parameter metadata anchor not found")
    parameter_decl_end = candidate.find("\n", parameter_decl_index)
    if parameter_decl_end < 0:
        raise ValueError("parameter metadata declaration line is unterminated")
    local_decl = (
        f"    mut ir_local_records: i64[{LOCAL_CAPACITY}] = {_zero_array(LOCAL_CAPACITY)}\n"
    )
    candidate = (
        candidate[: parameter_decl_end + 1]
        + local_decl
        + candidate[parameter_decl_end + 1 :]
    )

    previous_anchor = "    mut previous_start: i64 = 0\n"
    local_state = (
        previous_anchor
        + "    mut local_decl_kind: tryte = 0\n"
        + "    mut local_decl_name: i64 = 0\n"
        + "    mut local_decl_type: i64 = 0\n"
        + "    mut local_decl_extent: i64 = 1\n"
        + "    mut local_ordinal_owner: i64 = -1\n"
        + "    mut local_ordinal: i64 = 0\n"
    )
    candidate = _replace_once(
        candidate,
        previous_anchor,
        local_state,
        label="compact local capture state",
    )

    history_anchor = (
        "        previous_kind = kind\n"
        "        previous_value = value\n"
        "        previous_start = actual_start\n"
    )
    capture = (
        "        local_decl_kind = 0\n"
        "        match kind == 4:\n"
        "            -1:\n"
        "                match value == 5:\n"
        "                    -1:\n"
        "                        mut local_slot_2: i64 = slot - 2\n"
        "                        while local_slot_2 < 0:\n"
        "                            local_slot_2 += 16\n"
        "                        mut local_slot_3: i64 = slot - 3\n"
        "                        while local_slot_3 < 0:\n"
        "                            local_slot_3 += 16\n"
        "                        mut local_slot_4: i64 = slot - 4\n"
        "                        while local_slot_4 < 0:\n"
        "                            local_slot_4 += 16\n"
        "                        mut local_slot_5: i64 = slot - 5\n"
        "                        while local_slot_5 < 0:\n"
        "                            local_slot_5 += 16\n"
        "                        mut local_slot_6: i64 = slot - 6\n"
        "                        while local_slot_6 < 0:\n"
        "                            local_slot_6 += 16\n"
        "                        mut local_slot_7: i64 = slot - 7\n"
        "                        while local_slot_7 < 0:\n"
        "                            local_slot_7 += 16\n"
        "                        match previous_kind == 1:\n"
        "                            -1:\n"
        "                                match token_kind[local_slot_2] == 4:\n"
        "                                    -1:\n"
        "                                        match token_value[local_slot_2] == 3:\n"
        "                                            -1:\n"
        "                                                match token_kind[local_slot_3] == 1:\n"
        "                                                    -1:\n"
        "                                                        match token_kind[local_slot_4] == 1:\n"
        "                                                            -1:\n"
        "                                                                match token_value[local_slot_4] == 87:\n"
        "                                                                    -1:\n"
        "                                                                        local_decl_kind = 1\n"
        "                                                                        local_decl_name = token_value[local_slot_3]\n"
        "                                                                        local_decl_type = previous_value\n"
        "                                                                        local_decl_extent = 1\n"
        "                                                                    0:\n"
        "                                                                        discard 0\n"
        "                                                                    1:\n"
        "                                                                        discard 0\n"
        "                                                            0:\n"
        "                                                                discard 0\n"
        "                                                            1:\n"
        "                                                                discard 0\n"
        "                                                    0:\n"
        "                                                        discard 0\n"
        "                                                    1:\n"
        "                                                        discard 0\n"
        "                                            0:\n"
        "                                                discard 0\n"
        "                                            1:\n"
        "                                                discard 0\n"
        "                                    0:\n"
        "                                        discard 0\n"
        "                                    1:\n"
        "                                        discard 0\n"
        "                            0:\n"
        "                                discard 0\n"
        "                            1:\n"
        "                                discard 0\n"
        "                        match previous_kind == 4:\n"
        "                            -1:\n"
        "                                match previous_value == 11:\n"
        "                                    -1:\n"
        "                                        match token_kind[local_slot_2] == 2:\n"
        "                                            -1:\n"
        "                                                match token_kind[local_slot_3] == 4:\n"
        "                                                    -1:\n"
        "                                                        match token_value[local_slot_3] == 10:\n"
        "                                                            -1:\n"
        "                                                                match token_kind[local_slot_4] == 1:\n"
        "                                                                    -1:\n"
        "                                                                        match token_kind[local_slot_5] == 4:\n"
        "                                                                            -1:\n"
        "                                                                                match token_value[local_slot_5] == 3:\n"
        "                                                                                    -1:\n"
        "                                                                                        match token_kind[local_slot_6] == 1:\n"
        "                                                                                            -1:\n"
        "                                                                                                match token_kind[local_slot_7] == 1:\n"
        "                                                                                                    -1:\n"
        "                                                                                                        match token_value[local_slot_7] == 87:\n"
        "                                                                                                            -1:\n"
        "                                                                                                                local_decl_kind = 2\n"
        "                                                                                                                local_decl_name = token_value[local_slot_6]\n"
        "                                                                                                                local_decl_type = token_value[local_slot_4]\n"
        "                                                                                                                local_decl_extent = token_value[local_slot_2]\n"
        "                                                                                                            0:\n"
        "                                                                                                                discard 0\n"
        "                                                                                                            1:\n"
        "                                                                                                                discard 0\n"
        "                                                                                                    0:\n"
        "                                                                                                        discard 0\n"
        "                                                                                                    1:\n"
        "                                                                                                        discard 0\n"
        "                                                                                            0:\n"
        "                                                                                                discard 0\n"
        "                                                                                            1:\n"
        "                                                                                                discard 0\n"
        "                                                                                    0:\n"
        "                                                                                        discard 0\n"
        "                                                                                    1:\n"
        "                                                                                        discard 0\n"
        "                                                                            0:\n"
        "                                                                                discard 0\n"
        "                                                                            1:\n"
        "                                                                                discard 0\n"
        "                                                                    0:\n"
        "                                                                        discard 0\n"
        "                                                                    1:\n"
        "                                                                        discard 0\n"
        "                                                            0:\n"
        "                                                                discard 0\n"
        "                                                            1:\n"
        "                                                                discard 0\n"
        "                                                    0:\n"
        "                                                        discard 0\n"
        "                                                    1:\n"
        "                                                        discard 0\n"
        "                                            0:\n"
        "                                                discard 0\n"
        "                                            1:\n"
        "                                                discard 0\n"
        "                                    0:\n"
        "                                        discard 0\n"
        "                                    1:\n"
        "                                        discard 0\n"
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
        "        match local_decl_kind > 0:\n"
        "            -1:\n"
        "                match current_function >= 0:\n"
        "                    -1:\n"
        "                        match current_function < 64:\n"
        "                            -1:\n"
        "                                match local_decl_name >= 0:\n"
        "                                    -1:\n"
        "                                        match local_decl_name < 365:\n"
        "                                            -1:\n"
        "                                                match valid_type_name(local_decl_type):\n"
        "                                                    -1:\n"
        "                                                        match local_decl_extent > 0:\n"
        "                                                            -1:\n"
        "                                                                match local_decl_extent < 1461:\n"
        "                                                                    -1:\n"
        f"                                                                        match ir_local_record_count < {LOCAL_CAPACITY}:\n"
        "                                                                            -1:\n"
        "                                                                                match local_ordinal_owner == current_function:\n"
        "                                                                                    -1:\n"
        "                                                                                        discard 0\n"
        "                                                                                    0:\n"
        "                                                                                        local_ordinal_owner = current_function\n"
        "                                                                                        local_ordinal = 0\n"
        "                                                                                    1:\n"
        "                                                                                        local_ordinal_owner = current_function\n"
        "                                                                                        local_ordinal = 0\n"
        "                                                                                match local_ordinal < 365:\n"
        "                                                                                    -1:\n"
        "                                                                                        ir_local_records[ir_local_record_count] = (((((current_function + 1) * 366 + (local_decl_name + 1)) * 366 + (local_decl_type + 1)) * 3 + local_decl_kind) * 366 + (local_ordinal + 1)) * 1461 + local_decl_extent\n"
        "                                                                                        ir_local_record_count += 1\n"
        "                                                                                        local_ordinal += 1\n"
        "                                                                                    0:\n"
        "                                                                                        ir_capacity_ok = 0\n"
        "                                                                                    1:\n"
        "                                                                                        ir_capacity_ok = 0\n"
        "                                                                            0:\n"
        "                                                                                ir_capacity_ok = 0\n"
        "                                                                            1:\n"
        "                                                                                ir_capacity_ok = 0\n"
        "                                                                    0:\n"
        "                                                                        ir_capacity_ok = 0\n"
        "                                                                    1:\n"
        "                                                                        ir_capacity_ok = 0\n"
        "                                                            0:\n"
        "                                                                ir_capacity_ok = 0\n"
        "                                                            1:\n"
        "                                                                ir_capacity_ok = 0\n"
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
        + history_anchor
    )
    candidate = _replace_once(
        candidate,
        history_anchor,
        capture,
        label="compact rolling-window local capture",
    )

    pipeline_anchor = "    mut pipeline_ok: trit = -1\n"
    verifier = (
        "    match ir_local_record_count == local_count:\n"
        "        -1:\n"
        f"            match parameter_count + ir_local_record_count < {VALUE_CAPACITY + 1}:\n"
        "                -1:\n"
        "                    mut local_verify_index: i64 = 0\n"
        "                    while local_verify_index < ir_local_record_count:\n"
        "                        match ir_local_records[local_verify_index] > 0:\n"
        "                            -1:\n"
        "                                discard 0\n"
        "                            0:\n"
        "                                verifier_ok = 0\n"
        "                            1:\n"
        "                                verifier_ok = 0\n"
        "                        local_verify_index += 1\n"
        "                0:\n"
        "                    verifier_ok = 0\n"
        "                1:\n"
        "                    verifier_ok = 0\n"
        "        0:\n"
        "            verifier_ok = 0\n"
        "        1:\n"
        "            verifier_ok = 0\n"
        + pipeline_anchor
    )
    candidate = _replace_once(
        candidate,
        pipeline_anchor,
        verifier,
        label="compact local verifier",
    )

    required = (
        f"mut ir_local_records: i64[{LOCAL_CAPACITY}]",
        "ir_return_operand[current_function] = parameter_scan",
        "local_decl_kind = 1",
        "local_decl_kind = 2",
        "ir_local_records[ir_local_record_count] =",
        "match ir_local_record_count == local_count:",
        f"match parameter_count + ir_local_record_count < {VALUE_CAPACITY + 1}:",
        "mut local_verify_index: i64 = 0",
    )
    for marker in required:
        if marker not in candidate:
            raise ValueError(f"candidate missing required marker: {marker}")

    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source_path = args.source.resolve()
    baseline = source_path.read_text(encoding="utf-8")
    candidate = transform(baseline)
    destination = (
        args.output.resolve()
        if args.output is not None
        else source_path.with_suffix(".compact-local-candidate.s3")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(candidate, encoding="utf-8", newline="\n")

    print(f"SOURCE_BEFORE_SHA256={_sha256_text(baseline)}")
    print(f"SOURCE_AFTER_SHA256={_sha256_text(candidate)}")
    print(f"SOURCE_BEFORE_BYTES={len(baseline.encode('utf-8'))}")
    print(f"SOURCE_AFTER_BYTES={len(candidate.encode('utf-8'))}")
    print(f"LOCAL_CAPACITY_BOUND={LOCAL_CAPACITY}")
    print("LOCAL_CAPTURE=BOUNDED_TOKEN_RING_SUFFIX")
    print("LOCAL_VALUE_ID_RULE=parameter_count+global_local_record_slot")
    print("CANONICAL_SOURCE_MUTATED=NO")
    print("STATUS=NATIVE_QUALIFICATION_REQUIRED")
    print(f"OUTPUT={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
