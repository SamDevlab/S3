"""Compare a Stage1-produced S3IR2 v2 stream with the hosted semantic oracle.

The verifier deliberately does not require candidate value IDs to equal hosted
register-derived IDs. It reconstructs the identity mapping from parameter order,
source binding names, and instruction result edges. This is the handoff gate for
a real self-hosted lowering implementation: different physical storage and value
numbering are allowed; semantic meaning is not.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.stage1_semantic_stream_v2 import (
    VALUE_KIND_CODES,
    build_model,
    parse_stream,
    verify_stream,
)


class ConformanceError(ValueError):
    pass


def _by_tag(parsed: dict[str, Any], tag: str) -> list[list[int]]:
    return [record["fields"] for record in parsed["records"] if record["tag"] == tag]


def _source_slice(source: str, start: int, length: int) -> str | None:
    if start < 0 or length < 0 or start + length > len(source):
        return None
    return source[start : start + length]


def _expected_binding_names(model: dict[str, Any]) -> dict[int, str]:
    result: dict[int, str] = {}
    for binding in model["bindings"]:
        value_id = binding.get("value_id")
        name = binding.get("name")
        if isinstance(value_id, int) and not isinstance(value_id, bool) and isinstance(name, str):
            result[value_id] = name
    return result


def verify_conformance(source: str, candidate_stream: str) -> dict[str, Any]:
    model = build_model(source)
    expected_text = __import__(
        "tools.stage1_semantic_stream_v2", fromlist=["encode_model"]
    ).encode_model(model)
    expected = parse_stream(expected_text)
    candidate = parse_stream(candidate_stream)
    candidate_internal = verify_stream(candidate)
    errors: list[str] = []

    if candidate_internal["status"] != "PASS":
        errors.append("candidate stream fails internal S3IR2 v2 verification")
        errors.extend(str(item) for item in candidate_internal["errors"][:20])

    expected_f = _by_tag(expected, "F")
    candidate_f = _by_tag(candidate, "F")
    if len(expected_f) != len(candidate_f):
        errors.append(f"function count mismatch: expected {len(expected_f)}, got {len(candidate_f)}")
    function_map: dict[int, int] = {}
    for ordinal, (exp, got) in enumerate(zip(expected_f, candidate_f)):
        # id may differ; kind, parameter count and result count may not.
        function_map[exp[0]] = got[0]
        if (exp[1], exp[4], exp[5]) != (got[1], got[4], got[5]):
            errors.append(f"function {ordinal} signature metadata mismatch")
        expected_name = model["functions"][ordinal]["name"]
        candidate_name = _source_slice(source, got[2], got[3])
        if candidate_name != expected_name:
            errors.append(
                f"function {ordinal} source identity mismatch: expected {expected_name!r}, got {candidate_name!r}"
            )

    expected_b = _by_tag(expected, "B")
    candidate_b = _by_tag(candidate, "B")
    if len(expected_b) != len(candidate_b):
        errors.append(f"block count mismatch: expected {len(expected_b)}, got {len(candidate_b)}")
    block_map: dict[tuple[int, int], tuple[int, int]] = {}
    for ordinal, (exp, got) in enumerate(zip(expected_b, candidate_b)):
        expected_owner = function_map.get(exp[0])
        if expected_owner != got[0]:
            errors.append(f"block {ordinal} function owner mismatch")
        block_map[(exp[0], exp[1])] = (got[0], got[1])
        if (exp[2], exp[3]) != (got[2], got[3]):
            errors.append(f"block {ordinal} ordinal/instruction-count mismatch")

    expected_i = _by_tag(expected, "I")
    candidate_i = _by_tag(candidate, "I")
    if len(expected_i) != len(candidate_i):
        errors.append(f"instruction count mismatch: expected {len(expected_i)}, got {len(candidate_i)}")
    instruction_map: dict[int, int] = {}
    for ordinal, (exp, got) in enumerate(zip(expected_i, candidate_i)):
        instruction_map[exp[0]] = got[0]
        expected_block = block_map.get((exp[1], exp[2]))
        if expected_block != (got[1], got[2]):
            errors.append(f"instruction {ordinal} owner/block mismatch")
        # ordinal, opcode, result count, operand count and scalar immediate are semantic.
        if (exp[3], exp[4], exp[5], exp[6], exp[8]) != (got[3], got[4], got[5], got[6], got[8]):
            errors.append(f"instruction {ordinal} semantic shape mismatch")

    expected_v = _by_tag(expected, "V")
    candidate_v = _by_tag(candidate, "V")
    expected_v_by_id = {row[0]: row for row in expected_v}
    candidate_v_by_id = {row[0]: row for row in candidate_v}
    value_map: dict[int, int] = {}
    binding_names = _expected_binding_names(model)

    # Parameters are mapped by function order and declaration order.
    for expected_function, candidate_function in function_map.items():
        exp_params = [row for row in expected_v if row[1] == expected_function and row[2] == VALUE_KIND_CODES["parameter"]]
        got_params = [row for row in candidate_v if row[1] == candidate_function and row[2] == VALUE_KIND_CODES["parameter"]]
        if len(exp_params) != len(got_params):
            errors.append(
                f"parameter value count mismatch for function {expected_function}: expected {len(exp_params)}, got {len(got_params)}"
            )
        for exp, got in zip(exp_params, got_params):
            value_map[exp[0]] = got[0]
            if exp[3] != got[3] or exp[6] != got[6]:
                errors.append(f"parameter value type/mutability mismatch for expected value {exp[0]}")
            expected_name = binding_names.get(exp[0])
            if expected_name is not None and _source_slice(source, got[4], got[5]) != expected_name:
                errors.append(f"parameter source identity mismatch for {expected_name!r}")

    # Local bindings are not hosted IR registers. Map them by exact source name.
    expected_locals = [row for row in expected_v if row[2] == VALUE_KIND_CODES["local_binding"]]
    candidate_locals = [row for row in candidate_v if row[2] == VALUE_KIND_CODES["local_binding"]]
    candidate_local_index: dict[tuple[int, str, int, int], list[list[int]]] = {}
    for row in candidate_locals:
        name = _source_slice(source, row[4], row[5])
        if name is None:
            continue
        key = (row[1], name, row[3], row[6])
        candidate_local_index.setdefault(key, []).append(row)
    for exp in expected_locals:
        expected_name = binding_names.get(exp[0])
        candidate_owner = function_map.get(exp[1])
        if expected_name is None or candidate_owner is None:
            errors.append(f"cannot resolve expected local value {exp[0]}")
            continue
        key = (candidate_owner, expected_name, exp[3], exp[6])
        matches = candidate_local_index.get(key, [])
        if not matches:
            errors.append(f"missing local binding {expected_name!r} in function {exp[1]}")
            continue
        got = matches.pop(0)
        value_map[exp[0]] = got[0]

    # Every hosted instruction result is mapped from the corresponding R edge.
    expected_r = _by_tag(expected, "R")
    candidate_r = _by_tag(candidate, "R")
    expected_r_by_instruction: dict[int, list[list[int]]] = {}
    candidate_r_by_instruction: dict[int, list[list[int]]] = {}
    for row in expected_r:
        expected_r_by_instruction.setdefault(row[0], []).append(row)
    for row in candidate_r:
        candidate_r_by_instruction.setdefault(row[0], []).append(row)
    for expected_instruction, candidate_instruction in instruction_map.items():
        exp_rows = sorted(expected_r_by_instruction.get(expected_instruction, []), key=lambda row: row[1])
        got_rows = sorted(candidate_r_by_instruction.get(candidate_instruction, []), key=lambda row: row[1])
        if len(exp_rows) != len(got_rows):
            errors.append(f"result edge count mismatch for instruction {expected_instruction}")
        for exp, got in zip(exp_rows, got_rows):
            if exp[1] != got[1]:
                errors.append(f"result ordinal mismatch for instruction {expected_instruction}")
            value_map[exp[2]] = got[2]

    # Validate mapped value kinds/types/owners independently from physical storage IDs.
    for expected_id, candidate_id in value_map.items():
        exp = expected_v_by_id.get(expected_id)
        got = candidate_v_by_id.get(candidate_id)
        if exp is None or got is None:
            errors.append(f"mapped value missing: {expected_id}->{candidate_id}")
            continue
        mapped_owner = function_map.get(exp[1])
        if (mapped_owner, exp[2], exp[3], exp[6]) != (got[1], got[2], got[3], got[6]):
            errors.append(f"mapped value semantic metadata mismatch: {expected_id}->{candidate_id}")

    # O edges must point to the mapped semantic values in the mapped instructions.
    expected_o = _by_tag(expected, "O")
    candidate_o = _by_tag(candidate, "O")
    candidate_o_set = {(row[0], row[1], row[2]) for row in candidate_o}
    for exp in expected_o:
        mapped_instruction = instruction_map.get(exp[0])
        mapped_value = value_map.get(exp[2])
        if mapped_instruction is None or mapped_value is None:
            errors.append(f"cannot map operand edge {exp}")
            continue
        if (mapped_instruction, exp[1], mapped_value) not in candidate_o_set:
            errors.append(f"missing mapped operand edge for expected {exp}")

    # Calls: preserve callee kind/function and ordered argument/result value identity.
    expected_c = _by_tag(expected, "C")
    candidate_c = _by_tag(candidate, "C")
    candidate_c_by_instruction = {row[0]: row for row in candidate_c}
    expected_call_model = {int(row["instruction_id"]): row for row in model["calls"]}
    for exp in expected_c:
        mapped_instruction = instruction_map.get(exp[0])
        got = candidate_c_by_instruction.get(mapped_instruction) if mapped_instruction is not None else None
        if got is None:
            errors.append(f"missing call record for expected instruction {exp[0]}")
            continue
        mapped_callee = function_map.get(exp[2], -1) if exp[2] >= 0 else -1
        if (exp[1], mapped_callee, exp[5], exp[6]) != (got[1], got[2], got[5], got[6]):
            errors.append(f"call semantic metadata mismatch for instruction {exp[0]}")
        call_model = expected_call_model.get(exp[0])
        if call_model is not None:
            expected_name = str(call_model.get("callee") or "")
            if expected_name and _source_slice(source, got[3], got[4]) != expected_name:
                errors.append(f"call source identity mismatch for {expected_name!r}")

    expected_a = _by_tag(expected, "A")
    candidate_a_set = {(row[0], row[1], row[2]) for row in _by_tag(candidate, "A")}
    for exp in expected_a:
        mapped_instruction = instruction_map.get(exp[0])
        mapped_value = value_map.get(exp[2])
        if mapped_instruction is None or mapped_value is None:
            errors.append(f"cannot map call argument edge {exp}")
            continue
        if (mapped_instruction, exp[1], mapped_value) not in candidate_a_set:
            errors.append(f"missing mapped call argument for expected {exp}")

    # Terminators: condition/return values are semantic; target block IDs are mapped.
    expected_t = _by_tag(expected, "T")
    candidate_t_by_instruction = {row[0]: row for row in _by_tag(candidate, "T")}
    expected_instruction_owner = {row[0]: (row[1], row[2]) for row in expected_i}
    for exp in expected_t:
        mapped_instruction = instruction_map.get(exp[0])
        got = candidate_t_by_instruction.get(mapped_instruction) if mapped_instruction is not None else None
        if got is None:
            errors.append(f"missing terminator for expected instruction {exp[0]}")
            continue
        if exp[1] != got[1]:
            errors.append(f"terminator kind mismatch for instruction {exp[0]}")
        for index in (2, 6):
            expected_value = exp[index]
            mapped_value = value_map.get(expected_value, -1) if expected_value >= 0 else -1
            if got[index] != mapped_value:
                errors.append(f"terminator value edge mismatch for instruction {exp[0]} field {index}")
        owner = expected_instruction_owner.get(exp[0])
        if owner is None:
            continue
        expected_function = owner[0]
        for index in (3, 4, 5):
            target = exp[index]
            if target < 0:
                if got[index] >= 0:
                    errors.append(f"unexpected terminator target for instruction {exp[0]} field {index}")
                continue
            mapped_block = block_map.get((expected_function, target))
            if mapped_block is None or got[index] != mapped_block[1]:
                errors.append(f"terminator target mismatch for instruction {exp[0]} field {index}")

    status = "PASS" if not errors else "FAIL"
    return {
        "schema": "s3.selfhost.semantic-conformance-v2.v1",
        "status": status,
        "candidate_internal_status": candidate_internal["status"],
        "expected": {
            "functions": len(expected_f),
            "blocks": len(expected_b),
            "values": len(expected_v),
            "instructions": len(expected_i),
            "calls": len(expected_c),
            "terminators": len(expected_t),
        },
        "mapped_values": len(value_map),
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("candidate_stream", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = verify_conformance(
        args.source.read_text(encoding="utf-8"),
        args.candidate_stream.read_text(encoding="utf-8"),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"STATUS={result['status']}")
    print(f"MAPPED_VALUES={result['mapped_values']}")
    print(f"ERRORS={len(result['errors'])}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
