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
STAGE1_V1_SHA256 = "894a76a5c206b8e86b3149483b4bc2ad6904a4f6810aac62d1e235c1fd46a44c"
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
V2_BINARY_OPERATORS = {
    ast.BinaryOperator.ADD,
    ast.BinaryOperator.SUBTRACT,
    ast.BinaryOperator.MULTIPLY,
    ast.BinaryOperator.EQUAL,
    ast.BinaryOperator.LESS,
    ast.BinaryOperator.LESS_EQUAL,
    ast.BinaryOperator.GREATER,
    ast.BinaryOperator.GREATER_EQUAL,
    ast.BinaryOperator.COMPARE,
}
V2_COMPARISON_OPERATORS = {
    ast.BinaryOperator.EQUAL,
    ast.BinaryOperator.LESS,
    ast.BinaryOperator.LESS_EQUAL,
    ast.BinaryOperator.GREATER,
    ast.BinaryOperator.GREATER_EQUAL,
    ast.BinaryOperator.COMPARE,
}
V2_SUPPORTED_EXTERNALS = {
    "vector_new",
    "vector_get",
    "vector_len",
    "vector_push",
    "i64_vector_get",
    "i64_vector_len",
}
V2_MAX_SOURCE_BYTES = 4096
V2_MAX_TOKEN_COUNT = 1024
V2_PROVEN_SELF_COMPILED_FUNCTIONS = {
    "stage1_source_spans_equal",
    "stage1_find_symbol_value",
    "stage1_parameter_name_seen",
    "stage1_parameter_names_unique",
    "stage1_emission_value_count",
    "stage1_emission_instruction_count",
    "stage1_emission_value_id",
    "stage1_emission_operand_id",
    "stage1_emission_instruction_field",
    "stage1_emit_decimal",
    "stage1_emit_register",
    "stage1_source_name_is_main",
    "stage1_find_function_id_by_source_name",
    "stage1_emit_ir_function_name",
    "stage1_emit_ir_callee_name",
    "stage1_output_chunk",
}
V2_SELFHOSTED_COMPILER_BEHAVIOR = {
    "stage1_find_symbol_value": "symbol_resolution",
    "stage1_parameter_names_unique": "parameter_validation",
    "stage1_output_chunk": "assembly_emission",
    "stage1_emit_decimal": "assembly_emission",
    "stage1_emit_register": "assembly_emission",
    "stage1_source_name_is_main": "entry_point_classification",
    "stage1_find_function_id_by_source_name": "symbol_resolution",
    "stage1_emit_ir_function_name": "assembly_emission",
    "stage1_emit_ir_callee_name": "assembly_emission",
}


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


def _v2_type_supported(value: object, *, signature: bool) -> bool:
    if value is ast.TypeName.I64 or value is ast.TypeName.TRIT:
        return True
    return bool(signature and _v2_is_i64_vector_reference(value))


def _v2_is_i64_vector(value: object) -> bool:
    return bool(
        isinstance(value, ast.NominalType)
        and value.name == "vector"
        and value.type_arguments == (ast.TypeName.I64,)
    )


def _v2_is_i64_vector_reference(value: object) -> bool:
    return bool(
        isinstance(value, ast.ReferenceType)
        and _v2_is_i64_vector(value.target)
    )


def _v2_local_type_supported(value: object) -> bool:
    return value is ast.TypeName.I64 or _v2_is_i64_vector(value)


def _v2_return_type_supported(value: object) -> bool:
    return (
        value is ast.TypeName.I64
        or value is ast.TypeName.TRIT
        or _v2_is_i64_vector(value)
    )


def _v2_same_type(left: object | None, right: object) -> bool:
    return left is not None and _type_text(left) == _type_text(right)


def _v2_expression_type(
    expression: object,
    environment: dict[str, object],
    functions: dict[str, ast.FunctionDeclaration],
    *,
    unsupported_operations: set[str],
    unsupported_types: set[str],
    unsupported_callees: set[str],
    mutable_names: set[str] | None = None,
) -> object | None:
    if isinstance(expression, ast.IntegerLiteral):
        return ast.TypeName.I64
    if isinstance(expression, ast.UnaryExpression):
        if (
            expression.operator is ast.UnaryOperator.NEGATE
            and isinstance(expression.operand, ast.IntegerLiteral)
        ):
            return ast.TypeName.I64
        unsupported_operations.add(f"unary_{expression.operator.value}")
        return None
    if isinstance(expression, ast.AddressOfExpression):
        if not isinstance(expression.operand, ast.Identifier):
            unsupported_operations.add("address_of_requires_local_identifier")
            return None
        name = expression.operand.name
        target = environment.get(name)
        if target is None or not _v2_is_i64_vector(target):
            unsupported_operations.add("address_of_requires_i64_vector_local")
            return None
        if expression.mutable and (mutable_names is None or name not in mutable_names):
            unsupported_operations.add("mutable_reference_requires_mutable_binding")
            return None
        return ast.ReferenceType(
            target=target,
            mutable=expression.mutable,
            location=expression.location,
        )
    if isinstance(expression, ast.Identifier):
        if expression.name not in environment:
            unsupported_operations.add(f"unbound_identifier:{expression.name}")
            return None
        return environment[expression.name]
    if isinstance(expression, ast.BinaryExpression):
        left = _v2_expression_type(
            expression.left, environment, functions,
            unsupported_operations=unsupported_operations,
            unsupported_types=unsupported_types,
            unsupported_callees=unsupported_callees,
            mutable_names=mutable_names,
        )
        right = _v2_expression_type(
            expression.right, environment, functions,
            unsupported_operations=unsupported_operations,
            unsupported_types=unsupported_types,
            unsupported_callees=unsupported_callees,
            mutable_names=mutable_names,
        )
        if expression.operator not in V2_BINARY_OPERATORS:
            unsupported_operations.add(f"binary_{expression.operator.value}")
        if expression.operator is ast.BinaryOperator.COMPARE:
            if left is not right or left not in {ast.TypeName.I64, ast.TypeName.TRIT}:
                unsupported_operations.add("binary_operand_type_mismatch")
                return None
            return ast.TypeName.TRIT
        if left is not ast.TypeName.I64 or right is not ast.TypeName.I64:
            unsupported_operations.add("binary_operand_type_mismatch")
            return None
        if expression.operator in V2_COMPARISON_OPERATORS:
            return ast.TypeName.TRIT
        return ast.TypeName.I64
    if isinstance(expression, ast.CallExpression):
        if not isinstance(expression.callee, ast.Identifier):
            unsupported_callees.add("<indirect-call>")
            return None
        callee = expression.callee.name
        argument_types = [
            _v2_expression_type(
                argument.expression, environment, functions,
                unsupported_operations=unsupported_operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                mutable_names=mutable_names,
            )
            for argument in expression.arguments
        ]
        if callee in functions:
            target = functions[callee]
            if expression.type_arguments or target.signature.type_parameters:
                unsupported_callees.add(f"{callee}:generic-call")
                return target.return_type
            expected = [parameter.type_name for parameter in target.parameters]
            if len(argument_types) != len(expected) or [
                _type_text(item) if item is not None else None for item in argument_types
            ] != [_type_text(item) for item in expected]:
                unsupported_callees.add(f"{callee}:signature-mismatch")
            if not _v2_return_type_supported(target.return_type):
                unsupported_callees.add(f"{callee}:unsupported-return")
                return None
            return target.return_type
        if callee not in V2_SUPPORTED_EXTERNALS:
            unsupported_callees.add(callee)
            return None
        if callee in {"i64_vector_get", "i64_vector_len"}:
            if expression.type_arguments:
                unsupported_types.add(f"{callee}:does-not-take-type-arguments")
            if callee == "i64_vector_len":
                valid = (
                    len(argument_types) == 1
                    and isinstance(argument_types[0], ast.ReferenceType)
                    and not argument_types[0].mutable
                    and _v2_is_i64_vector_reference(argument_types[0])
                )
            else:
                valid = (
                    len(argument_types) == 2
                    and isinstance(argument_types[0], ast.ReferenceType)
                    and not argument_types[0].mutable
                    and _v2_is_i64_vector_reference(argument_types[0])
                    and argument_types[1] is ast.TypeName.I64
                )
            if not valid:
                unsupported_operations.add(f"{callee}:argument-shape")
            return ast.TypeName.I64
        if tuple(expression.type_arguments) != (ast.TypeName.I64,):
            unsupported_types.add(f"{callee}:requires-i64-type-argument")
        if callee == "vector_new":
            valid = len(argument_types) == 1 and argument_types[0] is ast.TypeName.I64
            if not valid:
                unsupported_operations.add("vector_new:argument-shape")
            return ast.NominalType(
                name="vector",
                location=expression.location,
                type_arguments=(ast.TypeName.I64,),
            )
        if callee == "vector_len":
            valid = (
                len(argument_types) == 1
                and isinstance(argument_types[0], ast.ReferenceType)
                and not argument_types[0].mutable
                and _v2_is_i64_vector_reference(argument_types[0])
            )
        elif callee == "vector_get":
            valid = (
                len(argument_types) == 2
                and isinstance(argument_types[0], ast.ReferenceType)
                and not argument_types[0].mutable
                and _v2_is_i64_vector_reference(argument_types[0])
                and argument_types[1] is ast.TypeName.I64
            )
        else:
            valid = (
                len(argument_types) == 2
                and isinstance(argument_types[0], ast.ReferenceType)
                and argument_types[0].mutable
                and _v2_is_i64_vector_reference(argument_types[0])
                and argument_types[1] is ast.TypeName.I64
            )
        if not valid:
            unsupported_operations.add(f"{callee}:argument-shape")
        return ast.TypeName.I64
    unsupported_operations.add(f"expression_{type(expression).__name__}")
    return None


def _v2_return_expression_type(
    expression: object,
    expected_type: object,
    environment: dict[str, object],
    functions: dict[str, ast.FunctionDeclaration],
    *,
    unsupported_operations: set[str],
    unsupported_types: set[str],
    unsupported_callees: set[str],
    mutable_names: set[str] | None = None,
) -> object | None:
    literal_value: int | None = None
    if isinstance(expression, ast.IntegerLiteral):
        literal_value = expression.value
    elif (
        isinstance(expression, ast.UnaryExpression)
        and expression.operator is ast.UnaryOperator.NEGATE
        and isinstance(expression.operand, ast.IntegerLiteral)
    ):
        literal_value = -expression.operand.value
    if expected_type is ast.TypeName.TRIT and literal_value in {-1, 0, 1}:
        return ast.TypeName.TRIT
    return _v2_expression_type(
        expression,
        environment,
        functions,
        unsupported_operations=unsupported_operations,
        unsupported_types=unsupported_types,
        unsupported_callees=unsupported_callees,
        mutable_names=mutable_names,
    )


def _v2_control_block_capabilities(
    block: ast.Block,
    function: ast.FunctionDeclaration,
    functions: dict[str, ast.FunctionDeclaration],
    environment: dict[str, object],
    mutable_names: set[str],
    *,
    syntax: set[str],
    operations: set[str],
    unsupported_types: set[str],
    unsupported_callees: set[str],
    supported_statement_ids: set[int],
    context: str,
) -> bool:
    if len(block.statements) > 64:
        operations.add(f"{context}_statement_capacity")
    local_environment = dict(environment)
    local_mutable_names = set(mutable_names)
    returned = False
    for index, statement in enumerate(block.statements):
        supported_statement_ids.add(id(statement))
        if returned:
            syntax.add(f"statement_after_return_in_{context}")
        if isinstance(statement, ast.VariableDeclaration):
            if statement.name in local_environment:
                operations.add("duplicate_local")
            if not (
                _v2_local_type_supported(statement.type_name)
                or statement.type_name is ast.TypeName.TRIT
            ):
                unsupported_types.add(_type_text(statement.type_name))
            inferred = _v2_expression_type(
                statement.initializer,
                local_environment,
                functions,
                unsupported_operations=operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                mutable_names=local_mutable_names,
            )
            if not _v2_same_type(inferred, statement.type_name):
                operations.add("local_initializer_type_mismatch")
            local_environment[statement.name] = statement.type_name
            if statement.mutable:
                local_mutable_names.add(statement.name)
        elif isinstance(statement, ast.AssignmentStatement):
            if not isinstance(statement.target, ast.VariableTarget):
                operations.add(
                    f"unsupported_assignment_target_{type(statement.target).__name__}"
                )
                continue
            target_name = statement.target.name
            if target_name not in local_environment:
                operations.add(f"assignment_to_unknown_binding:{target_name}")
                continue
            if target_name not in local_mutable_names:
                operations.add(f"assignment_to_immutable_binding:{target_name}")
                continue
            inferred = _v2_expression_type(
                statement.value,
                local_environment,
                functions,
                unsupported_operations=operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                mutable_names=local_mutable_names,
            )
            if not _v2_same_type(inferred, local_environment[target_name]):
                operations.add("assignment_value_type_mismatch")
        elif isinstance(statement, ast.DiscardStatement):
            _v2_expression_type(
                statement.expression,
                local_environment,
                functions,
                unsupported_operations=operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                mutable_names=local_mutable_names,
            )
        elif isinstance(statement, ast.ReturnStatement):
            if index != len(block.statements) - 1:
                syntax.add(f"nonterminal_return_in_{context}")
            inferred = _v2_return_expression_type(
                statement.expression,
                function.return_type,
                local_environment,
                functions,
                unsupported_operations=operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                mutable_names=local_mutable_names,
            )
            if not _v2_same_type(inferred, function.return_type):
                operations.add("return_type_mismatch")
            returned = True
        elif isinstance(statement, ast.SwitchStatement):
            condition_type = _v2_expression_type(
                statement.expression,
                local_environment,
                functions,
                unsupported_operations=operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                mutable_names=local_mutable_names,
            )
            if condition_type is not ast.TypeName.TRIT:
                operations.add("match_condition_type_mismatch")
            if tuple(case.label for case in statement.cases) != (-1, 0, 1):
                operations.add("match_requires_ordered_ternary_cases")
            all_cases_return = tuple(
                case.label for case in statement.cases
            ) == (-1, 0, 1)
            for case in statement.cases:
                case_returns = _v2_control_block_capabilities(
                    case.body,
                    function,
                    functions,
                    local_environment,
                    local_mutable_names,
                    syntax=syntax,
                    operations=operations,
                    unsupported_types=unsupported_types,
                    unsupported_callees=unsupported_callees,
                    supported_statement_ids=supported_statement_ids,
                    context="match_arm",
                )
                all_cases_return = all_cases_return and case_returns
            if all_cases_return:
                returned = True
        elif isinstance(statement, ast.WhileStatement):
            condition_type = _v2_expression_type(
                statement.condition,
                local_environment,
                functions,
                unsupported_operations=operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                mutable_names=local_mutable_names,
            )
            if condition_type is not ast.TypeName.TRIT:
                operations.add("while_condition_type_mismatch")
            _v2_control_block_capabilities(
                statement.body,
                function,
                functions,
                local_environment,
                local_mutable_names,
                syntax=syntax,
                operations=operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                supported_statement_ids=supported_statement_ids,
                context="while",
            )
        else:
            syntax.add(f"{context}_{type(statement).__name__}")
    return returned


def _v2_body_capabilities(
    function: ast.FunctionDeclaration,
    functions: dict[str, ast.FunctionDeclaration],
) -> tuple[set[str], set[str], set[str], set[str], list[str]]:
    syntax: set[str] = set()
    operations: set[str] = set()
    unsupported_types: set[str] = set()
    unsupported_callees: set[str] = set()
    local_calls: set[str] = set()
    mutable_names: set[str] = set()
    environment: dict[str, object] = {
        parameter.name: parameter.type_name for parameter in function.parameters
    }
    statements = function.body.statements
    returned = False
    supported_loop_statement_ids: set[int] = set()
    for index, statement in enumerate(statements):
        if returned:
            syntax.add("statement_after_return")
        if isinstance(statement, ast.VariableDeclaration):
            if statement.name in environment:
                operations.add("duplicate_local")
            if not _v2_local_type_supported(statement.type_name):
                unsupported_types.add(_type_text(statement.type_name))
            inferred = _v2_expression_type(
                statement.initializer, environment, functions,
                unsupported_operations=operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                mutable_names=mutable_names,
            )
            if not _v2_same_type(inferred, statement.type_name):
                operations.add("local_initializer_type_mismatch")
            environment[statement.name] = statement.type_name
            if statement.mutable:
                mutable_names.add(statement.name)
        elif isinstance(statement, ast.ReturnStatement):
            if index != len(statements) - 1:
                syntax.add("nonterminal_return")
            inferred = _v2_return_expression_type(
                statement.expression,
                function.return_type,
                environment,
                functions,
                unsupported_operations=operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                mutable_names=mutable_names,
            )
            if not _v2_same_type(inferred, function.return_type):
                operations.add("return_type_mismatch")
            returned = True
        elif isinstance(statement, ast.DiscardStatement):
            _v2_expression_type(
                statement.expression, environment, functions,
                unsupported_operations=operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                mutable_names=mutable_names,
            )
        elif isinstance(statement, ast.AssignmentStatement):
            if not isinstance(statement.target, ast.VariableTarget):
                operations.add(f"unsupported_assignment_target_{type(statement.target).__name__}")
                continue
            target_name = statement.target.name
            if target_name not in environment:
                operations.add(f"assignment_to_unknown_binding:{target_name}")
                continue
            if target_name not in mutable_names:
                operations.add(f"assignment_to_immutable_binding:{target_name}")
                continue
            if not isinstance(statement.value, (ast.IntegerLiteral, ast.Identifier, ast.BinaryExpression, ast.CallExpression)):
                operations.add(f"unsupported_assignment_value_{type(statement.value).__name__}")
                continue
            inferred = _v2_expression_type(
                statement.value, environment, functions,
                unsupported_operations=operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                mutable_names=mutable_names,
            )
            if not _v2_same_type(inferred, environment[target_name]):
                operations.add("assignment_value_type_mismatch")
        elif isinstance(statement, ast.CompoundAssignmentStatement):
            operations.add("compound_assignment")
        elif isinstance(statement, ast.SwitchStatement):
            switch_returns = _v2_control_block_capabilities(
                ast.Block((statement,), statement.location),
                function,
                functions,
                environment,
                mutable_names,
                syntax=syntax,
                operations=operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                supported_statement_ids=supported_loop_statement_ids,
                context="function_control",
            )
            if switch_returns:
                returned = True
        elif isinstance(statement, ast.WhileStatement):
            condition_type = _v2_expression_type(
                statement.condition, environment, functions,
                unsupported_operations=operations,
                unsupported_types=unsupported_types,
                unsupported_callees=unsupported_callees,
                mutable_names=mutable_names,
            )
            if condition_type is not ast.TypeName.TRIT:
                operations.add("while_condition_type_mismatch")
            loop_environment = dict(environment)
            loop_mutable_names = set(mutable_names)
            loop_returned = False
            if len(statement.body.statements) > 64:
                operations.add("while_statement_capacity")
            for body_index, body_statement in enumerate(statement.body.statements):
                if loop_returned:
                    syntax.add("statement_after_return_in_while")
                if isinstance(body_statement, ast.VariableDeclaration):
                    supported_loop_statement_ids.add(id(body_statement))
                    if body_statement.name in loop_environment:
                        operations.add("duplicate_local_in_while")
                    if not (
                        _v2_local_type_supported(body_statement.type_name)
                        or body_statement.type_name is ast.TypeName.TRIT
                    ):
                        unsupported_types.add(_type_text(body_statement.type_name))
                    inferred = _v2_expression_type(
                        body_statement.initializer, loop_environment, functions,
                        unsupported_operations=operations,
                        unsupported_types=unsupported_types,
                        unsupported_callees=unsupported_callees,
                        mutable_names=loop_mutable_names,
                    )
                    if not _v2_same_type(inferred, body_statement.type_name):
                        operations.add("local_initializer_type_mismatch_in_while")
                    loop_environment[body_statement.name] = body_statement.type_name
                    if body_statement.mutable:
                        loop_mutable_names.add(body_statement.name)
                elif isinstance(body_statement, ast.AssignmentStatement):
                    supported_loop_statement_ids.add(id(body_statement))
                    if not isinstance(body_statement.target, ast.VariableTarget):
                        operations.add(
                            f"unsupported_assignment_target_{type(body_statement.target).__name__}"
                        )
                        continue
                    target_name = body_statement.target.name
                    if target_name not in loop_environment:
                        operations.add(f"assignment_to_unknown_binding:{target_name}")
                        continue
                    if target_name not in loop_mutable_names:
                        operations.add(f"assignment_to_immutable_binding:{target_name}")
                        continue
                    inferred = _v2_expression_type(
                        body_statement.value, loop_environment, functions,
                        unsupported_operations=operations,
                        unsupported_types=unsupported_types,
                        unsupported_callees=unsupported_callees,
                        mutable_names=loop_mutable_names,
                    )
                    if not _v2_same_type(inferred, loop_environment[target_name]):
                        operations.add("assignment_value_type_mismatch")
                elif isinstance(body_statement, ast.ReturnStatement):
                    supported_loop_statement_ids.add(id(body_statement))
                    if body_index != len(statement.body.statements) - 1:
                        syntax.add("nonterminal_return_in_while")
                    inferred = _v2_expression_type(
                        body_statement.expression, loop_environment, functions,
                        unsupported_operations=operations,
                        unsupported_types=unsupported_types,
                        unsupported_callees=unsupported_callees,
                        mutable_names=loop_mutable_names,
                    )
                    if not _v2_same_type(inferred, function.return_type):
                        operations.add("return_type_mismatch")
                    loop_returned = True
                elif isinstance(body_statement, ast.DiscardStatement):
                    supported_loop_statement_ids.add(id(body_statement))
                    _v2_expression_type(
                        body_statement.expression, loop_environment, functions,
                        unsupported_operations=operations,
                        unsupported_types=unsupported_types,
                        unsupported_callees=unsupported_callees,
                        mutable_names=loop_mutable_names,
                    )
                elif isinstance(body_statement, ast.SwitchStatement):
                    _v2_control_block_capabilities(
                        ast.Block((body_statement,), body_statement.location),
                        function,
                        functions,
                        loop_environment,
                        loop_mutable_names,
                        syntax=syntax,
                        operations=operations,
                        unsupported_types=unsupported_types,
                        unsupported_callees=unsupported_callees,
                        supported_statement_ids=supported_loop_statement_ids,
                        context="while",
                    )
                elif isinstance(body_statement, ast.WhileStatement):
                    _v2_control_block_capabilities(
                        ast.Block((body_statement,), body_statement.location),
                        function,
                        functions,
                        loop_environment,
                        loop_mutable_names,
                        syntax=syntax,
                        operations=operations,
                        unsupported_types=unsupported_types,
                        unsupported_callees=unsupported_callees,
                        supported_statement_ids=supported_loop_statement_ids,
                        context="while",
                    )
                else:
                    syntax.add(f"while_body_{type(body_statement).__name__}")
        else:
            syntax.add(type(statement).__name__)
            for node in _walk(statement):
                if isinstance(node, ast.CallExpression) and isinstance(node.callee, ast.Identifier):
                    if node.callee.name in functions:
                        local_calls.add(node.callee.name)
                    elif node.callee.name not in V2_SUPPORTED_EXTERNALS:
                        unsupported_callees.add(node.callee.name)
                elif isinstance(node, ast.CallExpression) and not isinstance(node.callee, ast.Identifier):
                    unsupported_callees.add("<indirect-call>")
                elif isinstance(node, ast.BinaryExpression):
                    if node.operator not in V2_BINARY_OPERATORS:
                        operations.add(f"binary_{node.operator.value}")
                elif isinstance(
                    node,
                    (
                        ast.RecordExpression,
                        ast.GenericTypeExpression,
                        ast.IndexExpression,
                        ast.SliceExpression,
                        ast.FieldAccessExpression,
                        ast.UnaryExpression,
                        ast.MatchExpression,
                        ast.LenExpression,
                        ast.AddressOfExpression,
                        ast.DereferenceExpression,
                    ),
                ):
                    operations.add(f"expression_{type(node).__name__}")
    if not returned:
        syntax.add("missing_terminal_return")
    if len(function.parameters) > 64:
        operations.add("parameter_capacity")
    if len(statements) > 64:
        operations.add("statement_capacity")

    top_level_ids = {id(statement) for statement in statements}
    supported_nested_statement_nodes = (
        ast.VariableDeclaration,
        ast.ReturnStatement,
        ast.AssignmentStatement,
        ast.CompoundAssignmentStatement,
        ast.DiscardStatement,
        ast.SwitchStatement,
        ast.SelectStatement,
        ast.WhileStatement,
        ast.BreakStatement,
        ast.ContinueStatement,
        ast.ForStatement,
    )
    for node in _walk(function.body):
        if isinstance(node, supported_nested_statement_nodes):
            if id(node) not in top_level_ids and id(node) not in supported_loop_statement_ids:
                if isinstance(node, ast.AssignmentStatement):
                    operations.add("mutable_assignment_in_control_flow")
                elif isinstance(node, ast.CompoundAssignmentStatement):
                    operations.add("compound_assignment")
                elif isinstance(node, ast.WhileStatement):
                    syntax.add("WhileStatement")
                elif isinstance(node, ast.SwitchStatement):
                    syntax.add("SwitchStatement")
                elif isinstance(node, ast.VariableDeclaration):
                    syntax.add("nested_local_declaration")
                else:
                    syntax.add(type(node).__name__)
        if isinstance(node, ast.CallExpression) and isinstance(node.callee, ast.Identifier):
            if node.callee.name in functions:
                local_calls.add(node.callee.name)
    for node in _walk(function.body):
        if isinstance(node, ast.CallExpression) and isinstance(node.callee, ast.Identifier):
            if node.callee.name in functions:
                local_calls.add(node.callee.name)
    return syntax, operations, unsupported_types, unsupported_callees, sorted(local_calls)


def _function_entry_v2(
    function: ast.FunctionDeclaration,
    end_offset: int,
    functions: dict[str, ast.FunctionDeclaration],
    source_sha256: str,
) -> dict[str, object]:
    syntax, operations, unsupported_types, unsupported_callees, local_calls = (
        _v2_body_capabilities(function, functions)
    )
    signature_supported = (
        not function.signature.type_parameters
        and len(function.parameters) <= 64
        and all(_v2_type_supported(item.type_name, signature=True) for item in function.parameters)
        and _v2_return_type_supported(function.return_type)
    )
    unsupported_signature_types = sorted({
        *(
            _type_text(parameter.type_name)
            for parameter in function.parameters
            if not _v2_type_supported(parameter.type_name, signature=True)
        ),
        *(
            (_type_text(function.return_type),)
            if not _v2_return_type_supported(function.return_type)
            else ()
        ),
    })
    if function.signature.type_parameters:
        unsupported_signature_types.append("generic_function_signature")
    body_unsupported_types = set(unsupported_types)
    unsupported_types = body_unsupported_types | set(unsupported_signature_types)
    body_representable = not (
        syntax or operations or body_unsupported_types or unsupported_callees
    )
    representable = (
        signature_supported
        and not syntax
        and not operations
        and not unsupported_types
        and not unsupported_callees
    )
    parameters = [
        {"name": parameter.name, "type": _type_text(parameter.type_name)}
        for parameter in function.parameters
    ]
    local_declarations = [
        node for node in _walk(function.body) if isinstance(node, ast.VariableDeclaration)
    ]
    local_bindings = [
        {
            "name": local.name,
            "type": _type_text(local.type_name),
            "mutable": local.mutable,
        }
        for local in local_declarations
    ]

    def is_vector_type(value: object) -> bool:
        return (
            isinstance(value, ast.NominalType) and value.name == "vector"
        ) or isinstance(value, ast.VectorType)

    def is_aggregate_type(value: object) -> bool:
        return isinstance(value, ast.NominalType) and value.name != "vector"

    blockers = sorted(
        [*(f"signature_type:{item}" for item in unsupported_signature_types),
         *(f"syntax:{item}" for item in syntax),
         *(f"operation:{item}" for item in operations),
         *(f"type:{item}" for item in body_unsupported_types),
         *(f"callee:{item}" for item in unsupported_callees)]
    )
    return {
        "name": function.name,
        "function_name": function.name,
        "source_start": function.location.offset,
        "source_end": end_offset,
        "source_bytes": end_offset - function.location.offset,
        "source_span": {
            "start_offset": function.location.offset,
            "end_offset": end_offset,
        },
        "parameters": parameters,
        "parameter_types": [item["type"] for item in parameters],
        "return_type": _type_text(function.return_type),
        "reference_parameters": [
            item.name for item in function.parameters
            if isinstance(item.type_name, ast.ReferenceType)
        ],
        "vector_parameters": [
            item.name for item in function.parameters
            if is_vector_type(item.type_name)
            or (
                isinstance(item.type_name, ast.ReferenceType)
                and is_vector_type(item.type_name.target)
            )
        ],
        "aggregate_parameters": [
            item.name for item in function.parameters
            if is_aggregate_type(item.type_name)
        ],
        "local_bindings": local_bindings,
        "reference_locals": [
            item.name for item in local_declarations
            if isinstance(item.type_name, ast.ReferenceType)
        ],
        "vector_locals": [
            item.name for item in local_declarations
            if is_vector_type(item.type_name)
        ],
        "aggregate_locals": [
            item.name for item in local_declarations
            if is_aggregate_type(item.type_name)
        ],
        "top_level_statement_kinds": [type(item).__name__ for item in function.body.statements],
        "signature": "(" + ", ".join(_type_text(p.type_name) for p in function.parameters)
        + ") -> " + _type_text(function.return_type),
        "calls": sorted(
            {
                node.callee.name
                for node in _walk(function.body)
                if isinstance(node, ast.CallExpression) and isinstance(node.callee, ast.Identifier)
            }
        ),
        "local_calls": local_calls,
        "signature_supported": signature_supported,
        "body_syntax_supported": not syntax,
        "operations_supported": not operations,
        "unsupported_signature_types": sorted(set(unsupported_signature_types)),
        "unsupported_syntax": sorted(syntax),
        "unsupported_operations": sorted(operations),
        "unsupported_types": sorted(unsupported_types),
        "unsupported_callees": sorted(unsupported_callees),
        "blockers": blockers,
        "primary_blocker": blockers[0] if blockers else None,
        "secondary_blockers": blockers[1:],
        "body_representable": body_representable,
        "representable": representable,
        "dependency_closed": False,
        "self_compile_tested": False,
        "self_compile_pass": False,
        "self_compile_evidence": None,
        "compiler_version": "v2",
        "source_sha256": source_sha256,
    }


def _analyze_stage1_v2(source: str) -> dict[str, object]:
    program = parse(source)
    declarations = list(program.functions)
    functions = {function.name: function for function in declarations}
    encoded = source.encode("utf-8")
    source_sha256 = hashlib.sha256(encoded).hexdigest()
    starts = [function.location.offset for function in declarations]
    entries = [
        _function_entry_v2(
            function,
            starts[index + 1] if index + 1 < len(starts) else len(source),
            functions,
            source_sha256,
        )
        for index, function in enumerate(declarations)
    ]
    by_name = {str(entry["name"]): entry for entry in entries}

    def closure(name: str, active: set[str]) -> tuple[bool, set[str]]:
        entry = by_name[name]
        if not bool(entry["representable"]):
            return False, {name}
        if name in active:
            return True, {name}
        names = {name}
        for callee in entry["local_calls"]:
            if callee not in by_name:
                return False, names
            closed, dependencies = closure(str(callee), active | {name})
            names.update(dependencies)
            if not closed:
                return False, names
        return len(names) <= 16, names

    for entry in entries:
        name = str(entry["name"])
        closed, dependency_names = closure(name, set())
        entry["dependency_closed"] = closed
        entry["dependencies_supported"] = closed
        entry["dependency_function_count"] = len(dependency_names)
        entry["external_dependencies"] = sorted(
            set(entry["calls"]) - set(entry["local_calls"])
        )
        proven = (
            source_sha256 == STAGE1_V1_SHA256
            and name in V2_PROVEN_SELF_COMPILED_FUNCTIONS
            and bool(entry["representable"])
            and closed
        )
        entry["self_compile_tested"] = proven
        entry["self_compile_pass"] = proven
        entry["selfhosted_compiler_behavior"] = (
            proven and name in V2_SELFHOSTED_COMPILER_BEHAVIOR
        )
        entry["compiler_behavior_category"] = (
            V2_SELFHOSTED_COMPILER_BEHAVIOR.get(name)
            if entry["selfhosted_compiler_behavior"]
            else None
        )
        entry["function_source_within_byte_limit"] = (
            int(entry["source_bytes"]) <= V2_MAX_SOURCE_BYTES
        )
        entry["self_compile_evidence"] = None
        if proven:
            if name == "stage1_output_chunk":
                entry["self_compile_evidence"] = (
                    "tests/test_s3_1_13_stage1_compiler.py::test_stage1_v2_compiles_canonical_output_chunk"
                )
            elif name in {
                "stage1_source_spans_equal",
                "stage1_find_symbol_value",
                "stage1_parameter_name_seen",
                "stage1_parameter_names_unique",
            }:
                entry["self_compile_evidence"] = (
                    "tests/test_s3_1_13_stage1_compiler.py::test_stage1_v2_compiles_canonical_name_resolution_cluster_natively"
                )
            elif name == "stage1_emit_decimal":
                entry["self_compile_evidence"] = (
                    "tests/test_s3_1_13_stage1_compiler.py::test_stage1_v2_emits_canonical_decimal_comparison_relations"
                )
            elif name == "stage1_emit_register":
                entry["self_compile_evidence"] = (
                    "tests/test_s3_1_13_stage1_compiler.py::test_stage1_v2_self_compiles_emission_cluster_natively"
                )
            elif name == "stage1_source_name_is_main":
                entry["self_compile_evidence"] = (
                    "tests/test_s3_1_13_stage1_compiler.py::test_stage1_v2_compiles_canonical_source_name_predicate_natively"
                )
            elif name == "stage1_find_function_id_by_source_name":
                entry["self_compile_evidence"] = (
                    "tests/test_s3_1_13_stage1_compiler.py::test_stage1_v2_executes_canonical_function_symbol_lookup_natively"
                )
            elif name in {
                "stage1_emit_ir_function_name",
                "stage1_emit_ir_callee_name",
            }:
                entry["self_compile_evidence"] = (
                    "tests/test_s3_1_13_stage1_compiler.py::test_stage1_v2_executes_canonical_ir_name_emission_cluster_natively"
                )
            else:
                entry["self_compile_evidence"] = (
                    "tests/test_s3_1_13_stage1_compiler.py::test_stage1_v2_compiles_real_reference_vector_helpers"
                )

    def count(field: str) -> int:
        return sum(bool(entry[field]) for entry in entries)

    blocker_distribution: dict[str, int] = {}
    for entry in entries:
        blockers = (
            list(entry["unsupported_syntax"])
            + list(entry["unsupported_operations"])
            + list(entry["unsupported_types"])
            + list(entry["unsupported_callees"])
        )
        for blocker in blockers:
            blocker_distribution[str(blocker)] = blocker_distribution.get(str(blocker), 0) + 1
    return {
        "schema": "s3-stage1-representability-matrix",
        "schema_version": "2.0.0",
        "compiler_version": "v2",
        "source_path": str(SOURCE_PATH).replace("\\", "/"),
        "source_sha256": source_sha256,
        "source_bytes": len(encoded),
        "functions_total": len(entries),
        "functions_signature_supported": count("signature_supported"),
        "functions_body_representable": count("body_representable"),
        "functions_representable": count("representable"),
        "functions_dependency_closed": count("dependency_closed"),
        "functions_self_compile_proven": count("self_compile_pass"),
        "functions_selfhosted_compiler_behavior": count(
            "selfhosted_compiler_behavior"
        ),
        "function_attributed_source_bytes": sum(int(entry["source_bytes"]) for entry in entries),
        "capabilities": {
            "signature_parameter_types": ["i64", "&vector<i64>", "&mut vector<i64>"],
            "signature_return_types": ["i64", "trit", "vector<i64>"],
            "local_types": ["i64", "vector<i64>"],
            "expressions": [
                "integer_literal",
                "bound_identifier",
                "i64_add",
                "i64_subtract_checked",
                "i64_multiply",
                "typed_i64_relational_comparisons",
                "i64_three_way_compare",
                "local_call",
            ],
            "external_calls": [
                "vector_new<i64>", "vector_get<i64>", "vector_len<i64>",
                "vector_push<i64>", "i64_vector_get", "i64_vector_len"
            ],
            "statements": [
                "i64_local_declaration",
                "vector<i64>_local_declaration",
                "straight_line_i64_local_reassignment",
                "ternary_match_with_mutable_i64_state",
                "top_level_while_with_loop_carried_i64_state",
                "terminal_return",
            ],
            "program_function_capacity": 16,
            "program_block_capacity": 64,
            "max_source_bytes": V2_MAX_SOURCE_BYTES,
            "max_token_count": V2_MAX_TOKEN_COUNT,
            "body_statement_capacity": 64,
            "control_flow": [
                "explicit multi-block NativeIR with typed branch, jump, and return",
                "ternary match lowered to a three-way CFG",
                "nested while lowered to CFG with verified backedges",
            ],
            "mutation": [
                "straight-line i64 reassignment",
                "i64 mutable slots with typed TLOAD/TSTORE",
                "loop-carried state through memory operations",
                "local vector<i64> initialization via vector_new<i64>",
                "vector_push<i64> through a mutable vector reference",
            ],
        },
        "blocker_distribution": dict(sorted(blocker_distribution.items())),
        "functions": entries,
    }


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


def analyze_stage1(source: str, compiler_version: str = "v1") -> dict[str, object]:
    if compiler_version == "v2":
        return _analyze_stage1_v2(source)
    if compiler_version != "v1":
        raise ValueError(f"unsupported Stage1 compiler version: {compiler_version}")
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
    parser.add_argument("--compiler-version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = args.source.read_text(encoding="utf-8")
    matrix = analyze_stage1(source, compiler_version=args.compiler_version)
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
