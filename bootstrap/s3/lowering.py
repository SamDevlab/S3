"""Lower typed S3 AST into block-based, subtraction-free S3 IR."""

from __future__ import annotations

from dataclasses import dataclass, field

from . import ast
from .diagnostics import LoweringError, SourceLocation
from .ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRMemoryObject,
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


@dataclass(frozen=True, slots=True)
class _LoweredBinding:
    type_name: ast.DeclaredType
    mutable: bool
    register: int | None = None
    memory: int | None = None


class FunctionLowerer:
    def __init__(
        self,
        function: ast.FunctionDeclaration,
        semantic_model: SemanticModel,
    ):
        self.function = function
        self.semantic_model = semantic_model
        self.registers: list[IRRegister] = []
        self.memory_objects: list[IRMemoryObject] = []
        self.parameters: list[IRParameter] = []
        self.blocks: list[_MutableBlock] = []
        self.current: _MutableBlock | None = None
        self.variable_scopes: list[dict[str, _LoweredBinding]] = [{}]
        self.block_counter = 0

    def lower(self) -> IRFunction:
        for parameter in self.function.parameters:
            assert isinstance(parameter.type_name, ast.TypeName)
            register = self._allocate(parameter.type_name, parameter.location)
            self.parameters.append(
                IRParameter(
                    parameter.name,
                    register,
                    TYPE_MAP[parameter.type_name],
                    parameter.location,
                )
            )
            self.variable_scopes[0][parameter.name] = _LoweredBinding(
                parameter.type_name,
                mutable=False,
                register=register,
            )
        self.current = self._create_block("entry", self.function.body.location)
        self._lower_block(self.function.body, create_scope=False)
        if self.current is not None:
            raise LoweringError(
                f"function '{self.function.name}' ended without a terminator",
                self.function.location,
            )
        assert isinstance(self.function.return_type, ast.TypeName)
        return IRFunction(
            name=self.function.name,
            parameters=tuple(self.parameters),
            return_type=TYPE_MAP[self.function.return_type],
            registers=tuple(self.registers),
            blocks=tuple(
                IRBasicBlock(
                    block.name,
                    tuple(block.instructions),
                    block.location,
                )
                for block in self.blocks
            ),
            location=self.function.location,
            memory_objects=tuple(self.memory_objects),
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
        if isinstance(statement, ast.AssignmentStatement):
            self._lower_assignment(statement)
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
        if isinstance(statement, ast.WhileStatement):
            self._lower_while(statement)
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

    def _allocate_memory(
        self,
        element_type: ast.TypeName,
        length: int,
        mutable: bool,
        location: SourceLocation,
    ) -> int:
        index = len(self.memory_objects)
        self.memory_objects.append(
            IRMemoryObject(
                index,
                TYPE_MAP[element_type],
                length,
                mutable,
                location,
            )
        )
        return index

    def _lookup_variable(
        self,
        name: str,
        location: SourceLocation,
    ) -> _LoweredBinding:
        for scope in reversed(self.variable_scopes):
            if name in scope:
                return scope[name]
        raise LoweringError(f"unknown variable '{name}'", location)

    def _lower_declaration(self, declaration: ast.VariableDeclaration) -> None:
        if isinstance(declaration.type_name, ast.ArrayType):
            assert isinstance(declaration.type_name.element_type, ast.TypeName)
            assert isinstance(declaration.initializer, ast.ArrayLiteral)
            memory = self._allocate_memory(
                declaration.type_name.element_type,
                declaration.type_name.length,
                declaration.mutable,
                declaration.location,
            )
            for index, element in enumerate(declaration.initializer.elements):
                index_register = self._emit_constant(
                    index,
                    ast.TypeName.TRYTE,
                    element.location,
                )
                value = self._lower_expression(element)
                self._emit(
                    IRInstruction(
                        IROpcode.STORE,
                        operands=(index_register, value),
                        memory=memory,
                        initialization=True,
                        location=element.location,
                    )
                )
            self.variable_scopes[-1][declaration.name] = _LoweredBinding(
                declaration.type_name,
                declaration.mutable,
                memory=memory,
            )
            return

        if isinstance(declaration.initializer, ast.ArrayLiteral):
            raise LoweringError(
                "scalar declaration received an array initializer",
                declaration.initializer.location,
            )
        initializer = self._lower_expression(declaration.initializer)
        if declaration.mutable:
            memory = self._allocate_memory(
                declaration.type_name,
                1,
                True,
                declaration.location,
            )
            index = self._emit_constant(
                0,
                ast.TypeName.TRYTE,
                declaration.location,
            )
            self._emit(
                IRInstruction(
                    IROpcode.STORE,
                    operands=(index, initializer),
                    memory=memory,
                    initialization=True,
                    location=declaration.location,
                )
            )
            self.variable_scopes[-1][declaration.name] = _LoweredBinding(
                declaration.type_name,
                True,
                memory=memory,
            )
            return

        variable = self._allocate(declaration.type_name, declaration.location)
        self._emit(
            IRInstruction(
                IROpcode.MOVE,
                result=variable,
                operands=(initializer,),
                location=declaration.location,
            )
        )
        self.variable_scopes[-1][declaration.name] = _LoweredBinding(
            declaration.type_name,
            False,
            register=variable,
        )

    def _lower_assignment(self, statement: ast.AssignmentStatement) -> None:
        if isinstance(statement.target, ast.VariableTarget):
            binding = self._lookup_variable(
                statement.target.name,
                statement.target.location,
            )
            assert binding.memory is not None
            if isinstance(statement.value, ast.ArrayLiteral):
                raise LoweringError(
                    "scalar assignment received an array literal",
                    statement.value.location,
                )
            value = self._lower_expression(statement.value)
            index = self._emit_constant(
                0,
                ast.TypeName.TRYTE,
                statement.target.location,
            )
            self._emit(
                IRInstruction(
                    IROpcode.STORE,
                    operands=(index, value),
                    memory=binding.memory,
                    location=statement.location,
                )
            )
            return

        binding = self._lookup_variable(
            statement.target.array_name,
            statement.target.location,
        )
        assert binding.memory is not None
        index = self._lower_expression(statement.target.index)
        if isinstance(statement.value, ast.ArrayLiteral):
            raise LoweringError(
                "array element assignment received an array literal",
                statement.value.location,
            )
        value = self._lower_expression(statement.value)
        self._emit(
            IRInstruction(
                IROpcode.STORE,
                operands=(index, value),
                memory=binding.memory,
                location=statement.location,
            )
        )

    def _emit_constant(
        self,
        value: int,
        type_name: ast.TypeName,
        location: SourceLocation,
    ) -> int:
        result = self._allocate(type_name, location)
        self._emit(
            IRInstruction(
                IROpcode.CONST,
                result=result,
                immediate=value,
                location=location,
            )
        )
        return result

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

    def _lower_while(self, statement: ast.WhileStatement) -> None:
        condition_block = self._fresh_block("while_condition", statement.location)
        body_block = self._fresh_block("while_body", statement.location)
        exit_block_0 = self._fresh_block("while_exit_0", statement.location)
        exit_block_1 = self._fresh_block("while_exit_1", statement.location)
        exit_block = self._fresh_block("while_exit", statement.location)

        self._emit(
            IRInstruction(
                IROpcode.JUMP,
                targets=(condition_block.name,),
                location=statement.location,
            )
        )

        self.current = condition_block
        condition = self._lower_expression(statement.condition)

        self._emit(
            IRInstruction(
                IROpcode.BRANCH3,
                operands=(condition,),
                targets=(body_block.name, exit_block_0.name, exit_block_1.name),
                location=statement.location,
            )
        )

        self.current = body_block
        self._lower_block(statement.body, create_scope=True)
        body_terminated = self.current is None

        if not body_terminated:
            self.current.instructions.append(
                IRInstruction(
                    IROpcode.JUMP,
                    targets=(condition_block.name,),
                    location=statement.location,
                )
            )

        self.current = exit_block_0
        self._emit(
            IRInstruction(
                IROpcode.JUMP,
                targets=(exit_block.name,),
                location=statement.location,
            )
        )

        self.current = exit_block_1
        self._emit(
            IRInstruction(
                IROpcode.JUMP,
                targets=(exit_block.name,),
                location=statement.location,
            )
        )

        self.current = exit_block

    def _lower_expression(self, expression: ast.Expression) -> int:
        expression_type = self.semantic_model.type_of(expression)
        if isinstance(expression, ast.IntegerLiteral):
            return self._emit_constant(
                expression.value,
                expression_type,
                expression.location,
            )
        if isinstance(expression, ast.Identifier):
            binding = self._lookup_variable(expression.name, expression.location)
            if binding.register is not None:
                return binding.register
            assert binding.memory is not None
            assert isinstance(binding.type_name, ast.TypeName)
            index = self._emit_constant(
                0,
                ast.TypeName.TRYTE,
                expression.location,
            )
            result = self._allocate(binding.type_name, expression.location)
            self._emit(
                IRInstruction(
                    IROpcode.LOAD,
                    result=result,
                    operands=(index,),
                    memory=binding.memory,
                    location=expression.location,
                )
            )
            return result
        if isinstance(expression, ast.IndexExpression):
            binding = self._lookup_variable(
                expression.array_name,
                expression.location,
            )
            assert binding.memory is not None
            assert isinstance(binding.type_name, ast.ArrayType)
            assert isinstance(binding.type_name.element_type, ast.TypeName)
            index = self._lower_expression(expression.index)
            result = self._allocate(
                binding.type_name.element_type,
                expression.location,
            )
            self._emit(
                IRInstruction(
                    IROpcode.LOAD,
                    result=result,
                    operands=(index,),
                    memory=binding.memory,
                    location=expression.location,
                )
            )
            return result
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
    functions: list[IRFunction] = []
    for function in program.functions:
        try:
            functions.append(FunctionLowerer(function, semantic_model).lower())
        except LoweringError as error:
            error.add_diagnostic_context(function=function.name)
            raise
    return IRModule(tuple(functions))
