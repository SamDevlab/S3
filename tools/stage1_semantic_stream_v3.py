"""Audited Stage1 semantic stream v3.

v3 corrects the v2 oracle boundary:
- raw source bytes are authoritative (no newline normalization before SHA/anchors);
- source bindings are D records, not synthetic V values;
- bindings resolve to a real logical value or storage object;
- storage carries source provenance and is part of conformance;
- S1-S4 semantic conformance is separate from S1.6 canonical serialization.

This is a bootstrap-subset oracle. Unsupported/lossy semantic forms fail closed.
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

HEADER = "S3IR2 3"
SCHEMA = "s3.selfhost.semantic-stream.v3"
SEMANTIC_COMPLETE_MASK = 1 | 2 | 4 | 8

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
VALUE_KIND_CODES = {"parameter": 1, "constant": 2, "instruction_result": 3}
BINDING_KIND_CODES = {"parameter": 1, "local": 2, "loop_variable": 3}
BINDING_TARGET_CODES = {"value": 1, "storage": 2}
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
MEMORY_OPCODES = {
    OPCODE_CODES["load"],
    OPCODE_CODES["store"],
    OPCODE_CODES["address_of"],
}

EXPECTED_FIELDS = {
    "F": 6,
    "B": 5,
    "D": 9,
    "V": 8,
    "M": 6,
    "I": 9,
    "O": 3,
    "R": 3,
    "C": 7,
    "A": 3,
    "T": 7,
    "Z": 1,
}


class SemanticStreamV3Error(ValueError):
    pass


def _source(value: object) -> dict[str, int] | None:
    location = getattr(value, "location", None)
    if location is None:
        return None
    rendered = location.to_dict()
    return rendered if isinstance(rendered, dict) else None


def _offset_from_source(source: object) -> int:
    if not isinstance(source, dict):
        return -1
    value = source.get("offset")
    return value if isinstance(value, int) and not isinstance(value, bool) else -1


def _is_identifier_char(value: str) -> bool:
    return value == "_" or value.isalnum()


def _find_identifier_anchor(source: str, approximate_offset: int, name: str) -> int:
    if not name:
        return -1
    if approximate_offset < 0 or approximate_offset > len(source):
        approximate_offset = 0
    line_start = source.rfind("\n", 0, approximate_offset) + 1
    line_end = source.find("\n", approximate_offset)
    if line_end < 0:
        line_end = len(source)
    candidates: list[int] = []
    cursor = line_start
    while cursor <= line_end - len(name):
        found = source.find(name, cursor, line_end)
        if found < 0:
            break
        before_ok = found == 0 or not _is_identifier_char(source[found - 1])
        after_index = found + len(name)
        after_ok = after_index >= len(source) or not _is_identifier_char(source[after_index])
        if before_ok and after_ok:
            candidates.append(found)
        cursor = found + 1
    if not candidates:
        return -1
    return min(candidates, key=lambda item: abs(item - approximate_offset))


def _binding_type_code(declared: str) -> int:
    if declared.startswith("array["):
        return TYPE_CODES["array"]
    if (
        declared.startswith("ref<")
        or declared.startswith("mut_ref<")
        or declared.startswith("slice<")
        or declared.startswith("mut_slice<")
    ):
        return TYPE_CODES["reference"]
    if declared in TYPE_CODES:
        return TYPE_CODES[declared]
    return TYPE_CODES["nominal"]


def _decode_source(raw_source: bytes) -> str:
    try:
        source = raw_source.decode("ascii")
    except UnicodeDecodeError as error:
        raise SemanticStreamV3Error(
            "Stage1 semantic v3 currently requires the byte-exact ASCII self-hosting subset"
        ) from error
    return source


def _reject_lossy_ir(program: object) -> None:
    for function in program.functions:
        for block in function.blocks:
            for instruction in block.instructions:
                if instruction.opcode.value == "const_str":
                    raise SemanticStreamV3Error(
                        "CONST_STR is not yet losslessly represented by the Stage1 v3 bootstrap stream"
                    )
                if isinstance(instruction.immediate, float):
                    raise SemanticStreamV3Error(
                        "f64 immediates are not yet losslessly represented by the Stage1 v3 bootstrap stream"
                    )


def _definition_kind(row: dict[str, Any]) -> str:
    definition = row.get("definition")
    if not isinstance(definition, dict):
        return ""
    return str(definition.get("kind", ""))


def _anchor_from_row(row: dict[str, Any]) -> int:
    return _offset_from_source(row.get("source"))


def build_model_bytes(raw_source: bytes) -> dict[str, Any]:
    source = _decode_source(raw_source)
    compilation = compile_source(source)
    if compilation.ir is None:
        raise SemanticStreamV3Error("ordinary typed IR is unavailable")
    program = compilation.ir
    _reject_lossy_ir(program)

    source_sha256 = hashlib.sha256(raw_source).hexdigest()
    projected = project_semantic_ir(program, source_sha256=source_sha256)
    binding_reference = extract_bindings(compilation.ast)

    functions: list[dict[str, Any]] = []
    function_name_to_index: dict[str, int] = {}
    block_name_to_index: dict[tuple[int, str], int] = {}
    for function_index, function in enumerate(program.functions):
        function_name_to_index[function.name] = function_index
        approximate = _offset_from_source(_source(function))
        name_start = _find_identifier_anchor(source, approximate, function.name)
        if name_start < 0:
            raise SemanticStreamV3Error(
                f"cannot resolve exact function source anchor: {function.name}"
            )
        functions.append(
            {
                "function_id": function_index,
                "kind": "foreign" if function.external else "internal",
                "name": function.name,
                "name_start": name_start,
                "name_length": len(function.name),
                "parameter_count": len(function.parameters),
                "result_count": len(function.result_types),
            }
        )
        for block_index, block in enumerate(function.blocks):
            block_name_to_index[(function_index, block.name)] = block_index

    value_rows: list[dict[str, Any]] = []
    register_to_value: dict[tuple[int, int], int] = {}
    parameter_name_to_value: dict[tuple[int, str], int] = {}
    for row in projected["lanes"]["typed_values"]:
        kind = _definition_kind(row)
        if kind not in VALUE_KIND_CODES:
            continue
        value_id = int(row["value_id"])
        function_id = int(row["function_index"])
        register = int(row["register"])
        register_to_value[(function_id, register)] = value_id
        definition = row["definition"]
        anchor_start = _anchor_from_row(row)
        anchor_length = 0
        if kind == "parameter":
            parameter_name = str(definition.get("parameter_name", ""))
            anchor_start = _find_identifier_anchor(source, anchor_start, parameter_name)
            anchor_length = len(parameter_name)
            key = (function_id, parameter_name)
            if key in parameter_name_to_value:
                raise SemanticStreamV3Error(
                    f"parameter name is not a unique IR value: {function_id}:{parameter_name}"
                )
            parameter_name_to_value[key] = value_id
        value_rows.append(
            {
                "value_id": value_id,
                "function_id": function_id,
                "kind": kind,
                "type": str(row["type"]),
                "anchor_start": anchor_start,
                "anchor_length": anchor_length,
                "mutable": bool(definition.get("mutable", False)),
                "storage_id": -1,
            }
        )

    storage_rows: list[dict[str, Any]] = []
    storage_by_declaration: dict[tuple[int, int], list[int]] = {}
    for function_index, function in enumerate(program.functions):
        for memory in function.memory_objects:
            anchor_start = _offset_from_source(_source(memory))
            storage_rows.append(
                {
                    "function_id": function_index,
                    "storage_id": int(memory.index),
                    "element_type": memory.element_type.value,
                    "length": int(memory.length),
                    "mutable": bool(memory.mutable),
                    "anchor_start": anchor_start,
                }
            )
            storage_by_declaration.setdefault(
                (function_index, anchor_start), []
            ).append(int(memory.index))

    registers_by_declaration: dict[tuple[int, int], list[int]] = {}
    parameter_registers: set[tuple[int, int]] = set()
    for function_index, function in enumerate(program.functions):
        for parameter in function.parameters:
            parameter_registers.add((function_index, int(parameter.register)))
        for register in function.registers:
            anchor_start = _offset_from_source(_source(register))
            if anchor_start >= 0 and (function_index, int(register.index)) not in parameter_registers:
                registers_by_declaration.setdefault(
                    (function_index, anchor_start), []
                ).append(int(register.index))

    binding_rows: list[dict[str, Any]] = []
    for binding in binding_reference["bindings"]:
        function_name = str(binding["function"])
        function_id = function_name_to_index.get(function_name)
        if function_id is None:
            raise SemanticStreamV3Error(
                f"binding owner does not resolve in IR: {function_name}:{binding['name']}"
            )
        binding_name = str(binding["name"])
        declaration_offset = _offset_from_source(binding.get("source"))
        name_start = _find_identifier_anchor(source, declaration_offset, binding_name)
        if name_start < 0:
            raise SemanticStreamV3Error(
                f"cannot resolve exact binding source anchor: {function_name}:{binding_name}"
            )
        kind = str(binding["kind"])
        target_kind: str
        target_id: int
        if kind == "parameter":
            linked = parameter_name_to_value.get((function_id, binding_name))
            if linked is None:
                raise SemanticStreamV3Error(
                    "parameter binding does not resolve to one scalar IR value "
                    f"(aggregate/expanded parameters are outside the v3 bootstrap subset): "
                    f"{function_name}:{binding_name}"
                )
            target_kind, target_id = "value", linked
        elif kind in {"local", "loop_variable"}:
            storage_matches = storage_by_declaration.get(
                (function_id, declaration_offset), []
            )
            register_matches = registers_by_declaration.get(
                (function_id, declaration_offset), []
            )
            value_matches = [
                register_to_value[(function_id, register)]
                for register in register_matches
                if (function_id, register) in register_to_value
            ]
            if len(storage_matches) == 1:
                target_kind, target_id = "storage", storage_matches[0]
            elif not storage_matches and len(value_matches) == 1:
                target_kind, target_id = "value", value_matches[0]
            else:
                raise SemanticStreamV3Error(
                    "binding target is not uniquely provable from typed IR: "
                    f"{function_name}:{binding_name}@{declaration_offset} "
                    f"storage={storage_matches} values={value_matches}"
                )
        else:
            continue

        binding_rows.append(
            {
                "binding_id": int(binding["binding_id"]),
                "function_id": function_id,
                "kind": kind,
                "type_code": _binding_type_code(str(binding["declared_type"])),
                "name_start": name_start,
                "name_length": len(binding_name),
                "scope_path": list(binding.get("scope_path", [])),
                "mutable": bool(binding["mutable"]),
                "target_kind": target_kind,
                "target_id": target_id,
            }
        )

    instructions = list(projected["lanes"]["instructions"])
    instruction_by_id = {int(row["instruction_id"]): row for row in instructions}

    block_rows: list[dict[str, Any]] = []
    for function_index, function in enumerate(program.functions):
        for block_index, block in enumerate(function.blocks):
            block_instructions = [
                row
                for row in instructions
                if int(row["function_index"]) == function_index
                and int(row["block_index"]) == block_index
            ]
            terminator_id = -1
            if block_instructions:
                last = block_instructions[-1]
                if str(last["opcode"]) in {"return", "jump", "branch3"}:
                    terminator_id = int(last["instruction_id"])
            block_rows.append(
                {
                    "function_id": function_index,
                    "block_id": block_index,
                    "ordinal": block_index,
                    "instruction_count": len(block_instructions),
                    "terminator_instruction_id": terminator_id,
                }
            )

    call_rows: list[dict[str, Any]] = []
    for call in projected["lanes"]["calls"]:
        instruction = instruction_by_id[int(call["instruction_id"])]
        approximate = _anchor_from_row(instruction)
        callee = call.get("callee")
        callee_name = str(callee) if callee is not None else ""
        callee_start = (
            _find_identifier_anchor(source, approximate, callee_name)
            if callee_name
            else -1
        )
        call_rows.append(
            {
                **call,
                "callee_function_id": function_name_to_index.get(callee_name, -1),
                "callee_name_start": callee_start,
                "callee_name_length": len(callee_name) if callee_name else -1,
            }
        )

    terminator_rows: list[dict[str, Any]] = []
    for term in projected["lanes"]["terminators"]:
        function_id = int(term["function_index"])
        target_ids: list[int] = []
        for target in term.get("targets", []):
            target_id = block_name_to_index.get((function_id, str(target)))
            if target_id is None:
                raise SemanticStreamV3Error(
                    f"unresolved terminator target {term['function']}:{target}"
                )
            target_ids.append(target_id)
        terminator_rows.append({**term, "target_block_ids": target_ids})

    completeness = {
        "S1_values_bindings_storage": bool(
            projected["completeness"].get("typed_value_definitions")
        )
        and all(row["target_kind"] in {"value", "storage"} for row in binding_rows),
        "S2_instruction_def_use": bool(
            projected["completeness"].get("instruction_def_use")
        ),
        "S3_call_dataflow": bool(
            projected["completeness"].get("call_dataflow")
        )
        and all(row["callee_kind"] != "invalid" for row in call_rows),
        "S4_complete_terminators": bool(
            projected["completeness"].get("complete_terminators")
        )
        and all(row["target_block_ids"] is not None for row in terminator_rows),
    }

    return {
        "schema": SCHEMA,
        "source_sha256": source_sha256,
        "source_bytes": len(raw_source),
        "source_newline_policy": "RAW_BYTES_PRESERVED",
        "identity_policy": {
            "value": "IR_VALUE_NOT_SOURCE_BINDING",
            "binding": "FUNCTION_PLUS_EXACT_DECLARATION_ANCHOR_PLUS_IDENTIFIER",
            "binding_target": "VALUE_OR_STORAGE_REQUIRED",
            "storage": "IR_MEMORY_OBJECT_WITH_SOURCE_PROVENANCE",
            "candidate_numeric_ids_may_differ": True,
            "canonical_serialization_is_separate_gate": True,
        },
        "functions": functions,
        "blocks": block_rows,
        "bindings": binding_rows,
        "values": value_rows,
        "storage": storage_rows,
        "instructions": instructions,
        "calls": call_rows,
        "terminators": terminator_rows,
        "completeness": completeness,
        "errors": list(projected.get("errors", [])),
    }


def build_model(source: str) -> dict[str, Any]:
    return build_model_bytes(source.encode("ascii"))


def encode_model(model: dict[str, Any]) -> str:
    lines = [HEADER]
    for row in model["functions"]:
        lines.append(
            f"F {row['function_id']} {FUNCTION_KIND_CODES[row['kind']]} "
            f"{row['name_start']} {row['name_length']} "
            f"{row['parameter_count']} {row['result_count']}"
        )
    for row in model["blocks"]:
        lines.append(
            f"B {row['function_id']} {row['block_id']} {row['ordinal']} "
            f"{row['instruction_count']} {row['terminator_instruction_id']}"
        )
    for row in model["bindings"]:
        lines.append(
            f"D {row['binding_id']} {row['function_id']} "
            f"{BINDING_KIND_CODES[row['kind']]} {row['type_code']} "
            f"{row['name_start']} {row['name_length']} {int(row['mutable'])} "
            f"{BINDING_TARGET_CODES[row['target_kind']]} {row['target_id']}"
        )
    for row in model["values"]:
        lines.append(
            f"V {row['value_id']} {row['function_id']} "
            f"{VALUE_KIND_CODES[row['kind']]} {TYPE_CODES[row['type']]} "
            f"{row['anchor_start']} {row['anchor_length']} "
            f"{int(row['mutable'])} {row['storage_id']}"
        )
    for row in model["storage"]:
        lines.append(
            f"M {row['function_id']} {row['storage_id']} "
            f"{TYPE_CODES[row['element_type']]} {row['length']} "
            f"{int(row['mutable'])} {row['anchor_start']}"
        )
    for row in model["instructions"]:
        immediate = row.get("immediate")
        if isinstance(immediate, bool):
            immediate = int(immediate)
        if immediate is not None and not isinstance(immediate, int):
            raise SemanticStreamV3Error(
                f"non-integer immediate for instruction {row['instruction_id']} is unsupported"
            )
        aux_a = int(row.get("memory_object", -1))
        aux_b = int(immediate) if immediate is not None else -1
        lines.append(
            f"I {row['instruction_id']} {row['function_index']} "
            f"{row['block_index']} {row['ordinal']} "
            f"{OPCODE_CODES[row['opcode']]} {len(row['result_value_ids'])} "
            f"{len(row['operand_value_ids'])} {aux_a} {aux_b}"
        )
        for ordinal, value_id in enumerate(row["operand_value_ids"]):
            lines.append(f"O {row['instruction_id']} {ordinal} {value_id}")
        for ordinal, value_id in enumerate(row["result_value_ids"]):
            lines.append(f"R {row['instruction_id']} {ordinal} {value_id}")
    for row in model["calls"]:
        lines.append(
            f"C {row['instruction_id']} {CALLEE_KIND_CODES[row['callee_kind']]} "
            f"{row['callee_function_id']} {row['callee_name_start']} "
            f"{row['callee_name_length']} {len(row['argument_value_ids'])} "
            f"{len(row['result_value_ids'])}"
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
                raise SemanticStreamV3Error("jump must have exactly one target")
            negative = int(targets[0])
        elif kind == "branch3":
            if len(targets) != 3:
                raise SemanticStreamV3Error("branch3 must have exactly three targets")
            negative, zero, positive = map(int, targets)
        elif kind == "return":
            values = list(row.get("return_value_ids", []))
            if values:
                return_value = int(values[0])
        lines.append(
            f"T {row['instruction_id']} {TERMINATOR_KIND_CODES[kind]} "
            f"{condition} {negative} {zero} {positive} {return_value}"
        )
    complete = all(bool(value) for value in model["completeness"].values()) and not model["errors"]
    lines.append(f"Z {SEMANTIC_COMPLETE_MASK if complete else 0}")
    return "\n".join(lines) + "\n"


def parse_stream(text: str) -> dict[str, Any]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines or lines[0] != HEADER:
        raise SemanticStreamV3Error("missing or invalid S3IR2 v3 header")
    records: list[dict[str, Any]] = []
    mask: int | None = None
    for line_number, line in enumerate(lines[1:], start=2):
        parts = line.split()
        tag = parts[0]
        if tag not in EXPECTED_FIELDS:
            raise SemanticStreamV3Error(f"line {line_number}: unknown tag {tag}")
        try:
            fields = [int(item) for item in parts[1:]]
        except ValueError as error:
            raise SemanticStreamV3Error(
                f"line {line_number}: non-integer field"
            ) from error
        if len(fields) != EXPECTED_FIELDS[tag]:
            raise SemanticStreamV3Error(
                f"line {line_number}: {tag} expects {EXPECTED_FIELDS[tag]} fields, got {len(fields)}"
            )
        if tag == "Z":
            if mask is not None:
                raise SemanticStreamV3Error("multiple completeness records")
            mask = fields[0]
        records.append({"tag": tag, "fields": fields, "line": line_number})
    if mask is None:
        raise SemanticStreamV3Error("missing completeness record")
    return {
        "schema": SCHEMA,
        "records": records,
        "completeness_mask": mask,
        "complete": mask == SEMANTIC_COMPLETE_MASK,
    }


def _by_tag(parsed: dict[str, Any], tag: str) -> list[list[int]]:
    return [row["fields"] for row in parsed["records"] if row["tag"] == tag]


def verify_stream(parsed: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    functions: set[int] = set()
    blocks: set[tuple[int, int]] = set()
    bindings: dict[int, list[int]] = {}
    values: set[int] = set()
    storage: set[tuple[int, int]] = set()
    instructions: dict[int, tuple[int, int, int, int, int, int]] = {}
    operands: dict[int, list[tuple[int, int]]] = {}
    results: dict[int, list[tuple[int, int]]] = {}
    calls: dict[int, tuple[int, int]] = {}
    call_args: dict[int, list[tuple[int, int]]] = {}
    terminators: dict[int, list[int]] = {}

    for record in parsed["records"]:
        tag, f = record["tag"], record["fields"]
        if tag == "F":
            if f[0] in functions:
                errors.append(f"duplicate function id {f[0]}")
            functions.add(f[0])
        elif tag == "B":
            key = (f[0], f[1])
            if key in blocks:
                errors.append(f"duplicate block {key}")
            blocks.add(key)
        elif tag == "D":
            if f[0] in bindings:
                errors.append(f"duplicate binding id {f[0]}")
            bindings[f[0]] = f
        elif tag == "V":
            if f[0] in values:
                errors.append(f"duplicate value id {f[0]}")
            values.add(f[0])
        elif tag == "M":
            key = (f[0], f[1])
            if key in storage:
                errors.append(f"duplicate storage {key}")
            storage.add(key)
        elif tag == "I":
            if f[0] in instructions:
                errors.append(f"duplicate instruction id {f[0]}")
            instructions[f[0]] = (f[1], f[2], f[4], f[5], f[6], f[7])
        elif tag == "O":
            operands.setdefault(f[0], []).append((f[1], f[2]))
        elif tag == "R":
            results.setdefault(f[0], []).append((f[1], f[2]))
        elif tag == "C":
            calls[f[0]] = (f[5], f[6])
        elif tag == "A":
            call_args.setdefault(f[0], []).append((f[1], f[2]))
        elif tag == "T":
            if f[0] in terminators:
                errors.append(f"duplicate terminator for instruction {f[0]}")
            terminators[f[0]] = f

    for bid, f in bindings.items():
        _, owner, kind, type_code, name_start, name_length, _mutable, target_kind, target_id = f
        if owner not in functions:
            errors.append(f"binding {bid} has unknown function {owner}")
        if kind not in BINDING_KIND_CODES.values():
            errors.append(f"binding {bid} has invalid kind")
        if type_code not in TYPE_CODES.values():
            errors.append(f"binding {bid} has invalid type")
        if name_start < 0 or name_length <= 0:
            errors.append(f"binding {bid} has invalid source anchor")
        if target_kind == BINDING_TARGET_CODES["value"]:
            if target_id not in values:
                errors.append(f"binding {bid} targets unknown value {target_id}")
        elif target_kind == BINDING_TARGET_CODES["storage"]:
            if (owner, target_id) not in storage:
                errors.append(f"binding {bid} targets unknown storage {owner}:{target_id}")
        else:
            errors.append(f"binding {bid} has invalid target kind")

    for record in _by_tag(parsed, "V"):
        value_id, owner, kind, type_code, _start, _length, _mutable, _storage_id = record
        if owner not in functions:
            errors.append(f"value {value_id} has unknown function {owner}")
        if kind not in VALUE_KIND_CODES.values() or type_code not in TYPE_CODES.values():
            errors.append(f"value {value_id} has invalid kind/type")

    for record in _by_tag(parsed, "M"):
        owner, sid, type_code, length, _mutable, anchor = record
        if owner not in functions:
            errors.append(f"storage {owner}:{sid} has unknown function")
        if type_code not in TYPE_CODES.values() or length < 1 or anchor < 0:
            errors.append(f"storage {owner}:{sid} has invalid metadata")

    for iid, (owner, block, opcode, result_count, operand_count, aux_a) in instructions.items():
        if (owner, block) not in blocks:
            errors.append(f"instruction {iid} has unknown block {owner}:{block}")
        if opcode not in OPCODE_CODES.values():
            errors.append(f"instruction {iid} has invalid opcode")
        observed_o = sorted(operands.get(iid, []))
        observed_r = sorted(results.get(iid, []))
        if len(observed_o) != operand_count:
            errors.append(f"instruction {iid} operand count mismatch")
        if len(observed_r) != result_count:
            errors.append(f"instruction {iid} result count mismatch")
        for _ordinal, value_id in observed_o + observed_r:
            if value_id not in values:
                errors.append(f"instruction {iid} references unknown value {value_id}")
        if aux_a >= 0 and (owner, aux_a) not in storage:
            errors.append(f"instruction {iid} references unknown storage {owner}:{aux_a}")

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
                errors.append(f"jump {iid} target shape invalid")
            elif (owner, negative) not in blocks:
                errors.append(f"jump {iid} targets unknown block {negative}")
        elif kind == TERMINATOR_KIND_CODES["branch3"]:
            if condition < 0 or any(target < 0 for target in (negative, zero, positive)):
                errors.append(f"branch3 {iid} is incomplete")
            for target in (negative, zero, positive):
                if (owner, target) not in blocks:
                    errors.append(f"branch3 {iid} targets unknown block {target}")
        else:
            errors.append(f"terminator {iid} has invalid kind")
        for value_id in (condition, return_value):
            if value_id >= 0 and value_id not in values:
                errors.append(f"terminator {iid} references unknown value {value_id}")

    for f in _by_tag(parsed, "B"):
        owner, block, _ordinal, _count, terminator_id = f
        if terminator_id < 0:
            errors.append(f"block {owner}:{block} lacks terminator")
        elif terminator_id not in terminators:
            errors.append(
                f"block {owner}:{block} terminator {terminator_id} missing T record"
            )

    return {
        "schema": "s3.selfhost.semantic-stream-v3-verification.v1",
        "status": "PASS" if parsed["complete"] and not errors else "BLOCKED",
        "complete": parsed["complete"],
        "function_count": len(functions),
        "block_count": len(blocks),
        "binding_count": len(bindings),
        "value_count": len(values),
        "storage_count": len(storage),
        "instruction_count": len(instructions),
        "call_count": len(calls),
        "terminator_count": len(terminators),
        "errors": errors,
    }


def build_stream_bytes(raw_source: bytes) -> tuple[str, dict[str, Any], dict[str, Any]]:
    model = build_model_bytes(raw_source)
    stream = encode_model(model)
    parsed = parse_stream(stream)
    verification = verify_stream(parsed)
    return stream, model, verification


def build_stream(source: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    return build_stream_bytes(source.encode("ascii"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--stream-output", type=Path, required=True)
    parser.add_argument("--model-output", type=Path, required=True)
    parser.add_argument("--verification-output", type=Path, required=True)
    args = parser.parse_args(argv)

    raw_source = args.source.read_bytes()
    stream, model, verification = build_stream_bytes(raw_source)
    args.stream_output.parent.mkdir(parents=True, exist_ok=True)
    args.stream_output.write_text(stream, encoding="utf-8", newline="\n")
    args.model_output.parent.mkdir(parents=True, exist_ok=True)
    args.model_output.write_text(
        json.dumps(model, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    args.verification_output.parent.mkdir(parents=True, exist_ok=True)
    args.verification_output.write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"STATUS={verification['status']}")
    print(f"SOURCE_SHA256={model['source_sha256']}")
    print(f"SOURCE_BYTES={model['source_bytes']}")
    print(f"FUNCTIONS={verification['function_count']}")
    print(f"BINDINGS={verification['binding_count']}")
    print(f"VALUES={verification['value_count']}")
    print(f"STORAGE={verification['storage_count']}")
    print(f"INSTRUCTIONS={verification['instruction_count']}")
    return 0 if verification["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
