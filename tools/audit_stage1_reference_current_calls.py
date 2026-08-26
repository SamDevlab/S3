"""Audit current Stage1 call semantics from AST and typed O0 IR.

This is a hosted source-bound oracle.  It deliberately keeps AST call
expressions, O0 IR CALL instructions, and native Stage1 physical call records as
separate domains.  It never chooses or certifies physical Stage1 capacity.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Iterator

from bootstrap.s3.ast import (
    CallExpression,
    ForeignFunctionDeclaration,
    FunctionDeclaration,
    Program,
)
from bootstrap.s3.ir import IROpcode
from bootstrap.s3.pipeline import compile_source


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1" / "reference-current-call-inventory-contract.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" / "reference-current-call-inventory.json"
)


class CurrentCallInventoryError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise CurrentCallInventoryError(f"{label} is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise CurrentCallInventoryError(f"{label} is invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise CurrentCallInventoryError(f"{label} must be a JSON object")
    return value


def _walk(value: object) -> Iterator[object]:
    """Generic dataclass walker independent from any Program.walk convenience API."""

    if value is None or isinstance(value, (str, bytes, int, float, bool, Enum)):
        return
    yield value
    if isinstance(value, tuple | list):
        for item in value:
            yield from _walk(item)
        return
    if isinstance(value, dict):
        for item in value.values():
            yield from _walk(item)
        return
    if is_dataclass(value) and not isinstance(value, type):
        for field in fields(value):
            yield from _walk(getattr(value, field.name))


def _kind(callee: str | None, *, internal_names: set[str], foreign_names: set[str]) -> str:
    if callee is None:
        return "dynamic_or_nonidentifier"
    if callee in internal_names:
        return "internal"
    if callee in foreign_names:
        return "foreign"
    return "builtin_or_other"


def _location_offset(node: object) -> int | None:
    location = getattr(node, "location", None)
    offset = getattr(location, "offset", None)
    return offset if isinstance(offset, int) and not isinstance(offset, bool) and offset >= 0 else None


def _ast_inventory(program: Program) -> dict[str, Any]:
    internal_names = {function.name for function in program.functions}
    foreign_names = {function.name for function in program.foreign_functions}
    arity = Counter[int]()
    per_callee = Counter[str]()
    per_caller = Counter[str]()
    kinds = Counter[str]()
    total_arguments = 0
    max_arity = 0
    call_sites: list[dict[str, Any]] = []

    for function in program.functions:
        for node in _walk(function.body):
            if not isinstance(node, CallExpression):
                continue
            callee = node.simple_function_name
            argument_count = len(node.arguments)
            call_kind = _kind(callee, internal_names=internal_names, foreign_names=foreign_names)
            arity[argument_count] += 1
            total_arguments += argument_count
            max_arity = max(max_arity, argument_count)
            kinds[call_kind] += 1
            per_caller[function.name] += 1
            per_callee[callee if callee is not None else "<dynamic>"] += 1
            call_sites.append(
                {
                    "caller": function.name,
                    "callee": callee,
                    "kind": call_kind,
                    "arity": argument_count,
                    "source_offset": _location_offset(node),
                }
            )

    total = len(call_sites)
    return {
        "total_call_expressions": total,
        "total_argument_occurrences": total_arguments,
        "max_arity": max_arity,
        "arity_histogram": {str(key): arity[key] for key in sorted(arity)},
        "simple_identifier_calls": total - kinds["dynamic_or_nonidentifier"],
        "dynamic_or_nonidentifier_callees": kinds["dynamic_or_nonidentifier"],
        "internal_calls": kinds["internal"],
        "foreign_calls": kinds["foreign"],
        "builtin_or_other_calls": kinds["builtin_or_other"],
        "per_callee": dict(sorted(per_callee.items())),
        "per_caller": dict(sorted(per_caller.items())),
        "call_sites": call_sites,
    }


def _ir_inventory(program: Program, ir_program: object) -> dict[str, Any]:
    internal_names = {function.name for function in program.functions}
    foreign_names = {function.name for function in program.foreign_functions}
    operand_histogram = Counter[int]()
    per_callee = Counter[str]()
    per_caller = Counter[str]()
    kinds = Counter[str]()
    total_operands = 0
    total_results = 0
    max_operands = 0
    call_sites: list[dict[str, Any]] = []

    ir_functions = getattr(ir_program, "functions", ())
    for function in ir_functions:
        caller = getattr(function, "name", "<unknown>")
        blocks = getattr(function, "blocks", ())
        for block in blocks:
            for instruction in getattr(block, "instructions", ()):
                if getattr(instruction, "opcode", None) is not IROpcode.CALL:
                    continue
                callee = getattr(instruction, "callee", None)
                callee = callee if isinstance(callee, str) and callee else None
                operands = tuple(getattr(instruction, "operands", ()) or ())
                results = tuple(getattr(instruction, "results", ()) or ())
                operand_count = len(operands)
                result_count = len(results)
                call_kind = _kind(callee, internal_names=internal_names, foreign_names=foreign_names)
                operand_histogram[operand_count] += 1
                total_operands += operand_count
                total_results += result_count
                max_operands = max(max_operands, operand_count)
                kinds[call_kind] += 1
                per_caller[caller] += 1
                per_callee[callee if callee is not None else "<none>"] += 1
                call_sites.append(
                    {
                        "caller": caller,
                        "callee": callee,
                        "kind": call_kind,
                        "operand_count": operand_count,
                        "result_count": result_count,
                        "source_offset": _location_offset(instruction),
                    }
                )

    total = len(call_sites)
    return {
        "total_call_instructions": total,
        "total_operand_uses": total_operands,
        "total_result_definitions": total_results,
        "max_operand_count": max_operands,
        "operand_count_histogram": {
            str(key): operand_histogram[key] for key in sorted(operand_histogram)
        },
        "internal_calls": kinds["internal"],
        "foreign_calls": kinds["foreign"],
        "builtin_or_other_calls": kinds["builtin_or_other"],
        "callee_missing_calls": kinds["dynamic_or_nonidentifier"],
        "per_callee": dict(sorted(per_callee.items())),
        "per_caller": dict(sorted(per_caller.items())),
        "call_sites": call_sites,
    }


def audit_source(source_bytes: bytes, *, contract: dict[str, Any]) -> dict[str, Any]:
    if contract.get("schema") != "s3.selfhost.reference-current-call-inventory-contract.v1":
        raise CurrentCallInventoryError("current call inventory contract schema mismatch")
    try:
        source = source_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise CurrentCallInventoryError("Stage1 source is not UTF-8") from error

    compilation = compile_source(source, optimization="O0")
    ir_program, _ = compilation.require_ordinary_artifacts()
    ast_view = _ast_inventory(compilation.ast)
    ir_view = _ir_inventory(compilation.ast, ir_program)

    ast_total = ast_view["total_call_expressions"]
    ir_total = ir_view["total_call_instructions"]
    ast_arguments = ast_view["total_argument_occurrences"]
    ir_operands = ir_view["total_operand_uses"]
    return {
        "schema": contract["output_schema"],
        "status": "PASS_HOSTED_CURRENT_SOURCE_CALL_INVENTORY",
        "native_evidence": False,
        "source": {
            "sha256": _sha256(source_bytes),
            "bytes": len(source_bytes),
        },
        "optimization": "O0",
        "symbols": {
            "internal_functions": sorted(function.name for function in compilation.ast.functions),
            "foreign_functions": sorted(function.name for function in compilation.ast.foreign_functions),
        },
        "ast": ast_view,
        "o0_ir": ir_view,
        "cross_view": {
            "ast_call_expressions_minus_o0_ir_calls": ast_total - ir_total,
            "ast_argument_occurrences_minus_o0_ir_call_operands": ast_arguments - ir_operands,
            "call_counts_equal": ast_total == ir_total,
            "argument_operand_counts_equal": ast_arguments == ir_operands,
            "equality_required": False,
            "reason": (
                "Typed lowering may turn source calls such as conversions/builtins into non-CALL opcodes, "
                "and IR operands/results are semantic registers rather than physical Stage1 call-pool slots."
            ),
        },
        "historical_closure": {
            "calls_656_arguments_736_authoritative_for_this_source": False,
            "reason": "Historical native/static closure belonged to older source bytes and must not be promoted after source growth.",
        },
        "qualification": {
            "hosted_call_inventory": "PASS",
            "native_stage1_call_high_water_required": True,
            "native_stage1_call_argument_high_water_required": True,
            "physical_capacity_selected_by_this_report": False,
            "stage1_certified_for_stage2": False,
            "stage2_allowed": False,
            "full_self_hosting": False,
            "next": "MEASURE_AND_RECONCILE_NATIVE_STAGE1_CALL_AND_ARGUMENT_HIGH_WATER_ON_THE_SAME_SOURCE_SHA",
        },
    }


def validate_inventory_for_source(report: dict[str, Any], source_bytes: bytes) -> None:
    if report.get("schema") != "s3.selfhost.reference-current-call-inventory.v1":
        raise CurrentCallInventoryError("current call inventory report schema mismatch")
    if report.get("status") != "PASS_HOSTED_CURRENT_SOURCE_CALL_INVENTORY":
        raise CurrentCallInventoryError("current call inventory report is not PASS")
    source = report.get("source")
    if not isinstance(source, dict):
        raise CurrentCallInventoryError("current call inventory report lacks source binding")
    actual_sha = _sha256(source_bytes)
    if source.get("sha256") != actual_sha or source.get("bytes") != len(source_bytes):
        raise CurrentCallInventoryError("current call inventory report is stale for current source bytes")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    try:
        source_bytes = args.source.resolve().read_bytes()
        result = audit_source(
            source_bytes,
            contract=_load_json(args.contract.resolve(), "current call inventory contract"),
        )
    except (OSError, CurrentCallInventoryError, RuntimeError, ValueError) as error:
        parser.exit(2, f"Stage1 current call inventory blocked: {error}\n")

    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"SOURCE_SHA256={result['source']['sha256']}")
    print(f"AST_CALLS={result['ast']['total_call_expressions']}")
    print(f"AST_ARGUMENTS={result['ast']['total_argument_occurrences']}")
    print(f"O0_IR_CALLS={result['o0_ir']['total_call_instructions']}")
    print(f"O0_IR_CALL_OPERANDS={result['o0_ir']['total_operand_uses']}")
    print("HISTORICAL_656_736_AUTHORITY=False")
    print("NATIVE_EVIDENCE=False")
    print(f"NEXT={result['qualification']['next']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
