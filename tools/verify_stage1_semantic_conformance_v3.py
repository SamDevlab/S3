"""Strict semantic conformance gate for audited S3IR2 v3.

S1-S4 compare semantic meaning while allowing producer-local numeric IDs to differ.
Canonical ID assignment and byte identity are intentionally deferred to S1.6.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.stage1_semantic_stream_v3 import (
    BINDING_TARGET_CODES,
    build_model_bytes,
    encode_model,
    parse_stream,
    verify_stream,
)


class ConformanceV3Error(ValueError):
    pass


def _by_tag(parsed: dict[str, Any], tag: str) -> list[list[int]]:
    return [record["fields"] for record in parsed["records"] if record["tag"] == tag]


def _index_unique(rows: list[list[int]], key_fn, label: str) -> tuple[dict[Any, list[int]], list[str]]:
    result: dict[Any, list[int]] = {}
    errors: list[str] = []
    for row in rows:
        key = key_fn(row)
        if key in result:
            errors.append(f"duplicate {label} semantic key {key}")
        result[key] = row
    return result, errors


def verify_conformance_bytes(raw_source: bytes, candidate_stream: str) -> dict[str, Any]:
    model = build_model_bytes(raw_source)
    expected = parse_stream(encode_model(model))
    candidate = parse_stream(candidate_stream)
    candidate_internal = verify_stream(candidate)
    errors: list[str] = []

    if candidate_internal["status"] != "PASS":
        errors.append("candidate stream fails internal S3IR2 v3 verification")
        errors.extend(str(item) for item in candidate_internal["errors"][:25])

    expected_f = _by_tag(expected, "F")
    candidate_f = _by_tag(candidate, "F")
    if len(expected_f) != len(candidate_f):
        errors.append(
            f"function count mismatch: expected {len(expected_f)}, got {len(candidate_f)}"
        )
    function_map: dict[int, int] = {}
    candidate_f_by_anchor, duplicate_errors = _index_unique(
        candidate_f, lambda row: (row[2], row[3]), "function"
    )
    errors.extend(duplicate_errors)
    for exp in expected_f:
        got = candidate_f_by_anchor.get((exp[2], exp[3]))
        if got is None:
            errors.append(f"missing function at source anchor {exp[2]}:{exp[3]}")
            continue
        function_map[exp[0]] = got[0]
        if (exp[1], exp[4], exp[5]) != (got[1], got[4], got[5]):
            errors.append(f"function metadata mismatch at source anchor {exp[2]}")

    expected_b = _by_tag(expected, "B")
    candidate_b = _by_tag(candidate, "B")
    if len(expected_b) != len(candidate_b):
        errors.append(
            f"block count mismatch: expected {len(expected_b)}, got {len(candidate_b)}"
        )
    candidate_b_by_key, duplicate_errors = _index_unique(
        candidate_b, lambda row: (row[0], row[2]), "block"
    )
    errors.extend(duplicate_errors)
    block_map: dict[tuple[int, int], tuple[int, int]] = {}
    for exp in expected_b:
        candidate_owner = function_map.get(exp[0])
        if candidate_owner is None:
            continue
        got = candidate_b_by_key.get((candidate_owner, exp[2]))
        if got is None:
            errors.append(
                f"missing block ordinal {exp[2]} for expected function {exp[0]}"
            )
            continue
        block_map[(exp[0], exp[1])] = (got[0], got[1])
        if exp[3] != got[3]:
            errors.append(
                f"block instruction count mismatch for {exp[0]}:{exp[1]}"
            )

    expected_v = _by_tag(expected, "V")
    candidate_v = _by_tag(candidate, "V")
    expected_v_by_id = {row[0]: row for row in expected_v}
    candidate_v_by_id = {row[0]: row for row in candidate_v}
    if len(expected_v) != len(candidate_v):
        errors.append(
            f"value count mismatch: expected {len(expected_v)}, got {len(candidate_v)}"
        )
    value_map: dict[int, int] = {}

    expected_m = _by_tag(expected, "M")
    candidate_m = _by_tag(candidate, "M")
    if len(expected_m) != len(candidate_m):
        errors.append(
            f"storage count mismatch: expected {len(expected_m)}, got {len(candidate_m)}"
        )
    storage_map: dict[tuple[int, int], tuple[int, int]] = {}

    expected_d = _by_tag(expected, "D")
    candidate_d = _by_tag(candidate, "D")
    if len(expected_d) != len(candidate_d):
        errors.append(
            f"binding count mismatch: expected {len(expected_d)}, got {len(candidate_d)}"
        )
    candidate_d_index, duplicate_errors = _index_unique(
        candidate_d,
        lambda row: (row[1], row[4], row[5]),
        "binding",
    )
    errors.extend(duplicate_errors)
    binding_map: dict[int, int] = {}
    for exp in expected_d:
        candidate_owner = function_map.get(exp[1])
        if candidate_owner is None:
            continue
        got = candidate_d_index.get((candidate_owner, exp[4], exp[5]))
        if got is None:
            errors.append(
                f"missing binding at source anchor {exp[4]}:{exp[5]} in function {exp[1]}"
            )
            continue
        binding_map[exp[0]] = got[0]
        if (exp[2], exp[3], exp[6], exp[7]) != (got[2], got[3], got[6], got[7]):
            errors.append(
                f"binding semantic metadata mismatch at source anchor {exp[4]}"
            )
            continue
        if exp[7] == BINDING_TARGET_CODES["value"]:
            value_map[exp[8]] = got[8]
        elif exp[7] == BINDING_TARGET_CODES["storage"]:
            storage_map[(exp[1], exp[8])] = (got[1], got[8])

    candidate_m_index: dict[tuple[int, int, int, int, int], list[list[int]]] = {}
    for row in candidate_m:
        key = (row[0], row[2], row[3], row[4], row[5])
        candidate_m_index.setdefault(key, []).append(row)
    for exp in expected_m:
        key = (
            function_map.get(exp[0], -1),
            exp[2],
            exp[3],
            exp[4],
            exp[5],
        )
        matches = candidate_m_index.get(key, [])
        if not matches:
            errors.append(
                f"missing storage equivalent for {exp[0]}:{exp[1]} at anchor {exp[5]}"
            )
            continue
        got = matches.pop(0)
        existing = storage_map.get((exp[0], exp[1]))
        mapped = (got[0], got[1])
        if existing is not None and existing != mapped:
            errors.append(
                f"binding/storage mapping disagrees for {exp[0]}:{exp[1]}"
            )
        storage_map[(exp[0], exp[1])] = mapped

    expected_i = _by_tag(expected, "I")
    candidate_i = _by_tag(candidate, "I")
    if len(expected_i) != len(candidate_i):
        errors.append(
            f"instruction count mismatch: expected {len(expected_i)}, got {len(candidate_i)}"
        )
    candidate_i_index, duplicate_errors = _index_unique(
        candidate_i, lambda row: (row[1], row[2], row[3]), "instruction"
    )
    errors.extend(duplicate_errors)
    instruction_map: dict[int, int] = {}
    for exp in expected_i:
        mapped_block = block_map.get((exp[1], exp[2]))
        if mapped_block is None:
            continue
        got = candidate_i_index.get((mapped_block[0], mapped_block[1], exp[3]))
        if got is None:
            errors.append(
                f"missing instruction at {exp[1]}:{exp[2]} ordinal {exp[3]}"
            )
            continue
        instruction_map[exp[0]] = got[0]
        if (exp[4], exp[5], exp[6], exp[8]) != (got[4], got[5], got[6], got[8]):
            errors.append(f"instruction {exp[0]} semantic shape/immediate mismatch")
        if exp[7] < 0:
            if got[7] >= 0:
                errors.append(f"instruction {exp[0]} has unexpected storage operand")
        else:
            mapped_storage = storage_map.get((exp[1], exp[7]))
            if mapped_storage is None or got[7] != mapped_storage[1]:
                errors.append(f"instruction {exp[0]} storage target mismatch")

    expected_r = _by_tag(expected, "R")
    candidate_r = _by_tag(candidate, "R")
    expected_r_index: dict[int, list[list[int]]] = {}
    candidate_r_index: dict[int, list[list[int]]] = {}
    for row in expected_r:
        expected_r_index.setdefault(row[0], []).append(row)
    for row in candidate_r:
        candidate_r_index.setdefault(row[0], []).append(row)
    for expected_iid, candidate_iid in instruction_map.items():
        exp_rows = sorted(expected_r_index.get(expected_iid, []), key=lambda row: row[1])
        got_rows = sorted(candidate_r_index.get(candidate_iid, []), key=lambda row: row[1])
        if len(exp_rows) != len(got_rows):
            errors.append(f"result count mismatch for instruction {expected_iid}")
        for exp, got in zip(exp_rows, got_rows):
            if exp[1] != got[1]:
                errors.append(f"result ordinal mismatch for instruction {expected_iid}")
            value_map[exp[2]] = got[2]

    if len(value_map) != len(expected_v):
        missing = sorted(set(expected_v_by_id) - set(value_map))
        errors.append(f"unmapped expected values: {missing[:20]}")

    for expected_id, candidate_id in value_map.items():
        exp = expected_v_by_id.get(expected_id)
        got = candidate_v_by_id.get(candidate_id)
        if exp is None or got is None:
            errors.append(f"mapped value missing: {expected_id}->{candidate_id}")
            continue
        mapped_owner = function_map.get(exp[1])
        if (mapped_owner, exp[2], exp[3], exp[6]) != (
            got[1],
            got[2],
            got[3],
            got[6],
        ):
            errors.append(
                f"mapped value semantic metadata mismatch: {expected_id}->{candidate_id}"
            )
        if exp[4] >= 0 and (exp[4], exp[5]) != (got[4], got[5]):
            errors.append(
                f"mapped value source provenance mismatch: {expected_id}->{candidate_id}"
            )

    candidate_o_set = {(row[0], row[1], row[2]) for row in _by_tag(candidate, "O")}
    for exp in _by_tag(expected, "O"):
        mapped_instruction = instruction_map.get(exp[0])
        mapped_value = value_map.get(exp[2])
        if (
            mapped_instruction is None
            or mapped_value is None
            or (mapped_instruction, exp[1], mapped_value) not in candidate_o_set
        ):
            errors.append(f"missing mapped operand edge for expected {exp}")

    candidate_r_set = {(row[0], row[1], row[2]) for row in candidate_r}
    for exp in expected_r:
        mapped_instruction = instruction_map.get(exp[0])
        mapped_value = value_map.get(exp[2])
        if (
            mapped_instruction is None
            or mapped_value is None
            or (mapped_instruction, exp[1], mapped_value) not in candidate_r_set
        ):
            errors.append(f"missing mapped result edge for expected {exp}")

    expected_c = _by_tag(expected, "C")
    candidate_c_by_iid = {row[0]: row for row in _by_tag(candidate, "C")}
    for exp in expected_c:
        mapped_instruction = instruction_map.get(exp[0])
        got = candidate_c_by_iid.get(mapped_instruction) if mapped_instruction is not None else None
        if got is None:
            errors.append(f"missing call for instruction {exp[0]}")
            continue
        mapped_callee = function_map.get(exp[2], -1) if exp[2] >= 0 else -1
        if (exp[1], mapped_callee, exp[3], exp[4], exp[5], exp[6]) != (
            got[1],
            got[2],
            got[3],
            got[4],
            got[5],
            got[6],
        ):
            errors.append(f"call semantic metadata mismatch for instruction {exp[0]}")

    candidate_a_set = {(row[0], row[1], row[2]) for row in _by_tag(candidate, "A")}
    for exp in _by_tag(expected, "A"):
        mapped_instruction = instruction_map.get(exp[0])
        mapped_value = value_map.get(exp[2])
        if (
            mapped_instruction is None
            or mapped_value is None
            or (mapped_instruction, exp[1], mapped_value) not in candidate_a_set
        ):
            errors.append(f"missing mapped call argument for expected {exp}")

    candidate_t_by_iid = {row[0]: row for row in _by_tag(candidate, "T")}
    expected_instruction_owner = {row[0]: (row[1], row[2]) for row in expected_i}
    for exp in _by_tag(expected, "T"):
        mapped_instruction = instruction_map.get(exp[0])
        got = candidate_t_by_iid.get(mapped_instruction) if mapped_instruction is not None else None
        if got is None:
            errors.append(f"missing terminator for instruction {exp[0]}")
            continue
        if exp[1] != got[1]:
            errors.append(f"terminator kind mismatch for instruction {exp[0]}")
        for index in (2, 6):
            expected_value = exp[index]
            mapped_value = value_map.get(expected_value, -1) if expected_value >= 0 else -1
            if got[index] != mapped_value:
                errors.append(
                    f"terminator value mismatch for instruction {exp[0]} field {index}"
                )
        owner = expected_instruction_owner.get(exp[0])
        if owner is None:
            continue
        for index in (3, 4, 5):
            target = exp[index]
            if target < 0:
                if got[index] >= 0:
                    errors.append(
                        f"unexpected terminator target for instruction {exp[0]} field {index}"
                    )
                continue
            mapped_block = block_map.get((owner[0], target))
            if mapped_block is None or got[index] != mapped_block[1]:
                errors.append(
                    f"terminator target mismatch for instruction {exp[0]} field {index}"
                )

    candidate_d_by_id = {row[0]: row for row in candidate_d}
    for exp in expected_d:
        candidate_bid = binding_map.get(exp[0])
        got = candidate_d_by_id.get(candidate_bid) if candidate_bid is not None else None
        if got is None:
            continue
        if exp[7] == BINDING_TARGET_CODES["value"]:
            mapped_target = value_map.get(exp[8])
            if mapped_target is None or got[8] != mapped_target:
                errors.append(f"binding {exp[0]} value target mismatch")
        else:
            mapped_storage = storage_map.get((exp[1], exp[8]))
            if mapped_storage is None or got[8] != mapped_storage[1]:
                errors.append(f"binding {exp[0]} storage target mismatch")

    return {
        "schema": "s3.selfhost.semantic-conformance-v3.v1",
        "status": "PASS" if not errors else "FAIL",
        "candidate_internal_status": candidate_internal["status"],
        "source_sha256": model["source_sha256"],
        "source_bytes": model["source_bytes"],
        "expected": {
            "functions": len(expected_f),
            "blocks": len(expected_b),
            "bindings": len(expected_d),
            "values": len(expected_v),
            "storage": len(expected_m),
            "instructions": len(expected_i),
            "calls": len(expected_c),
            "terminators": len(_by_tag(expected, "T")),
        },
        "mapped_values": len(value_map),
        "mapped_storage": len(storage_map),
        "errors": errors,
    }


def verify_conformance(source: str, candidate_stream: str) -> dict[str, Any]:
    return verify_conformance_bytes(source.encode("ascii"), candidate_stream)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate_stream", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = verify_conformance_bytes(
        args.source.read_bytes(),
        args.candidate_stream.read_text(encoding="utf-8"),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"STATUS={result['status']}")
    print(f"SOURCE_SHA256={result['source_sha256']}")
    print(f"MAPPED_VALUES={result['mapped_values']}")
    print(f"MAPPED_STORAGE={result['mapped_storage']}")
    print(f"ERRORS={len(result['errors'])}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
