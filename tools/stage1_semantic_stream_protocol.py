"""Encode, parse, and verify the line-oriented Stage1 S3IR2 semantic stream.

The protocol is intentionally simple enough for the self-hosted S3 Stage1 to emit
without retaining module-global instruction/value arrays. The Python reference
encoder is the executable oracle for the S3 stream primitives.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from tools.stage1_semantic_ir_reference import build_reference

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
}
VALUE_KIND_CODES = {
    "parameter": 1,
    "local_or_storage_binding": 2,
    "constant": 3,
    "instruction_result": 4,
}
CALLEE_KIND_CODES = {
    "internal": 1,
    "foreign": 2,
    "builtin_or_external": 3,
    "invalid": 0,
}
TERMINATOR_KIND_CODES = {"return": 1, "jump": 2, "branch3": 3}

# Stable protocol opcode numbers. Never derive these from Enum ordinal position.
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

COMPLETE_MASK = 1 | 2 | 4 | 8


class SemanticStreamError(ValueError):
    pass


def _field(value: int) -> str:
    return str(int(value))


def _definition_code(value: dict[str, Any]) -> int:
    kind = str(value.get("definition", {}).get("kind", ""))
    return VALUE_KIND_CODES.get(kind, 0)


def _source_identity(value: dict[str, Any]) -> tuple[int, int]:
    # The current Stage0 SourceLocation schema is line/column based, not a lossless
    # byte-span identity. The Stage1 port owns exact byte start/length and should
    # emit them. Reference output therefore uses -1/-1 when unavailable rather
    # than inventing a byte range.
    return -1, -1


def encode_reference(reference: dict[str, Any]) -> str:
    lines: list[str] = ["S3IR2 1"]

    for value in reference["lanes"]["typed_values"]:
        name_start, name_length = _source_identity(value)
        definition = value.get("definition", {})
        mutable = int(bool(definition.get("mutable", False)))
        storage_id = int(definition.get("storage_id", -1))
        lines.append(
            " ".join(
                [
                    "V",
                    _field(value["value_id"]),
                    _field(value["function_index"]),
                    _field(_definition_code(value)),
                    _field(TYPE_CODES[value["type"]]),
                    _field(name_start),
                    _field(name_length),
                    _field(mutable),
                    _field(storage_id),
                ]
            )
        )

    for storage in reference["lanes"].get("storage_objects", []):
        lines.append(
            " ".join(
                [
                    "M",
                    _field(storage["function_index"]),
                    _field(storage["memory_id"]),
                    _field(TYPE_CODES[storage["element_type"]]),
                    _field(storage["length"]),
                    _field(int(bool(storage["mutable"]))),
                ]
            )
        )

    for instruction in reference["lanes"]["instructions"]:
        aux_a = int(instruction.get("memory_object", -1))
        immediate = instruction.get("immediate")
        aux_b = int(immediate) if isinstance(immediate, int) else -1
        lines.append(
            " ".join(
                [
                    "I",
                    _field(instruction["instruction_id"]),
                    _field(instruction["function_index"]),
                    _field(instruction["block_index"]),
                    _field(instruction["ordinal"]),
                    _field(OPCODE_CODES[instruction["opcode"]]),
                    _field(len(instruction["result_value_ids"])),
                    _field(len(instruction["operand_value_ids"])),
                    _field(aux_a),
                    _field(aux_b),
                ]
            )
        )
        for ordinal, value_id in enumerate(instruction["operand_value_ids"]):
            lines.append(f"O {instruction['instruction_id']} {ordinal} {value_id}")
        for ordinal, value_id in enumerate(instruction["result_value_ids"]):
            lines.append(f"R {instruction['instruction_id']} {ordinal} {value_id}")

    for call in reference["lanes"]["calls"]:
        lines.append(
            " ".join(
                [
                    "C",
                    _field(call["instruction_id"]),
                    _field(CALLEE_KIND_CODES[call["callee_kind"]]),
                    _field(-1),
                    _field(-1),
                    _field(-1),
                    _field(len(call["argument_value_ids"])),
                    _field(len(call["result_value_ids"])),
                ]
            )
        )
        for ordinal, value_id in enumerate(call["argument_value_ids"]):
            lines.append(f"A {call['instruction_id']} {ordinal} {value_id}")

    for terminator in reference["lanes"]["terminators"]:
        kind = terminator["kind"]
        condition = int(terminator.get("condition_value_id", -1))
        targets = list(terminator.get("targets", []))
        # Stage0 target names are symbolic strings. The Stage1 stream uses numeric
        # block IDs; reference target IDs use -1 placeholders and semantic parity
        # is checked from the decoded reference model separately.
        negative = -1
        zero = -1
        positive = -1
        return_value = -1
        return_values = terminator.get("return_value_ids", [])
        if return_values:
            return_value = int(return_values[0])
        lines.append(
            " ".join(
                [
                    "T",
                    _field(terminator["instruction_id"]),
                    _field(TERMINATOR_KIND_CODES[kind]),
                    _field(condition),
                    _field(negative),
                    _field(zero),
                    _field(positive),
                    _field(return_value),
                ]
            )
        )
        if kind == "jump" and len(targets) != 1:
            raise SemanticStreamError("reference jump does not have exactly one target")
        if kind == "branch3" and len(targets) != 3:
            raise SemanticStreamError("reference branch3 does not have exactly three targets")

    mask = 0
    completeness = reference["completeness"]
    if completeness.get("typed_value_definitions"):
        mask |= 1
    if completeness.get("instruction_def_use"):
        mask |= 2
    if completeness.get("call_dataflow"):
        mask |= 4
    if completeness.get("complete_terminators"):
        mask |= 8
    lines.append(f"Z {mask}")
    return "\n".join(lines) + "\n"


def parse_stream(text: str) -> dict[str, Any]:
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not raw_lines or raw_lines[0] != "S3IR2 1":
        raise SemanticStreamError("missing or invalid S3IR2 header")

    records: list[dict[str, Any]] = []
    completeness_mask: int | None = None
    for line_number, line in enumerate(raw_lines[1:], start=2):
        parts = line.split()
        tag = parts[0]
        try:
            fields = [int(part) for part in parts[1:]]
        except ValueError as error:
            raise SemanticStreamError(f"line {line_number}: non-integer field") from error

        expected_fields = {
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
        if tag not in expected_fields:
            raise SemanticStreamError(f"line {line_number}: unknown record tag {tag!r}")
        if len(fields) != expected_fields[tag]:
            raise SemanticStreamError(
                f"line {line_number}: {tag} expects {expected_fields[tag]} fields, got {len(fields)}"
            )
        if tag == "Z":
            if completeness_mask is not None:
                raise SemanticStreamError("multiple completeness records")
            completeness_mask = fields[0]
        records.append({"tag": tag, "fields": fields, "line": line_number})

    if completeness_mask is None:
        raise SemanticStreamError("missing completeness record")
    return {
        "schema": "s3.selfhost.semantic-stream.v1",
        "records": records,
        "completeness_mask": completeness_mask,
        "complete": completeness_mask == COMPLETE_MASK,
    }


def verify_stream(parsed: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    value_ids: set[int] = set()
    instruction_ids: set[int] = set()
    result_defs: dict[int, int] = {}
    operand_uses: list[tuple[int, int]] = []
    instruction_result_counts: dict[int, int] = {}
    instruction_operand_counts: dict[int, int] = {}
    observed_results: dict[int, int] = {}
    observed_operands: dict[int, int] = {}
    call_argument_counts: dict[int, int] = {}
    observed_call_arguments: dict[int, int] = {}
    terminator_instructions: set[int] = set()

    for record in parsed["records"]:
        tag = record["tag"]
        fields = record["fields"]
        if tag == "V":
            value_id = fields[0]
            if value_id in value_ids:
                errors.append(f"duplicate value id {value_id}")
            value_ids.add(value_id)
        elif tag == "I":
            instruction_id = fields[0]
            if instruction_id in instruction_ids:
                errors.append(f"duplicate instruction id {instruction_id}")
            instruction_ids.add(instruction_id)
            instruction_result_counts[instruction_id] = fields[5]
            instruction_operand_counts[instruction_id] = fields[6]
        elif tag == "O":
            instruction_id, _ordinal, value_id = fields
            operand_uses.append((instruction_id, value_id))
            observed_operands[instruction_id] = observed_operands.get(instruction_id, 0) + 1
        elif tag == "R":
            instruction_id, _ordinal, value_id = fields
            if value_id in result_defs:
                errors.append(f"value {value_id} is produced by multiple instructions")
            result_defs[value_id] = instruction_id
            observed_results[instruction_id] = observed_results.get(instruction_id, 0) + 1
        elif tag == "C":
            instruction_id = fields[0]
            call_argument_counts[instruction_id] = fields[5]
        elif tag == "A":
            instruction_id, _ordinal, value_id = fields
            operand_uses.append((instruction_id, value_id))
            observed_call_arguments[instruction_id] = observed_call_arguments.get(instruction_id, 0) + 1
        elif tag == "T":
            instruction_id = fields[0]
            if instruction_id in terminator_instructions:
                errors.append(f"duplicate terminator for instruction {instruction_id}")
            terminator_instructions.add(instruction_id)
            condition = fields[2]
            return_value = fields[6]
            if condition >= 0:
                operand_uses.append((instruction_id, condition))
            if return_value >= 0:
                operand_uses.append((instruction_id, return_value))

    for instruction_id, value_id in operand_uses:
        if instruction_id not in instruction_ids:
            errors.append(f"edge references unknown instruction {instruction_id}")
        if value_id not in value_ids:
            errors.append(f"instruction {instruction_id} references unknown value {value_id}")

    for instruction_id in instruction_ids:
        expected_results = instruction_result_counts.get(instruction_id, 0)
        actual_results = observed_results.get(instruction_id, 0)
        if expected_results != actual_results:
            errors.append(
                f"instruction {instruction_id} result count mismatch: expected {expected_results}, got {actual_results}"
            )
        expected_operands = instruction_operand_counts.get(instruction_id, 0)
        actual_operands = observed_operands.get(instruction_id, 0)
        if expected_operands != actual_operands:
            errors.append(
                f"instruction {instruction_id} operand count mismatch: expected {expected_operands}, got {actual_operands}"
            )

    for instruction_id, expected in call_argument_counts.items():
        actual = observed_call_arguments.get(instruction_id, 0)
        if expected != actual:
            errors.append(
                f"call {instruction_id} argument count mismatch: expected {expected}, got {actual}"
            )

    return {
        "schema": "s3.selfhost.semantic-stream-verification.v1",
        "status": "PASS" if not errors and parsed["complete"] else "BLOCKED",
        "complete": parsed["complete"],
        "value_count": len(value_ids),
        "instruction_count": len(instruction_ids),
        "terminator_count": len(terminator_instructions),
        "errors": errors,
    }


def build_stream_from_source(source: str) -> tuple[str, dict[str, Any], dict[str, Any]]:
    reference = build_reference(source)
    stream = encode_reference(reference)
    parsed = parse_stream(stream)
    verification = verify_stream(parsed)
    return stream, reference, verification


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--stream-output", type=Path, required=True)
    parser.add_argument("--verification-output", type=Path, required=True)
    args = parser.parse_args(argv)

    stream, _reference, verification = build_stream_from_source(
        args.source.read_text(encoding="utf-8")
    )
    args.stream_output.parent.mkdir(parents=True, exist_ok=True)
    args.stream_output.write_text(stream, encoding="utf-8", newline="\n")
    args.verification_output.parent.mkdir(parents=True, exist_ok=True)
    args.verification_output.write_text(
        json.dumps(verification, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"STREAM={args.stream_output}")
    print(f"VERIFICATION={args.verification_output}")
    print(f"STATUS={verification['status']}")
    return 0 if verification["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
