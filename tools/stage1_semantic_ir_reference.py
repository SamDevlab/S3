"""Build a deterministic semantic-IR reference for Stage1 self-hosting work.

This tool is an executable architecture oracle, not Stage1 evidence. It lowers an
S3 source with the existing typed Stage0 pipeline and projects that IR into the
five emitter-facing semantic lanes required by the self-hosted Stage1 compiler:

S1 typed value definitions
S2 instruction def/use
S3 call dataflow
S4 complete terminators
S5 canonical serialized IR

Logical semantic value IDs are deliberately independent from physical storage
slots. Missing definitions or unresolved uses fail closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bootstrap.s3.ir import IRFunction, IRInstruction, IRProgram, IROpcode
from bootstrap.s3.pipeline import compile_source

SCHEMA = "s3.selfhost.semantic-ir-reference.v1"
SERIALIZATION_FORMAT = "S3IR2-REFERENCE"
SERIALIZATION_VERSION = 1


class SemanticIRReferenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class _ValueIdentity:
    logical_id: int
    function_index: int
    register: int


def _canonical_json(payload: object) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _source_location(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    to_dict = getattr(value, "to_dict", None)
    if to_dict is None:
        return None
    rendered = to_dict()
    return rendered if isinstance(rendered, dict) else None


def _definition_index(function: IRFunction) -> tuple[dict[int, dict[str, Any]], list[str]]:
    definitions: dict[int, dict[str, Any]] = {}
    errors: list[str] = []

    for ordinal, parameter in enumerate(function.parameters):
        definitions[parameter.register] = {
            "kind": "parameter",
            "parameter_ordinal": ordinal,
            "parameter_name": parameter.name,
            "mutable": False,
        }

    for block_index, block in enumerate(function.blocks):
        for instruction_ordinal, instruction in enumerate(block.instructions):
            for result_ordinal, register in enumerate(instruction.results):
                if register in definitions:
                    errors.append(
                        f"register r{register} in {function.name} has multiple definitions"
                    )
                    continue
                definitions[register] = {
                    "kind": "constant" if instruction.opcode in {IROpcode.CONST, IROpcode.CONST_STR} else "instruction_result",
                    "block_index": block_index,
                    "block_name": block.name,
                    "instruction_ordinal": instruction_ordinal,
                    "result_ordinal": result_ordinal,
                    "opcode": instruction.opcode.value,
                    "immediate": instruction.immediate,
                    "static_string": instruction.static_string,
                }
    return definitions, errors


def _build_value_lane(program: IRProgram) -> tuple[list[dict[str, Any]], dict[tuple[int, int], _ValueIdentity], list[str]]:
    values: list[dict[str, Any]] = []
    identities: dict[tuple[int, int], _ValueIdentity] = {}
    errors: list[str] = []
    next_id = 0

    for function_index, function in enumerate(program.functions):
        definitions, definition_errors = _definition_index(function)
        errors.extend(definition_errors)
        for register in sorted(function.registers, key=lambda item: item.index):
            identity = _ValueIdentity(next_id, function_index, register.index)
            identities[(function_index, register.index)] = identity
            definition = definitions.get(register.index)
            if definition is None:
                errors.append(
                    f"register r{register.index} in {function.name} has no semantic definition"
                )
                definition = {"kind": "unresolved"}
            row: dict[str, Any] = {
                "value_id": next_id,
                "function_index": function_index,
                "function": function.name,
                "register": register.index,
                "type": register.type.value,
                "definition": definition,
            }
            if register.reference_target is not None:
                row["reference"] = {
                    "target_type": register.reference_target.value,
                    "mutable": register.reference_mutable,
                    "is_slice": register.reference_is_slice,
                    "slice_length_register": register.slice_length_register,
                }
            location = _source_location(register.location)
            if location is not None:
                row["source"] = location
            values.append(row)
            next_id += 1

    return values, identities, errors


def _value_id(
    identities: dict[tuple[int, int], _ValueIdentity],
    function_index: int,
    register: int,
    *,
    context: str,
) -> int:
    identity = identities.get((function_index, register))
    if identity is None:
        raise SemanticIRReferenceError(
            f"{context}: unresolved register r{register} in function index {function_index}"
        )
    return identity.logical_id


def _instruction_row(
    function_index: int,
    function: IRFunction,
    block_index: int,
    block_name: str,
    instruction_ordinal: int,
    instruction_id: int,
    instruction: IRInstruction,
    identities: dict[tuple[int, int], _ValueIdentity],
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "instruction_id": instruction_id,
        "function_index": function_index,
        "function": function.name,
        "block_index": block_index,
        "block": block_name,
        "ordinal": instruction_ordinal,
        "opcode": instruction.opcode.value,
        "operand_value_ids": [
            _value_id(
                identities,
                function_index,
                register,
                context=f"instruction {instruction_id} operand",
            )
            for register in instruction.operands
        ],
        "result_value_ids": [
            _value_id(
                identities,
                function_index,
                register,
                context=f"instruction {instruction_id} result",
            )
            for register in instruction.results
        ],
        "targets": list(instruction.targets),
    }
    if instruction.immediate is not None:
        row["immediate"] = instruction.immediate
    if instruction.static_string is not None:
        row["static_string"] = instruction.static_string
    if instruction.callee is not None:
        row["callee"] = instruction.callee
    if instruction.memory is not None:
        row["memory_object"] = instruction.memory
    if instruction.initialization:
        row["initialization"] = True
    location = _source_location(instruction.location)
    if location is not None:
        row["source"] = location
    return row


def _call_kind(program: IRProgram, callee: str | None) -> str:
    if callee is None:
        return "invalid"
    for function in program.functions:
        if function.name == callee:
            return "foreign" if function.external else "internal"
    return "builtin_or_external"


def project_semantic_ir(program: IRProgram, *, source_sha256: str) -> dict[str, Any]:
    values, identities, errors = _build_value_lane(program)
    instructions: list[dict[str, Any]] = []
    calls: list[dict[str, Any]] = []
    terminators: list[dict[str, Any]] = []
    storage: list[dict[str, Any]] = []
    instruction_id = 0

    function_names = {function.name for function in program.functions}

    for function_index, function in enumerate(program.functions):
        for memory in sorted(function.memory_objects, key=lambda item: item.index):
            row: dict[str, Any] = {
                "function_index": function_index,
                "function": function.name,
                "memory_id": memory.index,
                "element_type": memory.element_type.value,
                "length": memory.length,
                "mutable": memory.mutable,
                "identity_status": "IR_MEMORY_IDENTITY_ONLY",
            }
            location = _source_location(memory.location)
            if location is not None:
                row["source"] = location
            storage.append(row)

        for block_index, block in enumerate(function.blocks):
            if not function.external and not block.instructions:
                errors.append(f"non-external block {function.name}:{block.name} is empty")
            for ordinal, instruction in enumerate(block.instructions):
                row = _instruction_row(
                    function_index,
                    function,
                    block_index,
                    block.name,
                    ordinal,
                    instruction_id,
                    instruction,
                    identities,
                )
                instructions.append(row)

                if instruction.opcode is IROpcode.CALL:
                    calls.append(
                        {
                            "instruction_id": instruction_id,
                            "function_index": function_index,
                            "function": function.name,
                            "block": block.name,
                            "callee": instruction.callee,
                            "callee_kind": _call_kind(program, instruction.callee),
                            "callee_resolves_in_module": instruction.callee in function_names,
                            "argument_value_ids": list(row["operand_value_ids"]),
                            "result_value_ids": list(row["result_value_ids"]),
                        }
                    )

                if instruction.is_terminator:
                    term: dict[str, Any] = {
                        "instruction_id": instruction_id,
                        "function_index": function_index,
                        "function": function.name,
                        "block_index": block_index,
                        "block": block.name,
                        "kind": instruction.opcode.value,
                        "targets": list(instruction.targets),
                    }
                    if instruction.opcode is IROpcode.RETURN:
                        term["return_value_ids"] = list(row["operand_value_ids"])
                    elif instruction.opcode is IROpcode.JUMP:
                        if len(instruction.targets) != 1:
                            errors.append(
                                f"jump {function.name}:{block.name} has {len(instruction.targets)} targets"
                            )
                    elif instruction.opcode is IROpcode.BRANCH3:
                        if len(row["operand_value_ids"]) != 1:
                            errors.append(
                                f"branch3 {function.name}:{block.name} requires one condition value"
                            )
                        if len(instruction.targets) != 3:
                            errors.append(
                                f"branch3 {function.name}:{block.name} requires three targets"
                            )
                        term["condition_value_id"] = (
                            row["operand_value_ids"][0]
                            if row["operand_value_ids"]
                            else None
                        )
                    terminators.append(term)
                instruction_id += 1

            if not function.external:
                if not block.instructions or not block.instructions[-1].is_terminator:
                    errors.append(
                        f"block {function.name}:{block.name} lacks a complete terminator"
                    )

    lanes = {
        "typed_values": values,
        "storage_objects": storage,
        "instructions": instructions,
        "calls": calls,
        "terminators": terminators,
    }

    completeness = {
        "typed_value_definitions": not any("no semantic definition" in error or "multiple definitions" in error for error in errors),
        "instruction_def_use": True,
        "call_dataflow": all(call["callee"] is not None for call in calls),
        "complete_terminators": not any("terminator" in error or "branch3" in error or "jump" in error for error in errors),
    }

    if errors:
        completeness["instruction_def_use"] = not any("unresolved register" in error for error in errors)

    payload = {
        "schema": SCHEMA,
        "source_sha256": source_sha256,
        "logical_value_id_policy": "MODULE_MONOTONIC_FUNCTION_REGISTER_MAP",
        "physical_storage_is_semantic_identity": False,
        "lanes": lanes,
        "completeness": completeness,
        "errors": errors,
    }
    serialized = _canonical_json(payload)
    serialization_complete = all(completeness.values()) and not errors
    payload["serialization"] = {
        "format": SERIALIZATION_FORMAT,
        "version": SERIALIZATION_VERSION,
        "canonical_json": True,
        "bytes": len(serialized),
        "sha256": hashlib.sha256(serialized).hexdigest(),
        "canonical_serialized_ir": serialization_complete,
    }
    payload["completeness"]["canonical_serialized_ir"] = serialization_complete
    payload["status"] = "PASS" if serialization_complete else "BLOCKED"
    return payload


def build_reference(source: str) -> dict[str, Any]:
    source_bytes = source.encode("utf-8")
    result = compile_source(source)
    if result.ir is None:
        raise SemanticIRReferenceError("ordinary typed IR is unavailable for this source")
    return project_semantic_ir(
        result.ir,
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    reference = build_reference(args.source.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(reference, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"OUTPUT={args.output}")
    print(f"STATUS={reference['status']}")
    print(f"VALUES={len(reference['lanes']['typed_values'])}")
    print(f"INSTRUCTIONS={len(reference['lanes']['instructions'])}")
    print(f"CALLS={len(reference['lanes']['calls'])}")
    print(f"TERMINATORS={len(reference['lanes']['terminators'])}")
    print(f"SHA256={reference['serialization']['sha256']}")
    return 0 if reference["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
