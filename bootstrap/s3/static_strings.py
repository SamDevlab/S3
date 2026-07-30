"""Front-end static string literal table collection."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Callable

from . import ast
from .static_text import (
    StaticTextMetadata,
    decode_static_text,
    normalize_static_text_newlines,
)


STATIC_TEXT_QUERY_BUILTINS = frozenset(
    ("contains", "starts_with", "ends_with", "find")
)
STATIC_TEXT_TRANSFORM_BUILTINS = frozenset(
    ("upper", "lower", "trim", "repeat", "replace")
)


@dataclass(frozen=True, slots=True)
class StaticStringEntry:
    id: str
    value: str
    index: int

    @property
    def text(self) -> str:
        return self.value

    @property
    def utf8_bytes(self) -> bytes:
        return self.value.encode("utf-8")

    @property
    def metadata(self) -> StaticTextMetadata:
        data = self.utf8_bytes
        line_count = 0 if self.value == "" else len(self.value.splitlines())
        return StaticTextMetadata(
            byte_count=len(data),
            line_count=line_count,
            sha256=hashlib.sha256(data).hexdigest(),
        )

    @property
    def byte_count(self) -> int:
        return self.metadata.byte_count

    @property
    def line_count(self) -> int:
        return self.metadata.line_count

    @property
    def sha256(self) -> str:
        return self.metadata.sha256


@dataclass(frozen=True, slots=True)
class StaticStringTable:
    entries: tuple[StaticStringEntry, ...]

    def entry_for_value(self, value: str) -> StaticStringEntry | None:
        for entry in self.entries:
            if entry.value == value:
                return entry
        return None


def collect_static_string_literals(
    program: ast.Program,
    static_text_of: Callable[[ast.Expression], str | None] | None = None,
) -> StaticStringTable:
    entries: list[StaticStringEntry] = []
    seen: dict[str, StaticStringEntry] = {}

    def add(value: str) -> None:
        if value in seen:
            return
        index = len(entries)
        entry = StaticStringEntry(f"s{index}", value, index)
        seen[value] = entry
        entries.append(entry)

    def constant_text(expression: ast.Expression) -> str | None:
        if isinstance(expression, ast.StringLiteral):
            return decode_static_text(expression.value)
        if (
            isinstance(expression, ast.BinaryExpression)
            and expression.operator is ast.BinaryOperator.ADD
        ):
            left = constant_text(expression.left)
            right = constant_text(expression.right)
            if left is not None and right is not None:
                return normalize_static_text_newlines(left + right)
        if isinstance(expression, ast.CallExpression):
            if expression.function_name in STATIC_TEXT_TRANSFORM_BUILTINS:
                args = [constant_text(arg.expression) for arg in expression.arguments]
                if expression.function_name in ("upper", "lower", "trim") and len(args) == 1 and args[0] is not None:
                    if expression.function_name == "upper":
                        return args[0].upper()
                    if expression.function_name == "lower":
                        return args[0].lower()
                    return args[0].strip()
                if expression.function_name == "repeat" and len(args) == 2 and args[0] is not None:
                    if isinstance(expression.arguments[1].expression, ast.IntegerLiteral):
                        cnt = expression.arguments[1].expression.value
                        if cnt >= 0:
                            return args[0] * cnt
                if expression.function_name == "replace" and len(args) == 3 and all(a is not None for a in args):
                    return args[0].replace(args[1], args[2])
        return None

    def visit_expression(expression: ast.Expression) -> None:
        folded = (
            static_text_of(expression)
            if static_text_of is not None
            else constant_text(expression)
        )
        if folded is not None:
            add(folded)
            return
        if isinstance(expression, ast.StringLiteral):
            add(decode_static_text(expression.value))
        elif isinstance(expression, ast.UnaryExpression):
            visit_expression(expression.operand)
        elif isinstance(expression, ast.BinaryExpression):
            left_text = (
                static_text_of(expression.left)
                if static_text_of is not None
                else constant_text(expression.left)
            )
            right_text = (
                static_text_of(expression.right)
                if static_text_of is not None
                else constant_text(expression.right)
            )
            RELATIONAL_OPS = (
                ast.BinaryOperator.EQUAL,
                ast.BinaryOperator.NOT_EQUAL,
                ast.BinaryOperator.LESS,
                ast.BinaryOperator.LESS_EQUAL,
                ast.BinaryOperator.GREATER,
                ast.BinaryOperator.GREATER_EQUAL,
            )
            if (
                expression.operator in RELATIONAL_OPS
                and left_text is not None
                and right_text is not None
            ):
                return
            visit_expression(expression.left)
            visit_expression(expression.right)
        elif isinstance(expression, ast.CallExpression):
            if expression.function_name in STATIC_TEXT_QUERY_BUILTINS:
                argument_texts = [
                    (
                        static_text_of(argument.expression)
                        if static_text_of is not None
                        else constant_text(argument.expression)
                    )
                    for argument in expression.arguments
                ]
                if argument_texts and all(text is not None for text in argument_texts):
                    return
            for argument in expression.arguments:
                visit_expression(argument.expression)
        elif isinstance(expression, ast.IndexExpression):
            visit_expression(expression.index)
        elif isinstance(expression, ast.SliceExpression):
            visit_expression(expression.target)
            visit_expression(expression.start)
            visit_expression(expression.end)
        elif isinstance(expression, ast.MatchExpression):
            visit_expression(expression.selector)
            for case in expression.cases:
                visit_expression(case.expression)
        elif isinstance(expression, ast.LenExpression):
            text = (
                static_text_of(expression.argument)
                if static_text_of is not None
                else constant_text(expression.argument)
            )
            if text is not None:
                return
            visit_expression(expression.argument)

    def visit_initializer(initializer: ast.Initializer) -> None:
        if isinstance(initializer, ast.ArrayLiteral):
            for element in initializer.elements:
                visit_expression(element)
        else:
            visit_expression(initializer)

    def visit_target(target: ast.AssignmentTarget) -> None:
        if isinstance(target, ast.IndexTarget):
            visit_expression(target.index)

    def visit_block(block: ast.Block) -> None:
        for statement in block.statements:
            if isinstance(statement, ast.VariableDeclaration):
                visit_initializer(statement.initializer)
            elif isinstance(statement, (ast.AssignmentStatement, ast.CompoundAssignmentStatement)):
                visit_target(statement.target)
                visit_initializer(statement.value)
            elif isinstance(statement, ast.DiscardStatement):
                visit_expression(statement.expression)
            elif isinstance(statement, ast.ReturnStatement):
                visit_expression(statement.expression)
            elif isinstance(statement, ast.SwitchStatement):
                visit_expression(statement.expression)
                for case in statement.cases:
                    visit_block(case.body)
            elif isinstance(statement, ast.WhileStatement):
                visit_block(statement.body)
            elif isinstance(statement, ast.ForStatement):
                visit_expression(statement.start_expression)
                visit_expression(statement.end_expression)
                visit_expression(statement.step_expression)
                visit_block(statement.body)
            elif isinstance(statement, (ast.BreakStatement, ast.ContinueStatement)):
                pass

    for function in program.functions:
        visit_block(function.body)

    return StaticStringTable(tuple(entries))
