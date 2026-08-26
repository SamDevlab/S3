"""Measure the semantic information required by the Stage1 general emitter.

This is a host-side audit of the canonical source.  It uses the existing
parser and semantic analyzer only to describe the required IR contract; it is
not a compiler backend and cannot authorize Stage1 self-emission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

from bootstrap.s3 import ast
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" / "semantic-ir-requirements.json"
)


_STATEMENT_NAMES = {
    "VariableDeclaration",
    "AssignmentStatement",
    "CompoundAssignmentStatement",
    "DiscardStatement",
    "ReturnStatement",
    "SwitchStatement",
    "SelectStatement",
    "WhileStatement",
    "BreakStatement",
    "ContinueStatement",
    "ForStatement",
}

_EXPRESSION_NAMES = {
    "IntegerLiteral",
    "FloatLiteral",
    "StringLiteral",
    "Identifier",
    "CallExpression",
    "RecordExpression",
    "GenericTypeExpression",
    "IndexExpression",
    "SliceExpression",
    "FieldAccessExpression",
    "UnaryExpression",
    "BinaryExpression",
    "MatchExpression",
    "LenExpression",
    "AddressOfExpression",
    "DereferenceExpression",
}

_BINARY_OPCODE_GROUPS = {
    "+": "ADD",
    "-": "SUB",
    "*": "MUL",
    "/": "DIV",
    "&": "MINIMUM",
    "|": "MAXIMUM",
    "<=>": "COMPARE",
    "==": "COMPARE_EQUAL",
    "!=": "COMPARE_NOT_EQUAL",
    "<": "COMPARE_LESS",
    "<=": "COMPARE_LESS_EQUAL",
    ">": "COMPARE_GREATER",
    ">=": "COMPARE_GREATER_EQUAL",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _type_key(type_name: object) -> str:
    if isinstance(type_name, ast.TypeName):
        return type_name.value
    if isinstance(type_name, ast.ArrayType):
        return f"array[{type_name.length}]<{_type_key(type_name.element_type)}>"
    if isinstance(type_name, ast.ReferenceType):
        qualifier = "mut" if type_name.mutable else "const"
        return f"ref[{qualifier}]<{_type_key(type_name.target)}>"
    if isinstance(type_name, ast.SliceType):
        qualifier = "mut" if type_name.mutable else "const"
        return f"slice[{qualifier}]<{_type_key(type_name.element_type)}>"
    if isinstance(type_name, ast.NominalType):
        return type_name.name
    if isinstance(type_name, ast.TypeParameterType):
        return f"type_parameter<{type_name.name}>"
    return type(type_name).__name__


def _walk(
    value: object,
    *,
    counters: Counter[str],
    binary_ops: Counter[str],
    call_names: Counter[str],
    call_arities: Counter[str],
    declared_types: Counter[str],
    functions: dict[str, dict[str, int]],
    current_function: str | None = None,
) -> None:
    if isinstance(value, (tuple, list)):
        for child in value:
            _walk(
                child,
                counters=counters,
                binary_ops=binary_ops,
                call_names=call_names,
                call_arities=call_arities,
                declared_types=declared_types,
                functions=functions,
                current_function=current_function,
            )
        return
    if not is_dataclass(value):
        return

    name = type(value).__name__
    counters[name] += 1
    if name in _STATEMENT_NAMES and current_function is not None:
        functions[current_function]["statements"] += 1
    if name in _EXPRESSION_NAMES and current_function is not None:
        functions[current_function]["expressions"] += 1
    if isinstance(value, ast.BinaryExpression):
        binary_ops[value.operator.value] += 1
    elif isinstance(value, ast.CallExpression):
        call_names[value.function_name] += 1
        call_arities[str(len(value.arguments))] += 1
    elif isinstance(value, ast.VariableDeclaration):
        declared_types[_type_key(value.type_name)] += 1
    elif isinstance(value, ast.Parameter):
        declared_types[f"parameter:{_type_key(value.type_name)}"] += 1

    next_function = current_function
    if isinstance(value, ast.FunctionDeclaration):
        next_function = value.name
        functions.setdefault(next_function, {"statements": 0, "expressions": 0})
    for field in fields(value):
        if field.name == "location":
            continue
        _walk(
            getattr(value, field.name),
            counters=counters,
            binary_ops=binary_ops,
            call_names=call_names,
            call_arities=call_arities,
            declared_types=declared_types,
            functions=functions,
            current_function=next_function,
        )


def _reference_typed_ir(source: str) -> dict[str, Any]:
    """Measure the existing host IR as an oracle, never as Stage1 output."""

    from bootstrap.s3.pipeline import compile_source

    compilation = compile_source(source)
    if compilation.ir is None:
        return {"status": "UNAVAILABLE_ASYNC_OR_DYNAMIC"}
    module = compilation.ir
    foreign_names = {function.name for function in compilation.ast.foreign_functions}
    opcodes: Counter[str] = Counter()
    terminators: Counter[str] = Counter()
    call_kinds: Counter[str] = Counter()
    parameters = registers = memory_objects = blocks = instructions = results = 0
    max_registers = max_blocks = max_instructions = 0
    for function in module.functions:
        parameters += len(function.parameters)
        registers += len(function.registers)
        memory_objects += len(function.memory_objects)
        blocks += len(function.blocks)
        function_instructions = sum(
            len(block.instructions) for block in function.blocks
        )
        max_registers = max(max_registers, len(function.registers))
        max_blocks = max(max_blocks, len(function.blocks))
        max_instructions = max(max_instructions, function_instructions)
        for block in function.blocks:
            for instruction in block.instructions:
                instructions += 1
                opcode = instruction.opcode.value
                opcodes[opcode] += 1
                if instruction.is_terminator:
                    terminators[opcode] += 1
                results += len(instruction.results)
                if opcode == "call":
                    kind = (
                        "foreign"
                        if instruction.callee in foreign_names
                        else "internal"
                    )
                    call_kinds[kind] += 1
    return {
        "status": "MEASURED_HOST_IR_ORACLE_NOT_STAGE1_EVIDENCE",
        "functions": len(module.functions),
        "parameters": parameters,
        "registers": registers,
        "memory_objects": memory_objects,
        "blocks": blocks,
        "instructions": instructions,
        "instruction_results": results,
        "opcodes": dict(sorted(opcodes.items())),
        "terminators": dict(sorted(terminators.items())),
        "call_kinds": dict(sorted(call_kinds.items())),
        "max_registers_per_function": max_registers,
        "max_blocks_per_function": max_blocks,
        "max_instructions_per_function": max_instructions,
    }


def _line_number(source: str, offset: int) -> int:
    return source.count("\n", 0, offset) + 1


def _storage_evidence(source: str) -> dict[str, Any]:
    """Describe what the current packed lanes actually preserve.

    The names of the arrays are not semantic evidence by themselves.  This
    small source audit classifies their declarations, writes, and later reads
    so a future IR-v2 change cannot accidentally treat lexical aggregates as
    verified definitions or uses.
    """

    lines = source.splitlines()

    def occurrences(prefix: str) -> dict[str, Any]:
        declaration_lines: list[int] = []
        write_lines: list[int] = []
        read_lines: list[int] = []
        for line_number, line in enumerate(lines, 1):
            if prefix not in line:
                continue
            stripped = line.strip()
            if stripped.startswith(f"mut {prefix}"):
                declaration_lines.append(line_number)
            elif "=" in line:
                write_lines.append(line_number)
            else:
                read_lines.append(line_number)
        return {
            "declaration_lines": declaration_lines,
            "write_lines": write_lines,
            "read_lines": read_lines,
            "declaration_count": len(declaration_lines),
            "write_count": len(write_lines),
            "read_count": len(read_lines),
        }

    event_operand_matches = list(
        re.finditer(r"ir_ast_event_operand\s*=\s*([A-Za-z_][A-Za-z0-9_]*)", source)
    )
    event_offset_matches = list(
        re.finditer(r"ir_ast_event_offset\s*=\s*([^\n]+)", source)
    )
    event_record_matches = list(
        re.finditer(
            r"pack_ir_record\(ir_ast_event_opcode,\s*ir_ast_event_owner,\s*"
            r"ir_ast_event_operand,\s*ir_ast_event_offset\)",
            source,
        )
    )
    instruction_count_matches = list(
        re.finditer(r"ir_instruction_count\s*=\s*ir_ast_event_count", source)
    )

    return {
        "event_records": occurrences("ir_ast_event_records_"),
        "lexical_numeric_records": occurrences("ir_value_records_"),
        "legacy_instruction_records": occurrences("ir_instruction_records_"),
        "parameter_metadata": {
            "status": "PARTIAL",
            "capacity": 68,
            "fields_preserved": [
                "owner_function",
                "name_identity",
                "ordinal",
                "declared_type",
            ],
            "fields_missing": [
                "mutability",
                "semantic_value_id",
            ],
            "source_prefixes": [
                "ir_parameter_owner",
                "ir_parameter_name",
                "ir_parameter_ordinal",
                "ir_parameter_type",
            ],
        },
        "event_record_schema": {
            "pack_expression_count": len(event_record_matches),
            "operand_assignment_sources": sorted(
                {match.group(1) for match in event_operand_matches}
            ),
            "operand_assignment_lines": [
                _line_number(source, match.start()) for match in event_operand_matches
            ],
            "offset_assignment_expressions": [
                match.group(1).strip() for match in event_offset_matches
            ],
            "pack_lines": [
                _line_number(source, match.start()) for match in event_record_matches
            ],
            "schema": "packed(opcode, owner_function_plus_one, token_operand, token_offset)",
        },
        "instruction_cardinality": {
            "derived_from_event_count": bool(instruction_count_matches),
            "assignment_lines": [
                _line_number(source, match.start())
                for match in instruction_count_matches
            ],
        },
        "semantic_relationships": {
            "typed_value_definitions": False,
            "instruction_operand_value_ids": False,
            "instruction_result_value_ids": False,
            "call_argument_value_ids": False,
            "call_result_value_ids": False,
            "complete_terminator_values": False,
            "canonical_serialized_ir": False,
        },
        "interpretation": (
            "event records preserve token-derived aggregates; numeric records "
            "preserve lexical numeric observations; legacy instruction records "
            "are not consumed as semantic instruction definitions"
        ),
    }


def audit(source_path: Path, *, include_reference_ir: bool = False) -> dict[str, Any]:
    source_bytes = source_path.read_bytes()
    source = source_bytes.decode("utf-8")
    program = parse(source)
    semantic = analyze(program)
    foreign_names = {function.name for function in program.foreign_functions}

    counters: Counter[str] = Counter()
    binary_ops: Counter[str] = Counter()
    call_names: Counter[str] = Counter()
    call_arities: Counter[str] = Counter()
    declared_types: Counter[str] = Counter()
    functions: dict[str, dict[str, int]] = {}
    _walk(
        program,
        counters=counters,
        binary_ops=binary_ops,
        call_names=call_names,
        call_arities=call_arities,
        declared_types=declared_types,
        functions=functions,
    )

    call_count = counters["CallExpression"]
    argument_count = counters["CallArgument"]
    local_count = counters["VariableDeclaration"]
    parameter_count = counters["Parameter"]
    required_operations = {
        "CONST_I64": counters["IntegerLiteral"] > 0,
        "PARAM": parameter_count > 0,
        "LOCAL": local_count > 0,
        "LOAD": counters["Identifier"] > 0,
        "STORE": counters["AssignmentStatement"]
        + counters["CompoundAssignmentStatement"]
        > 0,
        "CALL_INTERNAL": any(
            name not in foreign_names for name in call_names
        ),
        "CALL_FOREIGN": any(name in foreign_names for name in call_names),
        "RETURN": counters["ReturnStatement"] > 0,
        "BRANCH": counters["SwitchStatement"] + counters["WhileStatement"] > 0,
        "JUMP": counters["BreakStatement"] + counters["ContinueStatement"] > 0,
        "DISCARD_EFFECT": counters["DiscardStatement"] > 0,
        "INDEX_LOAD_OR_STORE": counters["IndexExpression"]
        + counters["IndexTarget"]
        > 0,
        "ARRAY_INITIALIZER": counters["ArrayLiteral"] > 0,
        "UNARY": counters["UnaryExpression"] > 0,
    }
    for operator, count in binary_ops.items():
        required_operations[_BINARY_OPCODE_GROUPS[operator]] = count > 0

    observed_lanes = {
        "function_metadata": "function_names/function_types/function_flags",
        "parameter_metadata": (
            "PARTIAL:ir_parameter_owner/name/ordinal/type; "
            "missing mutability and semantic value IDs"
        ),
        "aggregate_events": "ir_ast_event_records_*",
        "aggregate_instructions": "ir_instruction_records_*",
        "lexical_numeric_records": "ir_value_records_*",
        "call_metadata": "ir_call_*",
    }
    missing_lanes = [
        "parameter_identity_type_mutability_and_value_id",
        "local_identity_type_mutability_storage_and_value_id",
        "typed_constant_interning_and_definition_ids",
        "instruction_operands_results_and_order",
        "call_result_and_argument_value_ids",
        "branch_conditions_and_complete_terminators",
        "canonical_serialized_ir_artifact",
    ]
    result: dict[str, Any] = {
        "schema": "s3.selfhost.stage1-semantic-ir-requirements.v1",
        "status": "BLOCKED_GENERAL_EMITTER_CAPABILITY_GAP",
        "source": {
            "path": str(source_path),
            "bytes": len(source_bytes),
            "sha256": _sha256(source_bytes),
        },
        "parser_semantic_audit": {
            "functions": len(program.functions),
            "foreign_functions": len(program.foreign_functions),
            "parameters": parameter_count,
            "local_declarations": local_count,
            "calls": call_count,
            "call_arguments": argument_count,
            "max_call_arity": max(
                (int(arity) for arity in call_arities), default=0
            ),
            "returns": counters["ReturnStatement"],
            "assignments": counters["AssignmentStatement"]
            + counters["CompoundAssignmentStatement"],
            "discards": counters["DiscardStatement"],
            "switches": counters["SwitchStatement"],
            "whiles": counters["WhileStatement"],
            "breaks": counters["BreakStatement"],
            "array_literals": counters["ArrayLiteral"],
            "index_expressions": counters["IndexExpression"],
            "index_targets": counters["IndexTarget"],
            "integer_literals": counters["IntegerLiteral"],
            "semantic_expression_types": len(semantic.expression_types),
            "semantic_constant_values": len(semantic.constant_values),
        },
        "ast_node_counts": dict(sorted(counters.items())),
        "binary_operators": dict(sorted(binary_ops.items())),
        "call_arities": {
            arity: call_arities[arity]
            for arity in sorted(call_arities, key=int)
        },
        "call_names": dict(sorted(call_names.items())),
        "foreign_call_names": sorted(name for name in call_names if name in foreign_names),
        "declared_types": dict(sorted(declared_types.items())),
        "function_shape": {
            name: functions[name] for name in sorted(functions)
        },
        "required_operations": dict(sorted(required_operations.items())),
        "current_observed_lanes": observed_lanes,
        "storage_evidence": _storage_evidence(source),
        "missing_lossless_typed_lanes": missing_lanes,
        "stage1_self_emit": "BLOCKED_UNTIL_MISSING_LANES_EXIST_AND_VERIFY",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "reference_typed_ir": (
            _reference_typed_ir(source)
            if include_reference_ir
            else {"status": "NOT_MEASURED_BY_DEFAULT"}
        ),
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--include-reference-ir",
        action="store_true",
        help="measure the existing host IR as an explicit non-Stage1 oracle",
    )
    args = parser.parse_args(argv)
    result = audit(
        args.source.resolve(), include_reference_ir=args.include_reference_ir
    )
    args.report.resolve().parent.mkdir(parents=True, exist_ok=True)
    args.report.resolve().write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={args.report.resolve()}")
    print(f"STATUS={result['status']}")
    print(f"FUNCTIONS={result['parser_semantic_audit']['functions']}")
    print(f"CALLS={result['parser_semantic_audit']['calls']}")
    print(f"LOCALS={result['parser_semantic_audit']['local_declarations']}")
    print(f"MISSING_LANES={len(result['missing_lossless_typed_lanes'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
