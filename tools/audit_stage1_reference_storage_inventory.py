"""Inventory canonical storage semantics from the trusted Stage0 typed IR.

Hosted oracle only.  Source locations are used to correlate memory objects with
source declarations/array parameters/for induction variables.  Unmatched memory
objects stay explicitly classified as lowering temporaries instead of being
misreported as source locals.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from bootstrap.s3 import ast
from bootstrap.s3.ir import IROpcode
from bootstrap.s3.pipeline import compile_source
from tools.audit_stage1_reference_semantic_value_inventory import (
    InventoryError,
    _canonical_source,
    _sha256,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "reference-storage-inventory-contract.json"
)
DEFAULT_MANIFEST = ROOT / "selfhost" / "compiler" / "compiler-sources.json"
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "reference-storage-inventory.json"
)


class StorageInventoryError(RuntimeError):
    pass


def _type_display(type_name: ast.DeclaredType) -> str:
    if isinstance(type_name, ast.TypeName):
        return type_name.value
    if isinstance(type_name, ast.ArrayType):
        return f"{_type_display(type_name.element_type)}[{type_name.length}]"
    if isinstance(type_name, ast.ReferenceType):
        return ("mut " if type_name.mutable else "") + "&" + _type_display(type_name.target)
    if isinstance(type_name, ast.SliceType):
        return ("mut " if type_name.mutable else "") + "&[" + type_name.element_type.value + "]"
    if isinstance(type_name, ast.NominalType):
        return type_name.name
    if isinstance(type_name, ast.TypeParameterType):
        return type_name.name
    return str(type_name)


def _origin_record(
    kind: str,
    name: str,
    declared_type: ast.DeclaredType,
    mutable: bool,
    offset: int,
    *,
    extent: int | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "name": name,
        "declared_type": _type_display(declared_type),
        "mutable": mutable,
        "extent": extent,
        "offset": offset,
    }


def _collect_block_origins(block: ast.Block, target: dict[int, list[dict[str, Any]]]) -> None:
    for statement in block.statements:
        if isinstance(statement, ast.VariableDeclaration):
            kind = (
                "local_array_declaration"
                if isinstance(statement.type_name, ast.ArrayType)
                else "local_scalar_declaration"
            )
            extent = statement.type_name.length if isinstance(statement.type_name, ast.ArrayType) else 1
            target[statement.location.offset].append(
                _origin_record(
                    kind,
                    statement.name,
                    statement.type_name,
                    statement.mutable,
                    statement.location.offset,
                    extent=extent,
                )
            )
        elif isinstance(statement, ast.ForStatement):
            target[statement.location.offset].append(
                _origin_record(
                    "for_induction_storage",
                    statement.variable_name,
                    statement.variable_type,
                    True,
                    statement.location.offset,
                    extent=1,
                )
            )
            _collect_block_origins(statement.body, target)
        elif isinstance(statement, ast.WhileStatement):
            _collect_block_origins(statement.body, target)
        elif isinstance(statement, ast.SwitchStatement):
            for case in statement.cases:
                _collect_block_origins(case.body, target)
        elif isinstance(statement, ast.SelectStatement):
            for arm in statement.arms:
                _collect_block_origins(arm.body, target)


def _source_origins(compilation) -> dict[str, dict[int, list[dict[str, Any]]]]:
    result: dict[str, dict[int, list[dict[str, Any]]]] = {}
    for function in compilation.ast.functions:
        offsets: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for parameter in function.parameters:
            if isinstance(parameter.type_name, ast.ArrayType):
                offsets[parameter.location.offset].append(
                    _origin_record(
                        "array_parameter",
                        parameter.name,
                        parameter.type_name,
                        False,
                        parameter.location.offset,
                        extent=parameter.type_name.length,
                    )
                )
        _collect_block_origins(function.body, offsets)
        result[function.name] = dict(offsets)
    return result


def _const_definitions(function) -> dict[int, object]:
    result: dict[int, object] = {}
    for block in function.blocks:
        for instruction in block.instructions:
            if (
                instruction.opcode is IROpcode.CONST
                and len(instruction.results) == 1
                and instruction.immediate is not None
            ):
                result[instruction.results[0]] = instruction.immediate
    return result


def _origin_for_memory(
    function_name: str,
    memory,
    origins: dict[str, dict[int, list[dict[str, Any]]]],
) -> tuple[str, dict[str, Any] | None, bool]:
    if memory.location is None:
        return "lowering_temporary_or_projection", None, False
    candidates = origins.get(function_name, {}).get(memory.location.offset, [])
    if len(candidates) == 1:
        return str(candidates[0]["kind"]), candidates[0], False
    if len(candidates) > 1:
        return "ambiguous_source_origin", None, True
    return "lowering_temporary_or_projection", None, False


def audit(contract: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    if contract.get("schema") != "s3.selfhost.reference-storage-inventory-contract.v1":
        raise StorageInventoryError("reference storage inventory contract schema mismatch")

    source_path, source_bytes, manifest = _canonical_source(manifest_path.resolve())
    compilation = compile_source(source_bytes.decode("utf-8"), optimization="O0")
    ir, _ = compilation.require_ordinary_artifacts()
    origins = _source_origins(compilation)

    memory_kind_histogram: Counter[str] = Counter()
    memory_element_histogram: Counter[str] = Counter()
    memory_extent_histogram: Counter[str] = Counter()
    load_index_type_histogram: Counter[str] = Counter()
    store_index_type_histogram: Counter[str] = Counter()
    access_kind_histogram: Counter[str] = Counter()
    violations: list[dict[str, Any]] = []
    memory_reports: list[dict[str, Any]] = []
    access_reports: list[dict[str, Any]] = []
    load_count = 0
    store_count = 0
    initialization_store_count = 0
    scalar_storage_access_count = 0
    scalar_zero_index_access_count = 0
    scalar_nonzero_or_unknown: list[dict[str, Any]] = []
    array_access_count = 0
    i64_index_access_count = 0
    tryte_index_access_count = 0
    ambiguous_origin_count = 0

    for function in ir.functions:
        if function.external:
            continue
        register_types = {register.index: register.type.value for register in function.registers}
        constants = _const_definitions(function)
        memory_by_id = {memory.index: memory for memory in function.memory_objects}
        origin_by_memory: dict[int, tuple[str, dict[str, Any] | None, bool]] = {}

        for memory in function.memory_objects:
            kind, origin, ambiguous = _origin_for_memory(function.name, memory, origins)
            origin_by_memory[memory.index] = (kind, origin, ambiguous)
            memory_kind_histogram[kind] += 1
            memory_element_histogram[memory.element_type.value] += 1
            memory_extent_histogram[str(memory.length)] += 1
            ambiguous_origin_count += int(ambiguous)

            if origin is not None:
                expected_extent = origin.get("extent")
                if kind in {"local_scalar_declaration", "for_induction_storage"} and memory.length != 1:
                    violations.append(
                        {
                            "kind": "SCALAR_STORAGE_EXTENT_MISMATCH",
                            "function": function.name,
                            "memory": memory.index,
                            "expected": 1,
                            "actual": memory.length,
                            "origin": origin,
                        }
                    )
                if kind in {"local_array_declaration", "array_parameter"} and isinstance(expected_extent, int) and memory.length != expected_extent:
                    violations.append(
                        {
                            "kind": "ARRAY_STORAGE_EXTENT_MISMATCH",
                            "function": function.name,
                            "memory": memory.index,
                            "expected": expected_extent,
                            "actual": memory.length,
                            "origin": origin,
                        }
                    )
                if kind == "array_parameter" and memory.mutable:
                    violations.append(
                        {
                            "kind": "ARRAY_PARAMETER_STORAGE_UNEXPECTEDLY_MUTABLE",
                            "function": function.name,
                            "memory": memory.index,
                            "origin": origin,
                        }
                    )

            memory_reports.append(
                {
                    "function": function.name,
                    "memory": memory.index,
                    "element_type": memory.element_type.value,
                    "length": memory.length,
                    "mutable": memory.mutable,
                    "source": None if memory.location is None else memory.location.to_dict(),
                    "origin_kind": kind,
                    "origin": origin,
                    "origin_ambiguous": ambiguous,
                }
            )

        for block in function.blocks:
            for position, instruction in enumerate(block.instructions):
                if instruction.opcode not in {IROpcode.LOAD, IROpcode.STORE}:
                    continue
                if instruction.memory is None or instruction.memory not in memory_by_id:
                    violations.append(
                        {
                            "kind": "ACCESS_MISSING_MEMORY",
                            "function": function.name,
                            "block": block.name,
                            "position": position,
                        }
                    )
                    continue
                memory = memory_by_id[instruction.memory]
                origin_kind, origin, _ = origin_by_memory[instruction.memory]
                expected_operands = 1 if instruction.opcode is IROpcode.LOAD else 2
                if len(instruction.operands) != expected_operands:
                    violations.append(
                        {
                            "kind": "ACCESS_OPERAND_CARDINALITY",
                            "function": function.name,
                            "block": block.name,
                            "position": position,
                            "opcode": instruction.opcode.value,
                            "expected": expected_operands,
                            "actual": len(instruction.operands),
                        }
                    )
                    continue

                index_register = instruction.operands[0]
                index_type = register_types.get(index_register)
                index_constant = constants.get(index_register)
                if index_type not in {"tryte", "i64"}:
                    violations.append(
                        {
                            "kind": "INVALID_MEMORY_INDEX_TYPE",
                            "function": function.name,
                            "block": block.name,
                            "position": position,
                            "opcode": instruction.opcode.value,
                            "index_type": index_type,
                        }
                    )
                if index_type == "tryte":
                    tryte_index_access_count += 1
                elif index_type == "i64":
                    i64_index_access_count += 1

                if instruction.opcode is IROpcode.LOAD:
                    load_count += 1
                    load_index_type_histogram[str(index_type)] += 1
                    if len(instruction.results) != 1:
                        violations.append(
                            {
                                "kind": "LOAD_RESULT_CARDINALITY",
                                "function": function.name,
                                "block": block.name,
                                "position": position,
                            }
                        )
                    else:
                        result_type = register_types.get(instruction.results[0])
                        if result_type != memory.element_type.value:
                            violations.append(
                                {
                                    "kind": "LOAD_RESULT_TYPE_MISMATCH",
                                    "function": function.name,
                                    "block": block.name,
                                    "position": position,
                                    "expected": memory.element_type.value,
                                    "actual": result_type,
                                }
                            )
                else:
                    store_count += 1
                    store_index_type_histogram[str(index_type)] += 1
                    initialization_store_count += int(instruction.initialization)
                    value_type = register_types.get(instruction.operands[1])
                    if value_type != memory.element_type.value:
                        violations.append(
                            {
                                "kind": "STORE_VALUE_TYPE_MISMATCH",
                                "function": function.name,
                                "block": block.name,
                                "position": position,
                                "expected": memory.element_type.value,
                                "actual": value_type,
                            }
                        )

                source_scalar = origin_kind in {
                    "local_scalar_declaration",
                    "for_induction_storage",
                }
                source_array = origin_kind in {
                    "local_array_declaration",
                    "array_parameter",
                }
                if source_scalar:
                    scalar_storage_access_count += 1
                    access_kind_histogram["source_scalar_storage"] += 1
                    if index_constant == 0:
                        scalar_zero_index_access_count += 1
                    else:
                        item = {
                            "function": function.name,
                            "block": block.name,
                            "position": position,
                            "opcode": instruction.opcode.value,
                            "memory": memory.index,
                            "index_type": index_type,
                            "index_constant": index_constant,
                            "origin": origin,
                        }
                        scalar_nonzero_or_unknown.append(item)
                        violations.append(
                            {"kind": "SCALAR_STORAGE_INDEX_NOT_PROVEN_ZERO", **item}
                        )
                elif source_array:
                    array_access_count += 1
                    access_kind_histogram["source_array_storage"] += 1
                else:
                    access_kind_histogram[origin_kind] += 1

                if len(access_reports) < 256:
                    access_reports.append(
                        {
                            "function": function.name,
                            "block": block.name,
                            "position": position,
                            "opcode": instruction.opcode.value,
                            "memory": memory.index,
                            "memory_length": memory.length,
                            "memory_element_type": memory.element_type.value,
                            "origin_kind": origin_kind,
                            "index_register": index_register,
                            "index_type": index_type,
                            "index_constant": index_constant,
                            "initialization": bool(instruction.initialization),
                        }
                    )

    declared_kinds = {
        "local_scalar_declaration",
        "local_array_declaration",
        "array_parameter",
        "for_induction_storage",
    }
    declared_storage_count = sum(memory_kind_histogram[kind] for kind in declared_kinds)
    temporary_count = memory_kind_histogram["lowering_temporary_or_projection"]
    passed = not violations and ambiguous_origin_count == 0

    return {
        "schema": "s3.selfhost.reference-storage-inventory.v1",
        "status": (
            "PASS_HOSTED_REFERENCE_STORAGE_INVENTORY"
            if passed
            else "BLOCKED_REFERENCE_STORAGE_INVARIANT_VIOLATION"
        ),
        "authority": "HOSTED_REFERENCE_ORACLE_ONLY",
        "native_evidence": False,
        "canonical_source_mutated": False,
        "canonical_source": {
            "path": str(source_path),
            "sha256": _sha256(source_bytes),
            "bytes": len(source_bytes),
            "manifest": manifest,
        },
        "aggregate": {
            "memory_object_count": sum(memory_kind_histogram.values()),
            "declared_storage_memory_count": declared_storage_count,
            "lowering_temporary_memory_count": temporary_count,
            "ambiguous_origin_count": ambiguous_origin_count,
            "memory_origin_kind_histogram": dict(sorted(memory_kind_histogram.items())),
            "memory_element_type_histogram": dict(sorted(memory_element_histogram.items())),
            "memory_extent_histogram": dict(sorted(memory_extent_histogram.items(), key=lambda item: int(item[0]))),
            "load_count": load_count,
            "store_count": store_count,
            "initialization_store_count": initialization_store_count,
            "load_index_type_histogram": dict(sorted(load_index_type_histogram.items())),
            "store_index_type_histogram": dict(sorted(store_index_type_histogram.items())),
            "tryte_index_access_count": tryte_index_access_count,
            "i64_index_access_count": i64_index_access_count,
            "scalar_storage_access_count": scalar_storage_access_count,
            "scalar_zero_index_access_count": scalar_zero_index_access_count,
            "scalar_nonzero_or_unknown_index_access_count": len(scalar_nonzero_or_unknown),
            "array_access_count": array_access_count,
            "access_origin_kind_histogram": dict(sorted(access_kind_histogram.items())),
        },
        "memory_objects": memory_reports,
        "access_samples": access_reports,
        "scalar_nonzero_or_unknown_index_accesses": scalar_nonzero_or_unknown,
        "violations": violations,
        "qualification": {
            "reference_storage_invariants": "PASS" if passed else "FAIL",
            "stage1_native_pass": False,
            "stage1_certified_for_stage2": False,
            "stage2_allowed": False,
            "full_self_hosting": False,
            "next": (
                "DIFFERENTIAL_NATIVE_IR_V2_STORAGE_MUST_ACCOUNT_FOR_REFERENCE_STORAGE_SEMANTICS"
                if passed
                else "REPAIR_REFERENCE_ORACLE_OR_UNDERLYING_TYPED_IR_STORAGE_INVARIANT"
            ),
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
            raise StorageInventoryError("contract must be a JSON object")
        result = audit(contract, args.manifest)
    except (StorageInventoryError, InventoryError, UnicodeDecodeError, json.JSONDecodeError) as error:
        parser.exit(2, f"reference storage inventory blocked: {error}\n")

    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    aggregate = result["aggregate"]
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"MEMORY_OBJECTS={aggregate['memory_object_count']}")
    print(f"DECLARED_STORAGE={aggregate['declared_storage_memory_count']}")
    print(f"LOWERING_TEMPORARIES={aggregate['lowering_temporary_memory_count']}")
    print(f"LOADS={aggregate['load_count']}")
    print(f"STORES={aggregate['store_count']}")
    print(f"TRYTE_INDEX_ACCESSES={aggregate['tryte_index_access_count']}")
    print(f"I64_INDEX_ACCESSES={aggregate['i64_index_access_count']}")
    print(f"SCALAR_ZERO_INDEX_VIOLATIONS={aggregate['scalar_nonzero_or_unknown_index_access_count']}")
    print("NATIVE_EVIDENCE=False")
    print(f"NEXT={result['qualification']['next']}")
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
