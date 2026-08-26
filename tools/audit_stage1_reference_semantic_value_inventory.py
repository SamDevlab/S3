"""Inventory semantic-value pressure from the trusted Stage0 typed pipeline.

This is a hosted oracle only.  It deliberately does not promote Stage1, does
not mutate the canonical compiler source, and does not require Stage1 IR-v2 to
copy the reference IR one-for-one.  Its job is to make omissions and capacity
assumptions visible before a native Stage1 candidate is promoted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

from bootstrap.s3 import ast
from bootstrap.s3.ir import IROpcode, TERMINATOR_OPCODES
from bootstrap.s3.pipeline import compile_source


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "reference-semantic-value-inventory-contract.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "reference-semantic-value-inventory.json"
)
DEFAULT_MANIFEST = ROOT / "selfhost" / "compiler" / "compiler-sources.json"
NUMERIC_TYPES = {"trit", "tryte", "i64"}


class InventoryError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_source(manifest_path: Path) -> tuple[Path, bytes, dict[str, Any]]:
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != "s3.compiler.sources.v1":
        raise InventoryError("canonical compiler manifest schema mismatch")
    sources = document.get("sources")
    if not isinstance(sources, list) or len(sources) != 1 or document.get("source_count") != 1:
        raise InventoryError("reference inventory currently requires exactly one canonical compiler source")
    entry = sources[0]
    if not isinstance(entry, dict):
        raise InventoryError("canonical source entry is malformed")
    relative = entry.get("path")
    expected_sha = entry.get("sha256")
    if not isinstance(relative, str) or not isinstance(expected_sha, str):
        raise InventoryError("canonical source entry lacks path/sha256")
    source_path = (ROOT / relative).resolve()
    try:
        source_path.relative_to(ROOT.resolve())
    except ValueError as error:
        raise InventoryError("canonical source path escapes repository root") from error
    data = source_path.read_bytes()
    actual_sha = _sha256(data)
    if actual_sha != expected_sha:
        raise InventoryError(
            f"canonical source SHA mismatch: manifest={expected_sha} actual={actual_sha}"
        )
    if document.get("total_bytes") != len(data):
        raise InventoryError("canonical source byte count differs from manifest")
    return source_path, data, document


def _type_key(type_name: object) -> str:
    if isinstance(type_name, ast.TypeName):
        return type_name.value
    return str(type_name)


def _value_repr(value: object) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "nan"
        if math.isinf(value):
            return "inf" if value > 0 else "-inf"
        return value.hex()
    return repr(value)


def _walk_dataclasses(value: object, seen: set[int] | None = None) -> Iterator[object]:
    visited = set() if seen is None else seen
    if value is None or isinstance(value, (str, bytes, int, float, bool, Enum)):
        return
    identity = id(value)
    if identity in visited:
        return
    visited.add(identity)
    if isinstance(value, (tuple, list, set, frozenset)):
        for item in value:
            yield from _walk_dataclasses(item, visited)
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk_dataclasses(item, visited)
        return
    if not is_dataclass(value):
        return
    yield value
    for field in fields(value):
        yield from _walk_dataclasses(getattr(value, field.name), visited)


def _semantic_constant_inventory(compilation) -> dict[str, Any]:
    model = compilation.semantic_model
    occurrences: list[tuple[str, str]] = []
    numeric_occurrences: list[tuple[str, int]] = []
    for node in _walk_dataclasses(compilation.ast):
        identity = id(node)
        if identity not in model.constant_values or identity not in model.expression_types:
            continue
        type_key = _type_key(model.expression_types[identity])
        value = model.constant_values[identity]
        occurrences.append((type_key, _value_repr(value)))
        if type_key in NUMERIC_TYPES and isinstance(value, int) and not isinstance(value, bool):
            numeric_occurrences.append((type_key, value))
    unique = sorted(set(occurrences))
    unique_numeric = sorted(set(numeric_occurrences), key=lambda item: (item[0], item[1]))
    return {
        "constant_expression_occurrences": len(occurrences),
        "unique_typed_constant_expressions": len(unique),
        "numeric_constant_expression_occurrences": len(numeric_occurrences),
        "unique_typed_numeric_constant_expressions": len(unique_numeric),
        "unique_typed_numeric_constants": [
            {"type": type_name, "value": value}
            for type_name, value in unique_numeric
        ],
    }


def _reference_ir_inventory(compilation, *, inline_min: int, inline_max: int) -> dict[str, Any]:
    ir, _ = compilation.require_ordinary_artifacts()
    opcode_histogram: Counter[str] = Counter()
    operand_use_histogram: Counter[str] = Counter()
    typed_constant_occurrences: list[tuple[str, str]] = []
    typed_numeric_constant_occurrences: list[tuple[str, int]] = []
    result_definitions: set[tuple[str, int]] = set()
    nonconstant_result_definitions: set[tuple[str, int]] = set()
    parameter_definitions: set[tuple[str, int]] = set()
    call_count = 0
    call_argument_uses = 0
    load_count = 0
    store_count = 0
    terminator_count = 0
    operand_use_count = 0
    block_count = 0
    instruction_count = 0
    register_count = 0
    memory_object_count = 0
    external_function_count = 0

    for function in ir.functions:
        if function.external:
            external_function_count += 1
        register_types = {register.index: register.type.value for register in function.registers}
        register_count += len(function.registers)
        memory_object_count += len(function.memory_objects)
        for parameter in function.parameters:
            parameter_definitions.add((function.name, parameter.register))
        block_count += len(function.blocks)
        for block in function.blocks:
            for instruction in block.instructions:
                instruction_count += 1
                opcode = instruction.opcode.value
                opcode_histogram[opcode] += 1
                operand_count = len(instruction.operands)
                operand_use_count += operand_count
                operand_use_histogram[opcode] += operand_count
                for result in instruction.results:
                    key = (function.name, result)
                    result_definitions.add(key)
                    if instruction.opcode not in {IROpcode.CONST, IROpcode.CONST_STR}:
                        nonconstant_result_definitions.add(key)
                if instruction.opcode is IROpcode.CONST:
                    if len(instruction.results) != 1 or instruction.immediate is None:
                        raise InventoryError("reference CONST instruction lacks exactly one result/immediate")
                    result = instruction.results[0]
                    type_key = register_types[result]
                    value = instruction.immediate
                    typed_constant_occurrences.append((type_key, _value_repr(value)))
                    if type_key in NUMERIC_TYPES and isinstance(value, int) and not isinstance(value, bool):
                        typed_numeric_constant_occurrences.append((type_key, value))
                if instruction.opcode is IROpcode.CALL:
                    call_count += 1
                    call_argument_uses += operand_count
                if instruction.opcode is IROpcode.LOAD:
                    load_count += 1
                if instruction.opcode is IROpcode.STORE:
                    store_count += 1
                if instruction.opcode in TERMINATOR_OPCODES:
                    terminator_count += 1

    unique_constants = sorted(set(typed_constant_occurrences))
    unique_numeric = sorted(set(typed_numeric_constant_occurrences), key=lambda item: (item[0], item[1]))
    wide_numeric = [
        (type_name, value)
        for type_name, value in unique_numeric
        if value < inline_min or value > inline_max
    ]
    # Planned semantic-value representation uses one header slot per interned
    # numeric constant, plus one raw i64 extension slot for each wide literal.
    interned_numeric_slots = len(unique_numeric) + len(wide_numeric)
    reference_dynamic_shape_pressure = (
        interned_numeric_slots + len(nonconstant_result_definitions)
    )
    return {
        "function_count": len(ir.functions),
        "external_function_count": external_function_count,
        "parameter_count": len(parameter_definitions),
        "memory_object_count": memory_object_count,
        "block_count": block_count,
        "instruction_count": instruction_count,
        "register_count": register_count,
        "result_register_count": len(result_definitions),
        "non_constant_result_register_count": len(nonconstant_result_definitions),
        "operand_use_count": operand_use_count,
        "opcode_histogram": dict(sorted(opcode_histogram.items())),
        "operand_use_histogram": dict(sorted(operand_use_histogram.items())),
        "typed_constant_occurrences": len(typed_constant_occurrences),
        "unique_typed_constants": len(unique_constants),
        "typed_numeric_constant_occurrences": len(typed_numeric_constant_occurrences),
        "unique_typed_numeric_constants": len(unique_numeric),
        "wide_unique_typed_integer_constants": len(wide_numeric),
        "wide_typed_integer_constants": [
            {"type": type_name, "value": value}
            for type_name, value in wide_numeric
        ],
        "interned_numeric_constant_physical_slots": interned_numeric_slots,
        "reference_dynamic_shape_pressure_slots": reference_dynamic_shape_pressure,
        "call_count": call_count,
        "call_argument_operand_uses": call_argument_uses,
        "load_count": load_count,
        "store_count": store_count,
        "terminator_count": terminator_count,
    }


def audit(contract: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    if contract.get("schema") != "s3.selfhost.reference-semantic-value-inventory-contract.v1":
        raise InventoryError("reference semantic value inventory contract schema mismatch")
    storage = contract.get("planned_stage1_value_storage")
    if not isinstance(storage, dict):
        raise InventoryError("contract lacks planned_stage1_value_storage")
    capacity = storage.get("total_physical_slots")
    inline_min = storage.get("inline_signed_literal_min")
    inline_max = storage.get("inline_signed_literal_max")
    if not all(isinstance(item, int) and not isinstance(item, bool) for item in (capacity, inline_min, inline_max)):
        raise InventoryError("contract storage capacities/ranges must be integers")

    source_path, source_bytes, manifest = _canonical_source(manifest_path.resolve())
    source = source_bytes.decode("utf-8")
    compilation = compile_source(source, optimization="O0")
    semantic = _semantic_constant_inventory(compilation)
    reference = _reference_ir_inventory(
        compilation,
        inline_min=inline_min,
        inline_max=inline_max,
    )
    reference_pressure = reference["reference_dynamic_shape_pressure_slots"]
    exceeds = reference_pressure > capacity
    next_step = (
        "PROVE_COMPACTION_OR_DESIGN_BANKED_SEMANTIC_VALUE_STORAGE"
        if exceeds
        else "RECONCILE_REFERENCE_VALUE_ORACLE_WITH_NATIVE_PARAMETER_LOCAL_COUNTS"
    )
    return {
        "schema": "s3.selfhost.reference-semantic-value-inventory.v1",
        "status": "PASS_HOSTED_REFERENCE_VALUE_INVENTORY",
        "authority": "HOSTED_REFERENCE_ORACLE_ONLY",
        "native_evidence": False,
        "canonical_source_mutated": False,
        "canonical_source": {
            "path": str(source_path),
            "sha256": _sha256(source_bytes),
            "bytes": len(source_bytes),
            "manifest": manifest,
        },
        "semantic_model": semantic,
        "reference_ir": reference,
        "candidate_stage1_storage": {
            "physical_slots": capacity,
            "inline_literal_min": inline_min,
            "inline_literal_max": inline_max,
            "reference_dynamic_shape_pressure_slots": reference_pressure,
            "reference_shape_exceeds_candidate_slots": exceeds,
            "warning": (
                "Reference IR shape is not a one-for-one Stage1 architecture mandate. "
                "If Stage1 uses fewer values, the reduction must be justified by a real "
                "lowering/compaction representation and verified def-use, not by dropping uses."
            ),
        },
        "qualification": {
            "stage1_native_pass": False,
            "stage1_certified_for_stage2": False,
            "stage2_allowed": False,
            "full_self_hosting": False,
            "next": next_step,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    try:
        contract = json.loads(args.contract.resolve().read_text(encoding="utf-8"))
        if not isinstance(contract, dict):
            raise InventoryError("contract must be a JSON object")
        result = audit(contract, args.manifest)
    except (InventoryError, UnicodeDecodeError, json.JSONDecodeError) as error:
        parser.exit(2, f"reference semantic value inventory blocked: {error}\n")
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"SOURCE_SHA256={result['canonical_source']['sha256']}")
    print(f"REFERENCE_INSTRUCTIONS={result['reference_ir']['instruction_count']}")
    print(f"REFERENCE_RESULTS={result['reference_ir']['result_register_count']}")
    print(f"REFERENCE_NONCONST_RESULTS={result['reference_ir']['non_constant_result_register_count']}")
    print(f"REFERENCE_UNIQUE_TYPED_NUMERIC_CONSTANTS={result['reference_ir']['unique_typed_numeric_constants']}")
    print(f"REFERENCE_DYNAMIC_SHAPE_PRESSURE={result['reference_ir']['reference_dynamic_shape_pressure_slots']}")
    print(f"CANDIDATE_VALUE_SLOTS={result['candidate_stage1_storage']['physical_slots']}")
    print(f"REFERENCE_SHAPE_EXCEEDS_CANDIDATE={result['candidate_stage1_storage']['reference_shape_exceeds_candidate_slots']}")
    print("NATIVE_EVIDENCE=False")
    print(f"NEXT={result['qualification']['next']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
