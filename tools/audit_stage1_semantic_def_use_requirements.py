"""Inventory Stage1 bootstrap semantic def-use requirements from the typed AST.

This is an external Python oracle for planning/testing only.  It does not build
Stage2 and must never become the Stage1 emitter backend.  The important design
choice is that mutable locals are storage identities: scalar/array reads require
explicit load instructions and writes require explicit store instructions.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from bootstrap.s3 import ast
from bootstrap.s3.pipeline import compile_source


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "semantic-def-use-requirements-audit.json"
)

_COMPARISONS = {
    ast.BinaryOperator.COMPARE,
    ast.BinaryOperator.EQUAL,
    ast.BinaryOperator.NOT_EQUAL,
    ast.BinaryOperator.LESS,
    ast.BinaryOperator.LESS_EQUAL,
    ast.BinaryOperator.GREATER,
    ast.BinaryOperator.GREATER_EQUAL,
}


class Inventory:
    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.array_locals: dict[str, int] = {}
        self.scalar_locals: set[str] = set()
        self.parameters: set[str] = set()
        self.indexed_names: Counter[str] = Counter()
        self.unsupported_nodes: Counter[str] = Counter()

    def expression(self, value: ast.Expression) -> None:
        if isinstance(value, ast.IntegerLiteral):
            self.counts["integer_constants"] += 1
            return
        if isinstance(value, ast.Identifier):
            self.counts["identifier_value_reads"] += 1
            if value.name in self.scalar_locals:
                self.counts["scalar_local_loads"] += 1
            elif value.name in self.parameters:
                self.counts["parameter_reads"] += 1
            return
        if isinstance(value, ast.IndexExpression):
            self.counts["index_loads"] += 1
            if isinstance(value.target, ast.Identifier):
                self.indexed_names[value.target.name] += 1
                if value.target.name in self.array_locals:
                    self.counts["fixed_array_loads"] += 1
                else:
                    self.counts["nonlocal_or_unknown_index_loads"] += 1
            else:
                self.expression(value.target)
                self.counts["complex_index_targets"] += 1
            self.expression(value.index)
            return
        if isinstance(value, ast.BinaryExpression):
            if value.operator in _COMPARISONS:
                self.counts["comparison_operations"] += 1
            else:
                self.counts["arithmetic_operations"] += 1
            self.expression(value.left)
            self.expression(value.right)
            return
        if isinstance(value, ast.UnaryExpression):
            self.counts["unary_operations"] += 1
            self.expression(value.operand)
            return
        if isinstance(value, ast.CallExpression):
            self.counts["calls"] += 1
            self.counts["call_arguments"] += len(value.arguments)
            if not isinstance(value.callee, ast.Identifier):
                self.expression(value.callee)
                self.counts["non_identifier_callees"] += 1
            for argument in value.arguments:
                self.expression(argument.expression)
            return
        if isinstance(value, ast.MatchExpression):
            self.counts["match_expressions"] += 1
            self.expression(value.selector)
            for case in value.cases:
                self.expression(case.expression)
            return
        if isinstance(value, ast.LenExpression):
            self.counts["len_expressions"] += 1
            self.expression(value.argument)
            return
        if isinstance(value, ast.AddressOfExpression):
            self.counts["address_of_expressions"] += 1
            self.expression(value.operand)
            return
        if isinstance(value, ast.DereferenceExpression):
            self.counts["dereference_expressions"] += 1
            self.expression(value.operand)
            return
        if isinstance(value, ast.SliceExpression):
            self.counts["slice_expressions"] += 1
            self.expression(value.target)
            self.expression(value.start)
            self.expression(value.end)
            return
        if isinstance(value, ast.FieldAccessExpression):
            self.counts["field_access_expressions"] += 1
            self.expression(value.target)
            return
        if isinstance(value, ast.RecordExpression):
            self.counts["record_expressions"] += 1
            for field in value.fields:
                self.expression(field.expression)
            return
        if isinstance(value, ast.GenericTypeExpression):
            self.counts["generic_type_expressions"] += 1
            self.expression(value.target)
            return
        self.unsupported_nodes[type(value).__name__] += 1

    def initializer(self, value: ast.Initializer) -> None:
        if isinstance(value, ast.ArrayLiteral):
            self.counts["array_initializers"] += 1
            self.counts["array_initializer_elements"] += len(value.elements)
            for element in value.elements:
                self.expression(element)
            return
        self.expression(value)

    def target_store(self, target: ast.AssignmentTarget, *, compound: bool) -> None:
        if isinstance(target, ast.VariableTarget):
            self.counts["scalar_local_stores"] += 1
            if compound:
                self.counts["scalar_local_loads"] += 1
            return
        if isinstance(target, ast.IndexTarget):
            self.counts["index_stores"] += 1
            self.indexed_names[target.array_name] += 1
            if target.array_name in self.array_locals:
                self.counts["fixed_array_stores"] += 1
                if compound:
                    self.counts["fixed_array_loads"] += 1
            else:
                self.counts["nonlocal_or_unknown_index_stores"] += 1
            self.expression(target.index)
            return
        if isinstance(target, ast.DereferenceTarget):
            self.counts["dereference_stores"] += 1
            self.expression(target.reference)
            return
        if isinstance(target, ast.FieldTarget):
            self.counts["field_stores"] += 1
            self.expression(target.target)
            return
        self.unsupported_nodes[type(target).__name__] += 1

    def block(self, block: ast.Block) -> None:
        for statement in block.statements:
            if isinstance(statement, ast.VariableDeclaration):
                self.counts["local_declarations"] += 1
                if isinstance(statement.type_name, ast.ArrayType):
                    self.counts["fixed_array_local_declarations"] += 1
                    self.array_locals[statement.name] = statement.type_name.length
                else:
                    self.counts["scalar_local_declarations"] += 1
                    self.scalar_locals.add(statement.name)
                self.initializer(statement.initializer)
            elif isinstance(statement, ast.AssignmentStatement):
                self.counts["assignments"] += 1
                self.target_store(statement.target, compound=False)
                self.initializer(statement.value)
            elif isinstance(statement, ast.CompoundAssignmentStatement):
                self.counts["compound_assignments"] += 1
                self.target_store(statement.target, compound=True)
                self.initializer(statement.value)
                self.counts["arithmetic_operations"] += 1
            elif isinstance(statement, ast.DiscardStatement):
                self.counts["discard_statements"] += 1
                if isinstance(statement.expression, ast.CallExpression):
                    self.counts["discarded_calls"] += 1
                self.expression(statement.expression)
            elif isinstance(statement, ast.ReturnStatement):
                self.counts["returns"] += 1
                self.expression(statement.expression)
            elif isinstance(statement, ast.WhileStatement):
                self.counts["while_statements"] += 1
                self.counts["conditional_terminator_inputs"] += 1
                self.expression(statement.condition)
                self.block(statement.body)
            elif isinstance(statement, ast.SwitchStatement):
                self.counts["match_statements"] += 1
                self.counts["conditional_terminator_inputs"] += 1
                self.expression(statement.expression)
                for case in statement.cases:
                    self.block(case.body)
            elif isinstance(statement, ast.BreakStatement):
                self.counts["break_statements"] += 1
            elif isinstance(statement, ast.ContinueStatement):
                self.counts["continue_statements"] += 1
            elif isinstance(statement, ast.ForStatement):
                self.counts["for_statements"] += 1
                self.expression(statement.start_expression)
                self.expression(statement.end_expression)
                self.expression(statement.step_expression)
                self.block(statement.body)
            elif isinstance(statement, ast.SelectStatement):
                self.counts["select_statements"] += 1
                for arm in statement.arms:
                    self.expression(arm.operation)
                    self.block(arm.body)
            else:
                self.unsupported_nodes[type(statement).__name__] += 1


def inventory_source(source: str) -> dict[str, object]:
    compilation = compile_source(source)
    aggregate: Counter[str] = Counter()
    indexed_names: Counter[str] = Counter()
    unsupported: Counter[str] = Counter()
    function_details: list[dict[str, object]] = []

    for function in compilation.ast.functions:
        inv = Inventory()
        inv.parameters.update(parameter.name for parameter in function.parameters)
        inv.block(function.body)
        aggregate.update(inv.counts)
        indexed_names.update(inv.indexed_names)
        unsupported.update(inv.unsupported_nodes)
        function_details.append({
            "name": function.name,
            "parameters": len(function.parameters),
            "counts": dict(sorted(inv.counts.items())),
            "array_locals": dict(sorted(inv.array_locals.items())),
            "indexed_names": dict(sorted(inv.indexed_names.items())),
            "unsupported_nodes": dict(sorted(inv.unsupported_nodes.items())),
        })

    required = {"CONST", "RETURN_VALUE"}
    if aggregate["scalar_local_loads"]:
        required.add("LOAD_LOCAL")
    if aggregate["scalar_local_stores"]:
        required.add("STORE_LOCAL")
    if aggregate["index_loads"]:
        required.add("LOAD_INDEX")
    if aggregate["index_stores"]:
        required.add("STORE_INDEX")
    if aggregate["arithmetic_operations"]:
        required.update({"ADD_SUB_MUL_DIV_AS_MEASURED"})
    if aggregate["comparison_operations"]:
        required.add("COMPARE")
    if aggregate["calls"]:
        required.update({"INTERNAL_CALL", "FOREIGN_CALL"})
    if aggregate["while_statements"] or aggregate["match_statements"]:
        required.update({"CONDITIONAL_BRANCH", "JUMP"})
    if aggregate["array_initializers"]:
        required.add("FIXED_ARRAY_INIT_OR_ORDERED_ELEMENT_STORES")

    return {
        "schema": "s3.selfhost.semantic-def-use-requirements-audit.v1",
        "status": "STATIC_ORACLE_REQUIREMENTS_ONLY_NATIVE_IR_V2_DIFFERENTIAL_REQUIRED",
        "native_evidence": False,
        "python_role": "EXTERNAL_TYPED_AST_ORACLE_ONLY_NOT_COMPILER_BACKEND",
        "functions": len(compilation.ast.functions),
        "foreign_functions": len(compilation.ast.foreign_functions),
        "aggregate_counts": dict(sorted(aggregate.items())),
        "indexed_names": dict(sorted(indexed_names.items())),
        "required_instruction_semantics": sorted(required),
        "unsupported_or_nonbootstrap_nodes": dict(sorted(unsupported.items())),
        "function_details": function_details,
        "critical_contract": {
            "mutable_local_is_storage_identity": True,
            "local_read_requires_explicit_load_result": True,
            "local_store_consumes_source_value": True,
            "array_read_requires_explicit_index_value_and_result": True,
            "array_write_requires_explicit_index_and_source_value": True,
            "phi_required_for_local_storage": False,
            "instruction_results_single_definition": True,
            "emitter_source_reread_allowed": False,
        },
        "next": "DIFFERENTIAL_NATIVE_IR_V2_MUST_ACCOUNT_FOR_EVERY_MEASURED_STORAGE_READ_WRITE_INDEX_AND_RESULT",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    result = inventory_source(args.source.resolve().read_text(encoding="utf-8"))
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    counts = result["aggregate_counts"]
    print(f"SCALAR_LOCAL_LOADS={counts.get('scalar_local_loads', 0)}")
    print(f"SCALAR_LOCAL_STORES={counts.get('scalar_local_stores', 0)}")
    print(f"INDEX_LOADS={counts.get('index_loads', 0)}")
    print(f"INDEX_STORES={counts.get('index_stores', 0)}")
    print("NATIVE_EVIDENCE=False")
    print(f"NEXT={result['next']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
