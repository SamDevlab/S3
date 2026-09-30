"""Inventory Stage1 source features against explicit compiler capability gates."""

from __future__ import annotations

import argparse
from dataclasses import fields, is_dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
from typing import Iterable

from bootstrap.s3 import ast
from bootstrap.s3.parser import parse


SOURCE_PATH = Path("selfhost/compiler/stage1_compiler_v1.s3")
VECTOR_BUILTINS = {
    "vector_new",
    "vector_len",
    "vector_capacity",
    "vector_reserve",
    "vector_push",
    "vector_pop",
    "vector_get",
    "vector_set",
    "vector_clone",
    "vector_slice",
    "i64_vector_new",
    "i64_vector_len",
    "i64_vector_push",
    "i64_vector_get",
    "i64_vector_set",
    "i64_vector_clone",
}
TEXT_TYPES = {ast.TypeName.STRING, ast.TypeName.BYTES, ast.TypeName.TEXT}
V1_BINARY_OPERATORS = {ast.BinaryOperator.ADD, ast.BinaryOperator.MULTIPLY}


def _type_text(value: object) -> str:
    if isinstance(value, ast.TypeName):
        return value.value
    if isinstance(value, ast.ReferenceType):
        prefix = "&mut " if value.mutable else "&"
        return prefix + _type_text(value.target)
    if isinstance(value, ast.VectorType):
        return f"vector<{_type_text(value.element_type)}>"
    if isinstance(value, ast.ArrayType):
        return f"[{_type_text(value.element_type)}; {value.length}]"
    if isinstance(value, ast.SliceType):
        prefix = "&mut " if value.mutable else "&"
        return f"{prefix}[{_type_text(value.element_type)}]"
    if isinstance(value, ast.NominalType):
        if not value.type_arguments:
            return value.name
        arguments = ", ".join(_type_text(item) for item in value.type_arguments)
        return f"{value.name}<{arguments}>"
    if isinstance(value, ast.TypeParameterType):
        return value.name
    return type(value).__name__


def _walk(value: object) -> Iterable[object]:
    if isinstance(value, (tuple, list)):
        for item in value:
            yield from _walk(item)
    elif isinstance(value, Enum):
        yield value
    elif is_dataclass(value):
        yield value
        for field in fields(value):
            if field.name != "location":
                yield from _walk(getattr(value, field.name))


def _nested_call_present(value: object, inside_call: bool = False) -> bool:
    if isinstance(value, ast.CallExpression):
        if inside_call:
            return True
        return any(
            _nested_call_present(getattr(value, field.name), True)
            for field in fields(value)
            if field.name != "location"
        )
    if isinstance(value, (tuple, list)):
        return any(_nested_call_present(item, inside_call) for item in value)
    if is_dataclass(value):
        return any(
            _nested_call_present(getattr(value, field.name), inside_call)
            for field in fields(value)
            if field.name != "location"
        )
    return False


def _type_nodes(value: object) -> list[object]:
    return [
        item
        for item in _walk(value)
        if isinstance(
            item,
            (
                ast.TypeName,
                ast.ReferenceType,
                ast.VectorType,
                ast.ArrayType,
                ast.SliceType,
                ast.NominalType,
                ast.TypeParameterType,
            ),
        )
    ]


def _type_families(types: list[object]) -> set[str]:
    families: set[str] = set()
    for item in types:
        if isinstance(item, ast.ReferenceType):
            families.add("reference")
        elif isinstance(item, ast.VectorType):
            families.add("vector")
        elif isinstance(item, (ast.ArrayType, ast.SliceType)):
            families.add("indexed")
        elif isinstance(item, ast.NominalType):
            if item.name == "vector":
                families.add("vector")
            else:
                families.add("aggregate")
        elif isinstance(item, ast.TypeName):
            if item in {ast.TypeName.TRIT, ast.TypeName.TRYTE}:
                families.add("ternary")
            elif item is ast.TypeName.F64:
                families.add("f64")
            elif item in TEXT_TYPES:
                families.add("text")
            elif item in {ast.TypeName.I64_VECTOR, ast.TypeName.F64_VECTOR, ast.TypeName.TRYTE_VECTOR}:
                families.add("vector")
            elif item is not ast.TypeName.I64:
                families.add("other")
    return families


def _expression_blockers(
    expression: object,
    available_names: set[str],
    function_names: set[str],
    *,
    allow_i64_vector_get: bool = False,
    reference_parameters: set[str] | None = None,
) -> set[str]:
    reference_parameters = reference_parameters or set()
    if isinstance(expression, ast.IntegerLiteral):
        return set()
    if isinstance(expression, ast.Identifier):
        return set() if expression.name in available_names else {"unbound_identifier"}
    if isinstance(expression, ast.BinaryExpression):
        blockers = _expression_blockers(
            expression.left,
            available_names,
            function_names,
            allow_i64_vector_get=allow_i64_vector_get,
            reference_parameters=reference_parameters,
        )
        blockers.update(
            _expression_blockers(
                expression.right,
                available_names,
                function_names,
                allow_i64_vector_get=allow_i64_vector_get,
                reference_parameters=reference_parameters,
            )
        )
        if expression.operator not in V1_BINARY_OPERATORS:
            blockers.add("unsupported_binary_operator")
        return blockers
    if isinstance(expression, ast.CallExpression):
        blockers: set[str] = set()
        if not isinstance(expression.callee, ast.Identifier):
            blockers.add("unsupported_indirect_call")
        else:
            callee = expression.callee.name
            is_vector_get = (
                callee == "vector_get"
                and tuple(expression.type_arguments) == (ast.TypeName.I64,)
                and len(expression.arguments) == 2
                and isinstance(expression.arguments[0].expression, ast.Identifier)
                and expression.arguments[0].expression.name in reference_parameters
            )
            if is_vector_get and allow_i64_vector_get:
                pass
            elif callee in function_names:
                if expression.type_arguments:
                    blockers.add("unsupported_generic_local_call")
            else:
                blockers.add(
                    "vector_operation" if callee in VECTOR_BUILTINS else "unsupported_builtin_call"
                )
        for argument in expression.arguments:
            blockers.update(
                _expression_blockers(
                    argument.expression,
                    available_names,
                    function_names,
                    allow_i64_vector_get=allow_i64_vector_get,
                    reference_parameters=reference_parameters,
                )
            )
        return blockers
    return {f"unsupported_expression_{type(expression).__name__}"}


def _body_blockers(
    function: ast.FunctionDeclaration,
    function_names: set[str],
    *,
    allow_i64_vector_get: bool = False,
) -> set[str]:
    available_names = {parameter.name for parameter in function.parameters}
    reference_parameters = {
        parameter.name
        for parameter in function.parameters
        if isinstance(parameter.type_name, ast.ReferenceType)
        and isinstance(parameter.type_name.target, ast.NominalType)
        and parameter.type_name.target.name == "vector"
        and parameter.type_name.target.type_arguments == (ast.TypeName.I64,)
    }
    blockers: set[str] = set()
    returned = False
    for index, statement in enumerate(function.body.statements):
        if isinstance(statement, ast.VariableDeclaration):
            if returned:
                blockers.add("statement_after_return")
            if statement.mutable:
                blockers.add("mutable_storage")
            if statement.type_name is not ast.TypeName.I64:
                blockers.add("unsupported_local_type")
            if statement.name in available_names:
                blockers.add("duplicate_local")
            blockers.update(
                _expression_blockers(
                    statement.initializer,
                    available_names,
                    function_names,
                    allow_i64_vector_get=allow_i64_vector_get,
                    reference_parameters=reference_parameters,
                )
            )
            available_names.add(statement.name)
        elif isinstance(statement, ast.ReturnStatement):
            if returned or index != len(function.body.statements) - 1:
                blockers.add("return_not_terminal")
            blockers.update(
                _expression_blockers(
                    statement.expression,
                    available_names,
                    function_names,
                    allow_i64_vector_get=allow_i64_vector_get,
                    reference_parameters=reference_parameters,
                )
            )
            returned = True
        else:
            blockers.add(f"unsupported_statement_{type(statement).__name__}")
    if not returned:
        blockers.add("missing_return")
    if len(function.parameters) > 64:
        blockers.add("parameter_capacity")
    if len(function.body.statements) > 64:
        blockers.add("statement_capacity")
    return blockers


def _function_entry(
    function: ast.FunctionDeclaration,
    end_offset: int,
    function_names: set[str],
) -> dict[str, object]:
    params = [
        {"name": parameter.name, "type": _type_text(parameter.type_name)}
        for parameter in function.parameters
    ]
    signature_types = _type_nodes(
        tuple(parameter.type_name for parameter in function.parameters)
        + (function.return_type,)
    )
    signature_families = _type_families(signature_types)
    supported_signature = all(
        parameter.type_name is ast.TypeName.I64 for parameter in function.parameters
    ) and function.return_type is ast.TypeName.I64

    body_nodes = list(_walk(function.body))
    call_nodes = [node for node in body_nodes if isinstance(node, ast.CallExpression)]
    calls = sorted(
        {
        node.callee.name
        for node in call_nodes
        if isinstance(node.callee, ast.Identifier)
        }
    )
    body_type_nodes = _type_nodes(function.body)
    body_families = _type_families(body_type_nodes)
    body_names = {type(node).__name__ for node in body_nodes}
    vector_calls = sorted(set(calls) & VECTOR_BUILTINS)
    local_calls = sorted(
        call
        for call in calls
        if call in function_names
    )

    signature_text = (
        "(" + ", ".join(item["type"] for item in params) + ") -> "
        + _type_text(function.return_type)
    )
    body_blockers = _body_blockers(function, function_names)
    primary_blocker = None
    if not supported_signature:
        if "reference" in signature_families:
            primary_blocker = "unsupported_reference_signature"
        elif "vector" in signature_families:
            primary_blocker = "unsupported_vector_signature"
        elif "aggregate" in signature_families:
            primary_blocker = "unsupported_aggregate_signature"
        elif "f64" in signature_families:
            primary_blocker = "unsupported_f64_signature"
        elif "ternary" in signature_families:
            primary_blocker = "unsupported_ternary_signature"
        else:
            primary_blocker = "unsupported_signature_type"
    elif body_blockers:
        primary_blocker = sorted(body_blockers)[0]

    secondary = set()
    if "AddressOfExpression" in body_names or "DereferenceExpression" in body_names:
        secondary.add("reference_operation")
    if vector_calls or "vector" in body_families:
        secondary.add("vector_operation")
    if "RecordExpression" in body_names or "FieldAccessExpression" in body_names:
        secondary.add("aggregate_operation")
    if "SwitchStatement" in body_names or "MatchExpression" in body_names:
        secondary.add("structured_branching")
    if "WhileStatement" in body_names or "ForStatement" in body_names:
        secondary.add("loop_control_flow")
    if "AssignmentStatement" in body_names or "CompoundAssignmentStatement" in body_names:
        secondary.add("mutable_storage")
    if "IndexExpression" in body_names or "SliceExpression" in body_names:
        secondary.add("indexing_or_slicing")
    if any(isinstance(node, ast.TypeName) and node in TEXT_TYPES for node in body_type_nodes):
        secondary.add("text_value")
    if _nested_call_present(function.body):
        secondary.add("nested_calls")
    secondary.update(body_blockers - ({primary_blocker} if primary_blocker else set()))
    unsupported_ops = sorted(
        body_names
        & {
            "BinaryExpression",
            "UnaryExpression",
            "AddressOfExpression",
            "DereferenceExpression",
            "FieldAccessExpression",
            "RecordExpression",
            "IndexExpression",
            "SliceExpression",
            "WhileStatement",
            "ForStatement",
            "SwitchStatement",
            "AssignmentStatement",
            "CompoundAssignmentStatement",
        }
    )

    return {
        "name": function.name,
        "source_start": function.location.offset,
        "source_end": end_offset,
        "source_bytes": end_offset - function.location.offset,
        "signature": signature_text,
        "parameters": params,
        "return_type": _type_text(function.return_type),
        "uses_references": "reference" in signature_families or bool(
            body_names & {"AddressOfExpression", "DereferenceExpression"}
        ),
        "uses_vectors": "vector" in signature_families or "vector" in body_families or bool(vector_calls),
        "uses_aggregates": "aggregate" in signature_families or bool(
            body_names & {"RecordExpression", "FieldAccessExpression"}
        ),
        "uses_strings": any(isinstance(node, ast.TypeName) and node in TEXT_TYPES for node in signature_types + body_type_nodes)
        or "StringLiteral" in body_names,
        "uses_indexing": bool(body_names & {"IndexExpression", "SliceExpression"}),
        "uses_dynamic_memory": any(
            name.endswith(("_new", "_push", "_reserve", "_clone", "_slice"))
            for name in calls
        ),
        "uses_nested_calls": _nested_call_present(function.body),
        "uses_unsupported_control_flow": bool(
            body_names & {"SwitchStatement", "MatchExpression", "WhileStatement", "ForStatement"}
        ),
        "unsupported_operations": unsupported_ops,
        "calls": calls,
        "local_calls": local_calls,
        "signature_supported_by_v1": supported_signature,
        "body_supported_by_v1": not body_blockers,
        "representable": supported_signature and not body_blockers,
        "primary_blocker": primary_blocker,
        "secondary_blockers": sorted(secondary),
        "dependency_closed": None,
        "self_compile_attempted": False,
        "self_compile_result": "NOT_ATTEMPTED",
    }


def analyze_stage1(source: str) -> dict[str, object]:
    program = parse(source)
    functions = list(program.functions)
    function_names = {function.name for function in functions}
    starts = [function.location.offset for function in functions]
    entries = [
        _function_entry(
            function,
            starts[index + 1] if index + 1 < len(starts) else len(source.encode("utf-8")),
            function_names,
        )
        for index, function in enumerate(functions)
    ]
    by_name = {str(entry["name"]): entry for entry in entries}

    def dependency_closed(name: str, active: set[str]) -> bool:
        entry = by_name[name]
        if not entry["representable"]:
            return False
        if name in active:
            return True
        next_active = active | {name}
        return all(
            callee in by_name and dependency_closed(callee, next_active)
            for callee in entry["local_calls"]
        )

    function_by_name = {function.name: function for function in functions}
    for entry in entries:
        entry["self_contained_representable"] = bool(entry["representable"]) and not entry["local_calls"]
        entry["dependency_closed"] = dependency_closed(str(entry["name"]), set())
        function = function_by_name[str(entry["name"])]
        future_body = _body_blockers(
            function,
            function_names,
            allow_i64_vector_get=True,
        )
        signature_types = _type_nodes(
            tuple(
                parameter.type_name for parameter in function.parameters
            )
            + (function.return_type,)
        )
        families = _type_families(signature_types)
        entry["representable_with_reference_vector_get_subset"] = (
            not future_body
            and families <= {"reference", "vector"}
        )

    distribution: dict[str, int] = {}
    for entry in entries:
        blocker = entry["primary_blocker"]
        if blocker:
            distribution[blocker] = distribution.get(blocker, 0) + 1
        for blocker in entry["secondary_blockers"]:
            distribution[blocker] = distribution.get(blocker, 0) + 1

    ref_vector_subset = sum(
        entry["representable_with_reference_vector_get_subset"] is True
        for entry in entries
    )
    reference_functions = sum("reference" in _type_families(_type_nodes(
        tuple(parameter.type_name for parameter in function.parameters) + (function.return_type,)
    )) for function in functions)
    vector_functions = sum("vector" in _type_families(_type_nodes(
        tuple(parameter.type_name for parameter in function.parameters) + (function.return_type,)
    )) for function in functions)
    primary_distribution: dict[str, int] = {}
    for entry in entries:
        blocker = entry["primary_blocker"]
        if blocker:
            primary_distribution[blocker] = primary_distribution.get(blocker, 0) + 1
    ref_vector_candidates = [
        str(entry["name"])
        for entry in entries
        if entry["representable_with_reference_vector_get_subset"] is True
    ]
    encoded = source.encode("utf-8")
    return {
        "schema": "s3-stage1-representability-matrix",
        "schema_version": "1.0.0",
        "source_path": str(SOURCE_PATH).replace("\\", "/"),
        "source_sha256": hashlib.sha256(encoded).hexdigest(),
        "source_bytes": len(encoded),
        "functions_total": len(entries),
        "functions_representable": sum(entry["representable"] is True for entry in entries),
        "function_attributed_source_bytes": sum(int(entry["source_bytes"]) for entry in entries),
        "v1_gate": {
            "supported_parameter_type": "i64",
            "supported_return_type": "i64",
            "body_subset": "final return; immutable i64 locals; integer literals; bound identifiers; local calls; i64 addition and multiplication",
        },
        "blocker_distribution_overlapping": dict(sorted(distribution.items())),
        "primary_blocker_distribution": dict(sorted(primary_distribution.items())),
        "capability_projection": {
            "functions_using_reference_signature_types": reference_functions,
            "functions_using_vector_signature_types": vector_functions,
            "functions_unlocked_by_typed_ir_only": 0,
            "functions_unlocked_by_references_only": 0,
            "functions_unlocked_by_vectors_only": 0,
            "functions_unlocked_by_references_plus_vectors_and_i64_vector_get": ref_vector_subset,
            "reference_vector_get_candidate_functions": ref_vector_candidates,
            "projection_scope": "signature and body subset only; excludes dependency closure and runtime/backend gates",
        },
        "functions": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE_PATH)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.read_text(encoding="utf-8")
    matrix = analyze_stage1(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(matrix, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
    )
    print(
        f"STAGE1_FUNCTIONS={matrix['functions_total']} "
        f"REPRESENTABLE={matrix['functions_representable']} "
        f"SHA256={matrix['source_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
