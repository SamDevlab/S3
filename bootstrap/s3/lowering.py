"""Lower typed S3 AST into block-based, subtraction-free S3 IR."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ast
from .diagnostics import LoweringError, SourceLocation
from .ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRModule,
    IROpcode,
    IRParameter,
    IRRegister,
    IRType,
)
from .semantic import SemanticModel


TYPE_MAP = {
    ast.TypeName.TRIT: IRType.TRIT,
    ast.TypeName.TRYTE: IRType.TRYTE,
}


@dataclass(slots=True)
class _MutableBlock:
    name: str
    location: SourceLocation | None
    instructions: list[IRInstruction] = field(default_factory=list)


class FunctionLowerer:
    def __init__(
        self,
        function: ast.FunctionDeclaration,
        semantic_model: SemanticModel,
    ):
        self.function = function
        self.semantic_model = semantic_model
        self.registers: list[IRRegister] = []
        self.parameters: list[IRParameter] = []
        self.blocks: list[_MutableBlock] = []
        self.current: _MutableBlock | None = None
        self.variable_scopes: list[dict[str, int]] = [{}]
        self.block_counter = 0

    def lower(self) -> IRFunction:
        for parameter in self.function.parameters:
            register = self._allocate(parameter.type_name, parameter.location)
            self.parameters.append(
                IRParameter(
                    parameter.name,
                    register,
                    TYPE_MAP[parameter.type_name],
                    parameter.location,
                )
            )
            self.variable_scopes[0][parameter.name] = register
        self.current = self._create_block("entry", self.function.body.location)
        self._lower_block(self.function.body, create_scope=False)
        if self.current is not None:
            raise LoweringError(
                f"function '{self.function.name}' ended without a terminator",
                self.function.location,
            )
        return IRFunction(
            self.function.name,
            tuple(self.parameters),
            TYPE_MAP[self.function.return_type],
            tuple(self.registers),
            tuple(
                IRBasicBlock(
                    block.name,
                    tuple(block.instructions),
                    block.location,
                )
                for block in self.blocks
            ),
            self.function.location,
        )

    def _create_block(
        self,
        name: str,
        location: SourceLocation | None,
    ) -> _MutableBlock:
        block = _MutableBlock(name, location)
        self.blocks.append(block)
        return block

    def _fresh_block(
        self,
        purpose: str,
        location: SourceLocation | None,
    ) -> _MutableBlock:
        name = f"{purpose}_{self.block_counter}"
        self.block_counter += 1
        return self._create_block(name, location)

    def _emit(self, instruction: IRInstruction) -> None:
        if self.current is None:
            raise LoweringError(
                "cannot emit an instruction after a terminator",
                instruction.location,
            )
        self.current.instructions.append(instruction)

    def _lower_block(self, block: ast.Block, *, create_scope: bool) -> None:
        if create_scope:
            self.variable_scopes.append({})
        try:
            for statement in block.statements:
                self._lower_statement(statement)
        finally:
            if create_scope:
                self.variable_scopes.pop()

    def _lower_statement(self, statement: ast.Statement) -> None:
        if isinstance(statement, ast.VariableDeclaration):
            self._lower_declaration(statement)
            return
        if isinstance(statement, ast.ReturnStatement):
            value = self._lower_expression(statement.expression)
            self._emit(
                IRInstruction(
                    IROpcode.RETURN,
                    operands=(value,),
                    location=statement.location,
                )
            )
            self.current = None
            return
        if isinstance(statement, ast.SwitchStatement):
            self._lower_switch(statement)
            return
        raise LoweringError("unsupported statement", statement.location)

    def _allocate(
        self,
        type_name: ast.TypeName,
        location: SourceLocation | None,
    ) -> int:
        index = len(self.registers)
        self.registers.append(IRRegister(index, TYPE_MAP[type_name], location))
        return index

    def _lookup_variable(self, name: str, location: SourceLocation) -> int:
        for scope in reversed(self.variable_scopes):
            if name in scope:
                return scope[name]
        raise LoweringError(f"unknown variable '{name}'", location)

    def _lower_declaration(self, declaration: ast.VariableDeclaration) -> None:
        initializer = self._lower_expression(declaration.initializer)
        variable = self._allocate(declaration.type_name, declaration.location)
        self._emit(
            IRInstruction(
                IROpcode.MOVE,
                result=variable,
                operands=(initializer,),
                location=declaration.location,
            )
        )
        self.variable_scopes[-1][declaration.name] = variable

    def _lower_switch(self, statement: ast.SwitchStatement) -> None:
        condition = self._lower_expression(statement.expression)
        cases = {case.label: case for case in statement.cases}
        suffixes = {-1: "negative", 0: "neutral", 1: "positive"}
        case_blocks = {
            label: self._fresh_block(
                f"switch_{suffixes[label]}",
                cases[label].location,
            )
            for label in (-1, 0, 1)
        }
        self._emit(
            IRInstruction(
                IROpcode.BRANCH3,
                operands=(condition,),
                targets=tuple(case_blocks[label].name for label in (-1, 0, 1)),
                location=statement.location,
            )
        )

        open_blocks: list[tuple[_MutableBlock, SourceLocation]] = []
        for label in (-1, 0, 1):
            case = cases[label]
            self.current = case_blocks[label]
            self._lower_block(case.body, create_scope=True)
            if self.current is not None:
                open_blocks.append((self.current, case.location))

        if not open_blocks:
            self.current = None
            return
        continuation = self._fresh_block(
            "switch_continue",
            statement.location,
        )
        for block, location in open_blocks:
            block.instructions.append(
                IRInstruction(
                    IROpcode.JUMP,
                    targets=(continuation.name,),
                    location=location,
                )
            )
        self.current = continuation

    def _lower_expression(self, expression: ast.Expression) -> int:
        expression_type = self.semantic_model.type_of(expression)
        if isinstance(expression, ast.IntegerLiteral):
            result = self._allocate(expression_type, expression.location)
            self._emit(
                IRInstruction(
                    IROpcode.CONST,
                    result=result,
                    immediate=expression.value,
                    location=expression.location,
                )
            )
            return result
        if isinstance(expression, ast.Identifier):
            return self._lookup_variable(expression.name, expression.location)
        if isinstance(expression, ast.CallExpression):
            arguments = tuple(
                self._lower_expression(argument.expression)
                for argument in expression.arguments
            )
            result = self._allocate(expression_type, expression.location)
            self._emit(
                IRInstruction(
                    IROpcode.CALL,
                    result=result,
                    operands=arguments,
                    callee=expression.function_name,
                    location=expression.location,
                )
            )
            return result
        if isinstance(expression, ast.UnaryExpression):
            operand = self._lower_expression(expression.operand)
            result = self._allocate(expression_type, expression.location)
            self._emit(
                IRInstruction(
                    IROpcode.INVERT,
                    result=result,
                    operands=(operand,),
                    location=expression.location,
                )
            )
            return result
        if isinstance(expression, ast.BinaryExpression):
            return self._lower_binary(expression, expression_type)
        raise LoweringError("unsupported expression", expression.location)

    def _lower_binary(
        self,
        expression: ast.BinaryExpression,
        result_type: ast.TypeName,
    ) -> int:
        left = self._lower_expression(expression.left)
        right = self._lower_expression(expression.right)
        if expression.operator is ast.BinaryOperator.SUBTRACT:
            inverted = self._allocate(
                self.semantic_model.type_of(expression.right),
                expression.right.location,
            )
            self._emit(
                IRInstruction(
                    IROpcode.INVERT,
                    result=inverted,
                    operands=(right,),
                    location=expression.location,
                )
            )
            result = self._allocate(result_type, expression.location)
            self._emit(
                IRInstruction(
                    IROpcode.ADD,
                    result=result,
                    operands=(left, inverted),
                    location=expression.location,
                )
            )
            return result

        opcode_map = {
            ast.BinaryOperator.ADD: IROpcode.ADD,
            ast.BinaryOperator.MINIMUM: IROpcode.MINIMUM,
            ast.BinaryOperator.MAXIMUM: IROpcode.MAXIMUM,
            ast.BinaryOperator.COMPARE: IROpcode.COMPARE,
        }
        try:
            opcode = opcode_map[expression.operator]
        except KeyError as error:
            raise LoweringError(
                f"unsupported operator '{expression.operator.value}'",
                expression.location,
            ) from error
        result = self._allocate(result_type, expression.location)
        self._emit(
            IRInstruction(
                opcode,
                result=result,
                operands=(left, right),
                location=expression.location,
            )
        )
        return result


def lower(program: ast.Program, semantic_model: SemanticModel) -> IRModule:
    return IRModule(
        tuple(
            FunctionLowerer(function, semantic_model).lower()
            for function in program.functions
        )
    )

