"""Authoritative S3IR2 v2 semantic stream for the Stage1 handoff.

v1 proved the streaming shape. v2 freezes the handoff contract: source bindings,
typed values, instruction def/use, calls, complete numeric terminators, and the
canonical serialization gate are all explicit and fail closed.

This module is a hosted oracle. It does not claim that the self-hosted Stage1 has
already emitted the stream natively.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from bootstrap.s3.pipeline import compile_source
from tools.stage1_semantic_ir_reference import project_semantic_ir
from tools.stage1_source_binding_reference import extract_bindings

HEADER = "S3IR2 2"
SCHEMA = "s3.selfhost.semantic-stream.v2"
COMPLETE_MASK = 1 | 2 | 4 | 8 | 16

TYPE_CODES = {
    "trit": 1,
    "tryte": 2,
    "i64": 3,
    "f64": 4,
    "string": 5,
    "bytes": 6,
    "text": 7,
    "vector": 8,
    "reference": 9,
    "array": 10,
    "nominal": 11,
}
VALUE_KIND_CODES = {
    "parameter": 1,
    "local_binding": 2,
    "constant": 3,
    "instruction_result": 4,
}
FUNCTION_KIND_CODES = {"internal": 1, "foreign": 2}
CALLEE_KIND_CODES = {
    "internal": 1,
    "foreign": 2,
    "builtin_or_external": 3,
    "invalid": 0,
}
TERMINATOR_KIND_CODES = {"return": 1, "jump": 2, "branch3": 3}
OPCODE_CODES = {
    "const": 1,
    "const_str": 2,
    "move": 3,
    "invert": 4,
    "add": 5,
    "numeric_difference": 6,
    "multiply": 7,
    "divide": 8,
    "relate": 9,
    "convert": 10,
    "minimum": 11,
    "maximum": 12,
    "compare": 13,
    "call": 14,
    "load": 15,
    "store": 16,
    "address_of": 17,
    "reference_load": 18,
    "reference_store": 19,
    "slice_length": 20,
    "slice_load": 21,
    "slice_store": 22,
    "return": 23,
    "jump": 24,
    "branch3": 25,
}

EXPECTED_FIELDS = {
    "F": 6,
    "B": 5,
    "V": 8,
    "M": 5,
    "I": 9,
    "O": 3,
    "R": 3,
    "C": 7,
    "A": 3,
    "T": 7,
    "Z": 1,
}


class SemanticStreamV2Error(ValueError):
    pass


def _source(value: object) -> dict[str, int] | None:
    location = getattr(value, "location", None)
    if location is None:
        return None
    rendered = location.to_dict()
    return rendered if isinstance(rendered, dict) else None


def _anchor(row: dict[str, Any], *, default_length: int = 0) -> tuple[int, int]:
    source = row.get("source")
    if not isinstance(source, dict):
        return -1, -1
    offset = source.get("offset")
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
        return -1, -1
    return offset, default_length


def _binding_type_code(declared: str) -> int:
    if declared.startswith("array["):
        return TYPE_CODES["array"]
    if declared.startswith("ref<") or declared.startswith("mut_ref<") or declared.startswith("slice<") or declared.startswith("mut_slice<"):
        return TYPE_CODES["reference"]
    if declared.startswith("type_parameter<") or "<" in declared:
        return TYPE_CODES["nominal"]
    return TYPE_CODES.get(declared, TYPE_CODES["nominal"])


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def build_model(source: str) -> dict[str, Any]:
    source_bytes = source.encode("utf-8")
    compilation = compile_source(source)
    if compilation.ir is None:
        raise SemanticStreamV2Error("ordinary typed IR is unavailable")
    program = compilation.ir
    projected = project_semantic_ir(
        program,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
    )
    bindings = extract_bindings(compilation.ast)

    functions: list[dict[str, Any]] = []
    function_name_to_index: dict[str, int] = {}
    block_name_to_index: dict[tuple[int, str], int] = {}
    for function_index, function in enumerate(program.functions):
        function_name_to_index[function.name] = function_index
        location = _source(function)
        name_start = int(location["offset"]) if isinstance(location, dict) and isinstance(location.get("offset"), int) else -1
        functions.append({
            "function_id": function_index,
            "kind": "foreign" if function.external else "internal",
            "name": function.name,
            "name_start": name_start,
            "name_length": len(function.name),
            "parameter_count": len(function.parameters),
            "result_count": len(function.result_types),
        })
        for block_index, block in enumerate(function.blocks):
            block_name_to_index[(function_index, block.name)] = block_index

    host_values = list(projected["lanes"]["typed_values"])
    value_rows: list[dict[str, Any]] = []
    parameter_key_to_value: dict[tuple[int, int], int] = {}
    for row in host_values:
        definition = row.get("definition", {})
        kind = str(definition.get("kind", ""))
        if kind not in {"parameter", "constant", "instruction_result"}:
            continue
        start, length = _anchor(
            row,
            default_length=(len(str(definition.get("parameter_name", ""))) if kind == "parameter" else 0),
        )
        value_row = {
            "value_id": int(row["value_id"]),
            "function_id": int(row["function_index"]),
            "kind": kind,
            "type": str(row["type"]),
            "anchor_start": start,
            "anchor_length": length,
            "mutable": bool(definition.get("mutable", False)),
            "storage_id": -1,
        }
        value_rows.append(value_row)
        if kind == "parameter":
            ordinal = definition.get("parameter_ordinal")
            if isinstance(ordinal, int) and not isinstance(ordinal, bool):
                parameter_key_to_value[(int(row["function_index"]), ordinal)] = int(row["value_id"])

    next_value_id = max((row["value_id"] for row in value_rows), default=-1) + 1
    binding_rows: list[dict[str, Any]] = []
    for binding in bindings["bindings"]:
        kind = str(binding["kind"])
        if kind == "parameter":
            key = (int(binding["function_index"]), int(binding["parameter_ordinal"]))
            linked = parameter_key_to_value.get(key)
            if linked is None:
                raise SemanticStreamV2Error(f"parameter binding has no IR value link: {binding['function']}:{binding['name']}")
            binding_rows.append({**binding, "value_id": linked, "link_status": "LINKED_PARAMETER_VALUE"})
            continue
        if kind not in {"local", "loop_variable"}:
            continue
        location = binding.get("source")
        start = int(location["offset"]) if isinstance(location, dict) and isinstance(location.get("offset"), int) else -1
        declared = str(binding["declared_type"])
        local_value = {
            "value_id": next_value_id,
            "function_id": int(binding["function_index"]),
            "kind": "local_binding",
            "type": declared,
            "anchor_start": start,
            "anchor_length": len(str(binding["name"])),
            "mutable": bool(binding["mutable"]),
            "storage_id": -1,
        }
        value_rows.append(local_value)
        binding_rows.append({**binding, "value_id": next_value_id, "link_status": "SOURCE_BINDING_VALUE"})
        next_value_id += 1

    instructions = list(projected["lanes"]["instructions"])
    instruction_by_id = {int(row["instruction_id"]): row for row in instructions}
    block_rows: list[dict[str, Any]] = []
    for function_index, function in enumerate(program.functions):
        for block_index, block in enumerate(function.blocks):
            block_instructions = [
                row for row in instructions
                if int(row["function_index"]) == function_index and int(row["block_index"]) == block_index
            ]
            terminator_id = -1
            if block_instructions:
                last = block_instructions[-1]
                if str(last["opcode"]) in {"return", "jump", "branch3"}:
                    terminator_id = int(last["instruction_id"])
            block_rows.append({
                "function_id": function_index,
                "block_id": block_index,
                "ordinal": block_index,
                "instruction_count": len(block_instructions),
                "terminator_instruction_id": terminator_id,
            })

    call_rows: list[dict[str, Any]] = []
    for call in projected["lanes"]["calls"]:
        instruction = instruction_by_id[int(call["instruction_id"])]
        start, _ = _anchor(instruction)
        callee = call.get("callee")
        callee_name = str(callee) if callee is not None else ""
        call_rows.append({
            **call,
            "callee_function_id": function_name_to_index.get(callee_name, -1),
            "callee_name_start": start,
            "callee_name_length": len(callee_name) if callee_name else -1,
        })

    terminator_rows: list[dict[str, Any]] = []
    for term in projected["lanes"]["terminators"]:
        function_id = int(term["function_index"])
        target_ids: list[int] = []
        for target in term.get("targets", []):
            target_id = block_name_to_index.get((function_id, str(target)))
            if target_id is None:
                raise SemanticStreamV2Error(f"unresolved terminator target {term['function']}:{target}")
            target_ids.append(target_id)
        terminator_rows.append({**term, "target_block_ids": target_ids})

    completeness = {
        "S1_typed_values_and_bindings": bool(projected["completeness"].get("typed_value_definitions")) and all(row["link_status"] for row in binding_rows),
        "S2_instruction_def_use": bool(projected["completeness"].get("instruction_def_use")),
        "S3_call_dataflow": bool(projected["completeness"].get("call_dataflow")) and all(row["callee_kind"] != "invalid" for row in call_rows),
        "S4_complete_terminators": bool(projected["completeness"].get("complete_terminators")) and all(row["target_block_ids"] is not None for row in terminator_rows),
    }

    model = {
        "schema": SCHEMA,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_bytes": len(source_bytes),
        "identity_policy": {
            "logical_value_ids": "DETERMINISTIC_SEMANTIC_ORDER_NOT_PHYSICAL_SLOT",
            "source_binding_identity": "FUNCTION_SCOPE_PLUS_SOURCE_OFFSET_PLUS_EXACT_NAME",
            "physical_storage_is_semantic_identity": False,
            "scratch_storage_reuse_allowed": True,
        },
        "functions": functions,
        "blocks": block_rows,
        "values": value_rows,
        "bindings": binding_rows,
        "storage": list(projected["lanes"].get("storage_objects", [])),
        "instructions": instructions,
        "calls": call_rows,
        "terminators": terminator_rows,
        "completeness": completeness,
        "errors": list(projected.get("errors", [])),
    }
    core = _canonical_json(model)
    model["canonical_model"] = {
        "bytes": len(core),
        "sha256": hashlib.sha256(core).hexdigest(),
    }
    return model


def encode_model(model: dict[str, Any]) -> str:
    lines: list[str] = [HEADER]
    for row in model["functions"]:
        lines.append(
            f"F {row['function_id']} {FUNCTION_KIND_CODES[row['kind']]} {row['name_start']} {row['name_length']} {row['parameter_count']} {row['result_count']}"
        )
    for row in model["blocks"]:
        lines.append(
            f"B {row['function_id']} {row['block_id']} {row['ordinal']} {row['instruction_count']} {row['terminator_instruction_id']}"
        )
    for row in model["values"]:
        kind = VALUE_KIND_CODES[row["kind"]]
        type_code = _binding_type_code(row["type"]) if row["kind"] == "local_binding" else TYPE_CODES[row["type"]]
        lines.append(
            f"V {row['value_id']} {row['function_id']} {kind} {type_code} {row['anchor_start']} {row['anchor_length']} {int(row['mutable'])} {row['storage_id']}"
        )
    for row in model["storage"]:
        lines.append(
            f"M {row['function_index']} {row['memory_id']} {TYPE_CODES[row['element_type']]} {row['length']} {int(bool(row['mutable']))}"
        )
    for row in model["instructions"]:
        aux_a = int(row.get("memory_object", -1))
        immediate = row.get("immediate")
        aux_b = int(immediate) if isinstance(immediate, int) and not isinstance(immediate, bool) else -1
        lines.append(
            f"I {row['instruction_id']} {row['function_index']} {row['block_index']} {row['ordinal']} {OPCODE_CODES[row['opcode']]} {len(row['result_value_ids'])} {len(row['operand_value_ids'])} {aux_a} {aux_b}"
        )
        for ordinal, value_id in enumerate(row["operand_value_ids"]):
            lines.append(f"O {row['instruction_id']} {ordinal} {value_id}")
        for ordinal, value_id in enumerate(row["result_value_ids"]):
            lines.append(f"R {row['instruction_id']} {ordinal} {value_id}")
    for row in model["calls"]:
        lines.append(
            f"C {row['instruction_id']} {CALLEE_KIND_CODES[row['callee_kind']]} {row['callee_function_id']} {row['callee_name_start']} {row['callee_name_length']} {len(row['argument_value_ids'])} {len(row['result_value_ids'])}"
        )
        for ordinal, value_id in enumerate(row["argument_value_ids"]):
            lines.append(f"A {row['instruction_id']} {ordinal} {value_id}")
    for row in model["terminators"]:
        kind = str(row["kind"])
        targets = list(row["target_block_ids"])
        condition = int(row.get("condition_value_id", -1))
        negative = zero = positive = -1
        return_value = -1
        if kind == "jump":
            if len(targets) != 1:
                raise SemanticStreamV2Error("jump must have exactly one numeric target")
            negative = int(targets[0])
        elif kind == "branch3":
            if len(targets) != 3:
                raise SemanticStreamV2Error("branch3 must have exactly three numeric targets")
            negative, zero, positive = (int(targets[0]), int(targets[1]), int(targets[2]))
        elif kind == "return":
            values = list(row.get("return_value_ids", []))
            if values:
                return_value = int(values[0])
        lines.append(
            f"T {row['instruction_id']} {TERMINATOR_KIND_CODES[kind]} {condition} {negative} {zero} {positive} {return_value}"
        )

    lanes_ok = all(bool(value) for value in model["completeness"].values()) and not model["errors"]
    mask = COMPLETE_MASK if lanes_ok else 0
    lines.append(f"Z {mask}")
    return "\n".join(lines) + "\n"


def parse_stream(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0] != HEADER:
        raise SemanticStreamV2Error("missing or invalid S3IR2 v2 header")
    records: list[dict[str, Any]] = []
    mask: int | None = None
    for line_number, line in enumerate(lines[1:], start=2):
        parts = line.split()
        tag = parts[0]
        if tag not in EXPECTED_FIELDS:
            raise SemanticStreamV2Error(f"line {line_number}: unknown tag {tag}")
        try:
            fields = [int(item) for item in parts[1:]]
        except ValueError as error:
            raise SemanticStreamV2Error(f"line {line_number}: non-integer field") from error
        if len(fields) != EXPECTED_FIELDS[tag]:
            raise SemanticStreamV2Error(
                f"line {line_number}: {tag} expects {EXPECTED_FIELDS[tag]} fields, got {len(fields)}"
            )
        if tag == "Z":
            if mask is not None:
                raise SemanticStreamV2Error("multiple completeness records")
            mask = fields[0]
        records.append({"tag": tag, "fields": fields, "line": line_number})
    if mask is None:
        raise SemanticStreamV2Error("missing completeness record")
    return {"schema": SCHEMA, "records": records, "completeness_mask": mask, "complete": mask == COMPLETE_MASK}


def verify_stream(parsed: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    functions: set[int] = set()
    blocks: set[tuple[int, int]] = set()
    values: set[int] = set()
    instructions: dict[int, tuple[int, int, int, int]] = {}
    operands: dict[int, list[tuple[int, int]]] = {}
    results: dict[int, list[tuple[int, int]]] = {}
    calls: dict[int, tuple[int, int]] = {}
    call_args: dict[int, list[tuple[int, int]]] = {}
    terminators: dict[int, list[int]] = {}

    for record in parsed["records"]:
        tag = record["tag"]
        f = record["fields"]
        if tag == "F":
            if f[0] in functions:
                errors.append(f"duplicate function id {f[0]}")
            functions.add(f[0])
        elif tag == "B":
            key = (f[0], f[1])
            if key in blocks:
                errors.append(f"duplicate block {key}")
            blocks.add(key)
        elif tag == "V":
            if f[0] in values:
                errors.append(f"duplicate value id {f[0]}")
            values.add(f[0])
            if f[1] not in functions:
                errors.append(f"value {f[0]} has unknown function {f[1]}")
            if f[2] not in VALUE_KIND_CODES.values() or f[3] not in TYPE_CODES.values():
                errors.append(f"value {f[0]} has invalid kind/type code")
        elif tag == "M":
            if f[0] not in functions:
                errors.append(f"memory {f[1]} has unknown function {f[0]}")
        elif tag == "I":
            iid = f[0]
            if iid in instructions:
                errors.append(f"duplicate instruction id {iid}")
            instructions[iid] = (f[1], f[2], f[5], f[6])
            if (f[1], f[2]) not in blocks:
                errors.append(f"instruction {iid} has unknown block {f[1]}:{f[2]}")
            if f[4] not in OPCODE_CODES.values():
                errors.append(f"instruction {iid} has invalid opcode {f[4]}")
        elif tag == "O":
            operands.setdefault(f[0], []).append((f[1], f[2]))
        elif tag == "R":
            results.setdefault(f[0], []).append((f[1], f[2]))
        elif tag == "C":
            calls[f[0]] = (f[5], f[6])
            if f[1] not in CALLEE_KIND_CODES.values():
                errors.append(f"call {f[0]} has invalid callee kind")
            if f[2] >= 0 and f[2] not in functions:
                errors.append(f"call {f[0]} references unknown callee function {f[2]}")
        elif tag == "A":
            call_args.setdefault(f[0], []).append((f[1], f[2]))
        elif tag == "T":
            terminators[f[0]] = f

    for iid, (owner, block, result_count, operand_count) in instructions.items():
        observed_o = sorted(operands.get(iid, []))
        observed_r = sorted(results.get(iid, []))
        if len(observed_o) != operand_count:
            errors.append(f"instruction {iid} operand count mismatch")
        if len(observed_r) != result_count:
            errors.append(f"instruction {iid} result count mismatch")
        for _ordinal, value_id in observed_o + observed_r:
            if value_id not in values:
                errors.append(f"instruction {iid} references unknown value {value_id}")
        _ = owner, block

    for iid, (arg_count, _result_count) in calls.items():
        if iid not in instructions:
            errors.append(f"call references unknown instruction {iid}")
        args = sorted(call_args.get(iid, []))
        if len(args) != arg_count:
            errors.append(f"call {iid} argument count mismatch")
        for _ordinal, value_id in args:
            if value_id not in values:
                errors.append(f"call {iid} references unknown value {value_id}")

    for iid, f in terminators.items():
        instruction = instructions.get(iid)
        if instruction is None:
            errors.append(f"terminator references unknown instruction {iid}")
            continue
        owner = instruction[0]
        kind = f[1]
        condition, negative, zero, positive, return_value = f[2:]
        if kind == TERMINATOR_KIND_CODES["return"]:
            if any(target >= 0 for target in (negative, zero, positive)):
                errors.append(f"return {iid} carries branch target")
        elif kind == TERMINATOR_KIND_CODES["jump"]:
            if negative < 0 or zero >= 0 or positive >= 0:
                errors.append(f"jump {iid} does not carry exactly one target")
            elif (owner, negative) not in blocks:
                errors.append(f"jump {iid} targets unknown block {negative}")
        elif kind == TERMINATOR_KIND_CODES["branch3"]:
            if condition < 0 or any(target < 0 for target in (negative, zero, positive)):
                errors.append(f"branch3 {iid} is incomplete")
            for target in (negative, zero, positive):
                if (owner, target) not in blocks:
                    errors.append(f"branch3 {iid} targets unknown block {target}")
        else:
            errors.append(f"terminator {iid} has invalid kind {kind}")
        for value_id in (condition, return_value):
            if value_id >= 0 and value_id not in values:
                errors.append(f"terminator {iid} references unknown value {value_id}")

    for record in parsed["records"]:
        if record["tag"] != "B":
            continue
        function_id, block_id, _ordinal, _count, terminator_id = record["fields"]
        if terminator_id < 0:
            errors.append(f"block {function_id}:{block_id} lacks terminator")
        elif terminator_id not in terminators:
            errors.append(f"block {function_id}:{block_id} terminator {terminator_id} missing T record")

    status = "PASS" if parsed["complete"] and not errors else "BLOCKED"
    return {
        "schema": "s3.selfhost.semantic-stream-v2-verification.v1",
        "status": status,
        "complete": parsed["complete"],
        "function_count": len(functions),
        "block_count": len(blocks),
        "value_count": len(values),
        "instruction_count": len(instructions),
        "call_count": len(calls),
        "terminator_count": len(terminators),
        "errors": errors,
    }


def build_stream(source: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    model = build_model(source)
    stream = encode_model(model)
    parsed = parse_stream(stream)
    verification = verify_stream(parsed)
    return stream, model, verification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--stream-output", type=Path, required=True)
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument("--verification-output", type=Path, required=True)
    args = parser.parse_args(argv)

    source = args.source.read_text(encoding="utf-8")
    stream, model, verification = build_stream(source)
    args.stream_output.parent.mkdir(parents=True, exist_ok=True)
    args.stream_output.write_text(stream, encoding="utf-8", newline="\n")
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    args.model_output.write_text(json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    args.verification_output.parent.mkdir(parents=True, exist_ok=True)
    args.verification_output.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"STATUS={verification['status']}")
    print(f"FUNCTIONS={verification['function_count']}")
    print(f"BLOCKS={verification['block_count']}")
    print(f"VALUES={verification['value_count']}")
    print(f"INSTRUCTIONS={verification['instruction_count']}")
    print(f"CALLS={verification['call_count']}")
    print(f"TERMINATORS={verification['terminator_count']}")
    print(f"MODEL_SHA256={model['canonical_model']['sha256']}")
    return 0 if verification["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
