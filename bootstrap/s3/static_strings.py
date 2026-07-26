"""Front-end static string literal table collection."""

from __future__ import annotations

from dataclasses import dataclass

from . import ast
from .static_text import (
    StaticTextMetadata,
    decode_static_text,
    encode_static_text,
    static_text_metadata,
)


@dataclass(frozen=True, slots=True)
class StaticStringEntry:
    id: str
    value: str
    index: int

    @property
    def text(self) -> str:
        return decode_static_text(self.value)

    @property
    def utf8_bytes(self) -> bytes:
        return encode_static_text(self.value)

    @property
    def metadata(self) -> StaticTextMetadata:
        return static_text_metadata(self.value)

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


def collect_static_string_literals(program: ast.Program) -> StaticStringTable:
    entries: list[StaticStringEntry] = []
    seen: dict[str, StaticStringEntry] = {}

    def add(value: str) -> None:
        if value in seen:
            return
        index = len(entries)
        entry = StaticStringEntry(f"s{index}", value, index)
        seen[value] = entry
        entries.append(entry)

    def visit_expression(expression: ast.Expression) -> None:
        if isinstance(expression, ast.StringLiteral):
            add(expression.value)
        elif isinstance(expression, ast.UnaryExpression):
            visit_expression(expression.operand)
        elif isinstance(expression, ast.BinaryExpression):
            visit_expression(expression.left)
            visit_expression(expression.right)
        elif isinstance(expression, ast.CallExpression):
            for argument in expression.arguments:
                visit_expression(argument.expression)
        elif isinstance(expression, ast.IndexExpression):
            visit_expression(expression.index)
        elif isinstance(expression, ast.MatchExpression):
            visit_expression(expression.selector)
            for case in expression.cases:
                visit_expression(case.expression)
        elif isinstance(expression, ast.LenExpression):
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
