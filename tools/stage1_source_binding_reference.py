"""Extract deterministic source-level bindings needed by the Stage1 semantic port.

Stage0 typed IR intentionally does not preserve every source binding name for
storage objects. This companion oracle walks the typed AST so the Stage1 port has
an explicit target for parameter/local identity, declared type, mutability, and
lexical scope without pretending physical IR memory IDs are source identities.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from bootstrap.s3 import ast
from bootstrap.s3.pipeline import compile_source

SCHEMA = "s3.selfhost.source-bindings-reference.v1"


def _location(value: object) -> dict[str, object] | None:
    location = getattr(value, "location", None)
    if location is None:
        return None
    rendered = location.to_dict()
    return rendered if isinstance(rendered, dict) else None


def _type_name(value: ast.DeclaredType) -> str:
    if isinstance(value, ast.TypeName):
        return value.value
    if isinstance(value, ast.ArrayType):
        return f"array[{value.length}]<{_type_name(value.element_type)}>"
    if isinstance(value, ast.ReferenceType):
        prefix = "mut_ref" if value.mutable else "ref"
        return f"{prefix}<{_type_name(value.target)}>"
    if isinstance(value, ast.SliceType):
        prefix = "mut_slice" if value.mutable else "slice"
        return f"{prefix}<{value.element_type.value}>"
    if isinstance(value, ast.NominalType):
        if value.type_arguments:
            args = ",".join(_type_name(item) for item in value.type_arguments)
            return f"{value.name}<{args}>"
        return value.name
    if isinstance(value, ast.TypeParameterType):
        return f"type_parameter<{value.name}>"
    raise TypeError(f"unsupported declared type: {type(value).__name__}")


def _walk_block(
    block: ast.Block,
    *,
    function_index: int,
    function_name: str,
    scope_path: tuple[int, ...],
    next_binding_id: list[int],
) -> Iterable[dict[str, Any]]:
    for statement_ordinal, statement in enumerate(block.statements):
        statement_scope = scope_path + (statement_ordinal,)
        if isinstance(statement, ast.VariableDeclaration):
            binding_id = next_binding_id[0]
            next_binding_id[0] += 1
            yield {
                "binding_id": binding_id,
                "function_index": function_index,
                "function": function_name,
                "kind": "local",
                "name": statement.name,
                "declared_type": _type_name(statement.type_name),
                "mutable": statement.mutable,
                "scope_path": list(scope_path),
                "statement_ordinal": statement_ordinal,
                "source": _location(statement),
                "semantic_value_link": "TO_BE_RESOLVED_BY_STAGE1_LOWERING",
                "physical_storage_is_identity": False,
            }
        elif isinstance(statement, ast.ForStatement):
            binding_id = next_binding_id[0]
            next_binding_id[0] += 1
            yield {
                "binding_id": binding_id,
                "function_index": function_index,
                "function": function_name,
                "kind": "loop_variable",
                "name": statement.variable_name,
                "declared_type": statement.variable_type.value,
                "mutable": False,
                "scope_path": list(statement_scope),
                "statement_ordinal": statement_ordinal,
                "source": _location(statement),
                "semantic_value_link": "TO_BE_RESOLVED_BY_STAGE1_LOWERING",
                "physical_storage_is_identity": False,
            }
            yield from _walk_block(
                statement.body,
                function_index=function_index,
                function_name=function_name,
                scope_path=statement_scope,
                next_binding_id=next_binding_id,
            )
        elif isinstance(statement, ast.WhileStatement):
            yield from _walk_block(
                statement.body,
                function_index=function_index,
                function_name=function_name,
                scope_path=statement_scope,
                next_binding_id=next_binding_id,
            )
        elif isinstance(statement, ast.SwitchStatement):
            for case_ordinal, case in enumerate(statement.cases):
                yield from _walk_block(
                    case.body,
                    function_index=function_index,
                    function_name=function_name,
                    scope_path=statement_scope + (case_ordinal,),
                    next_binding_id=next_binding_id,
                )
        elif isinstance(statement, ast.SelectStatement):
            for arm_ordinal, arm in enumerate(statement.arms):
                yield from _walk_block(
                    arm.body,
                    function_index=function_index,
                    function_name=function_name,
                    scope_path=statement_scope + (arm_ordinal,),
                    next_binding_id=next_binding_id,
                )


def extract_bindings(program: ast.Program) -> dict[str, Any]:
    bindings: list[dict[str, Any]] = []
    next_binding_id = [0]

    for function_index, function in enumerate(program.functions):
        for ordinal, parameter in enumerate(function.parameters):
            binding_id = next_binding_id[0]
            next_binding_id[0] += 1
            bindings.append(
                {
                    "binding_id": binding_id,
                    "function_index": function_index,
                    "function": function.name,
                    "kind": "parameter",
                    "name": parameter.name,
                    "declared_type": _type_name(parameter.type_name),
                    "mutable": False,
                    "parameter_ordinal": ordinal,
                    "scope_path": [],
                    "source": _location(parameter),
                    "semantic_value_link": "PARAMETER_REGISTER_VALUE",
                    "physical_storage_is_identity": False,
                }
            )
        bindings.extend(
            _walk_block(
                function.body,
                function_index=function_index,
                function_name=function.name,
                scope_path=(),
                next_binding_id=next_binding_id,
            )
        )

    return {
        "schema": SCHEMA,
        "binding_count": len(bindings),
        "bindings": bindings,
        "identity_policy": "FUNCTION_PLUS_LEXICAL_SCOPE_PLUS_EXACT_NAME",
        "physical_storage_is_source_identity": False,
    }


def build_binding_reference(source: str) -> dict[str, Any]:
    compilation = compile_source(source)
    return extract_bindings(compilation.ast)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    reference = build_binding_reference(args.source.read_text(encoding="utf-8"))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(reference, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"OUTPUT={args.output}")
    print(f"BINDINGS={reference['binding_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
