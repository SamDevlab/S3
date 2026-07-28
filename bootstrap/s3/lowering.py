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
    IRStaticString,
    IRType,
)
from .semantic import SemanticModel
from .static_strings import collect_static_string_literals
from .static_text import decode_static_text, normalize_static_text_newlines


TYPE_MAP = {
    ast.TypeName.TRIT: IRType.TRIT,
    ast.TypeName.TRYTE: IRType.TRYTE,
    ast.TypeName.STRING: IRType.STRING,
}


@dataclass(slots=True)
class _MutableBlock:
    name: str
    location: SourceLocation | None
    instructions: list[IRInstruction] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class LoopContext:
    continue_target: str
    break_target: str


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
        static_string_ids: dict[str, str],
    ):
        self.function = function
        self.semantic_model = semantic_model
        self.static_string_ids = static_string_ids
        self.registers: list[IRRegister] = []
        self.memory_objects: list[IRMemoryObject] = []
        self.parameters: list[IRParameter] = []
        self.blocks: list[_MutableBlock] = []
        self.current: _MutableBlock | None = None
        self.variable_scopes: list[dict[str, _LoweredBinding]] = [{}]
        self.block_counter = 0
        self.loop_stack: list[LoopContext] = []

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
        if isinstance(statement, ast.BreakStatement):
            assert self.loop_stack, "break outside loop"
            target = self.loop_stack[-1].break_target
            self._emit(
                IRInstruction(
                    IROpcode.JUMP,
                    targets=(target,),
                    location=statement.location,
                )
            )
            self.current = None
            return
        if isinstance(statement, ast.ContinueStatement):
            assert self.loop_stack, "continue outside loop"
            target = self.loop_stack[-1].continue_target
            self._emit(
                IRInstruction(
                    IROpcode.JUMP,
                    targets=(target,),
                    location=statement.location,
                )
            )
            self.current = None
            return
        if isinstance(statement, ast.AssignmentStatement):
            self._lower_assignment(statement)
            return
        if isinstance(statement, ast.CompoundAssignmentStatement):
            self._lower_compound_assignment(statement)
            return
        if isinstance(statement, ast.DiscardStatement):
            self._lower_expression(statement.expression)
            return
        if isinstance(statement, ast.SwitchStatement):
            self._lower_switch(statement)
            return
        if isinstance(statement, ast.WhileStatement):
            self._lower_while(statement)
            return
        if isinstance(statement, ast.ForStatement):
            self._lower_for(statement)
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

    def _lower_compound_assignment(
        self,
        statement: ast.CompoundAssignmentStatement,
    ) -> None:
        if isinstance(statement.target, ast.VariableTarget):
            binding = self._lookup_variable(
                statement.target.name,
                statement.target.location,
            )
            assert binding.memory is not None
            assert isinstance(binding.type_name, ast.TypeName)
            idx_zero = self._emit_constant(
                0,
                ast.TypeName.TRYTE,
                statement.target.location,
            )
            cur_val = self._allocate(binding.type_name, statement.location)
            self._emit(
                IRInstruction(
                    IROpcode.LOAD,
                    result=cur_val,
                    operands=(idx_zero,),
                    memory=binding.memory,
                    location=statement.location,
                )
            )
            rhs_val = self._lower_expression(statement.value)
            res_val = self._allocate(binding.type_name, statement.location)
            self._emit(
                IRInstruction(
                    IROpcode.ADD,
                    result=res_val,
                    operands=(cur_val, rhs_val),
                    location=statement.location,
                )
            )
            idx_zero_2 = self._emit_constant(
                0,
                ast.TypeName.TRYTE,
                statement.target.location,
            )
            self._emit(
                IRInstruction(
                    IROpcode.STORE,
                    operands=(idx_zero_2, res_val),
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
        assert isinstance(binding.type_name, ast.ArrayType)
        assert isinstance(binding.type_name.element_type, ast.TypeName)

        # 1. Lower index ONCE
        idx_reg = self._lower_expression(statement.target.index)

        # 2. Load current element ONCE
        cur_val = self._allocate(
            binding.type_name.element_type,
            statement.location,
        )
        self._emit(
            IRInstruction(
                IROpcode.LOAD,
                result=cur_val,
                operands=(idx_reg,),
                memory=binding.memory,
                location=statement.location,
            )
        )

        # 3. Lower RHS ONCE
        rhs_val = self._lower_expression(statement.value)

        # 4. Perform operation
        res_val = self._allocate(
            binding.type_name.element_type,
            statement.location,
        )
        self._emit(
            IRInstruction(
                IROpcode.ADD,
                result=res_val,
                operands=(cur_val, rhs_val),
                location=statement.location,
            )
        )

        # 5. Store back into same array index
        self._emit(
            IRInstruction(
                IROpcode.STORE,
                operands=(idx_reg, res_val),
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
        explicit_cases = {c.label: c for c in statement.cases if c.label is not None}
        fallback_case = next((c for c in statement.cases if c.label is None), None)
        cases_by_label = {
            lbl: explicit_cases.get(lbl, fallback_case)
            for lbl in (-1, 0, 1)
        }
        suffixes = {-1: "negative", 0: "neutral", 1: "positive"}

        case_blocks = {
            label: self._fresh_block(
                f"switch_{suffixes[label]}",
                cases_by_label[label].location,
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
        lowered_cases: dict[int, _MutableBlock] = {}
        for label in (-1, 0, 1):
            case = cases_by_label[label]
            case_id = id(case)
            if case_id in lowered_cases:
                orig_block = lowered_cases[case_id]
                case_blocks[label].instructions.append(
                    IRInstruction(
                        IROpcode.JUMP,
                        targets=(orig_block.name,),
                        location=case.location,
                    )
                )
                continue
            self.current = case_blocks[label]
            lowered_cases[case_id] = case_blocks[label]
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
        self.loop_stack.append(
            LoopContext(
                continue_target=condition_block.name,
                break_target=exit_block.name,
            )
        )
        try:
            self._lower_block(statement.body, create_scope=True)
        finally:
            self.loop_stack.pop()
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

    def _lower_for(self, statement: ast.ForStatement) -> None:
        start_val = self._lower_expression(statement.start_expression)
        end_val = self._lower_expression(statement.end_expression)
        step_val = self._lower_expression(statement.step_expression)
        memory = self._allocate_memory(
            statement.variable_type,
            1,
            True,
            statement.location,
        )
        idx_zero = self._emit_constant(0, ast.TypeName.TRYTE, statement.location)
        self._emit(
            IRInstruction(
                IROpcode.STORE,
                operands=(idx_zero, start_val),
                memory=memory,
                initialization=True,
                location=statement.location,
            )
        )
        cond_block = self._fresh_block("for_cond", statement.location)
        body_block = self._fresh_block("for_body", statement.location)
        step_block = self._fresh_block("for_step", statement.location)
        exit_block_0 = self._fresh_block("for_exit_0", statement.location)
        exit_block_1 = self._fresh_block("for_exit_1", statement.location)
        exit_block = self._fresh_block("for_exit", statement.location)

        self._emit(
            IRInstruction(
                IROpcode.JUMP,
                targets=(cond_block.name,),
                location=statement.location,
            )
        )

        self.current = cond_block
        cur_val = self._allocate(statement.variable_type, statement.location)
        idx_zero_c = self._emit_constant(0, ast.TypeName.TRYTE, statement.location)
        self._emit(
            IRInstruction(
                IROpcode.LOAD,
                result=cur_val,
                operands=(idx_zero_c,),
                memory=memory,
                location=statement.location,
            )
        )
        cmp_reg = self._allocate(ast.TypeName.TRIT, statement.location)
        self._emit(
            IRInstruction(
                IROpcode.COMPARE,
                result=cmp_reg,
                operands=(cur_val, end_val),
                location=statement.location,
            )
        )
        def _is_negative_constant(expr: ast.Expression) -> bool:
            if isinstance(expr, ast.IntegerLiteral):
                return expr.value < 0
            if isinstance(expr, ast.UnaryExpression) and expr.operator == ast.UnaryOperator.NEGATE:
                if isinstance(expr.operand, ast.IntegerLiteral):
                    return expr.operand.value > 0
            return False

        if _is_negative_constant(statement.step_expression):
            branch_targets = (exit_block_0.name, exit_block_1.name, body_block.name)
        else:
            branch_targets = (body_block.name, exit_block_0.name, exit_block_1.name)

        self._emit(
            IRInstruction(
                IROpcode.BRANCH3,
                operands=(cmp_reg,),
                targets=branch_targets,
                location=statement.location,
            )
        )

        self.current = body_block
        self.loop_stack.append(
            LoopContext(
                continue_target=step_block.name,
                break_target=exit_block.name,
            )
        )
        self.variable_scopes.append({})
        self.variable_scopes[-1][statement.variable_name] = _LoweredBinding(
            statement.variable_type,
            mutable=False,
            memory=memory,
        )
        try:
            self._lower_block(statement.body, create_scope=False)
        finally:
            self.variable_scopes.pop()
            self.loop_stack.pop()

        if self.current is not None:
            self.current.instructions.append(
                IRInstruction(
                    IROpcode.JUMP,
                    targets=(step_block.name,),
                    location=statement.location,
                )
            )

        self.current = step_block
        step_cur = self._allocate(statement.variable_type, statement.location)
        idx_zero_s = self._emit_constant(0, ast.TypeName.TRYTE, statement.location)
        self._emit(
            IRInstruction(
                IROpcode.LOAD,
                result=step_cur,
                operands=(idx_zero_s,),
                memory=memory,
                location=statement.location,
            )
        )
        next_val = self._allocate(statement.variable_type, statement.location)
        self._emit(
            IRInstruction(
                IROpcode.ADD,
                result=next_val,
                operands=(step_cur, step_val),
                location=statement.location,
            )
        )
        idx_zero_s2 = self._emit_constant(0, ast.TypeName.TRYTE, statement.location)
        self._emit(
            IRInstruction(
                IROpcode.STORE,
                operands=(idx_zero_s2, next_val),
                memory=memory,
                initialization=False,
                location=statement.location,
            )
        )
        self._emit(
            IRInstruction(
                IROpcode.JUMP,
                targets=(cond_block.name,),
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
        if isinstance(expression, ast.StringLiteral):
            try:
                static_string = self.static_string_ids[
                    decode_static_text(expression.value)
                ]
            except KeyError as error:
                raise LoweringError(
                    "string literal is missing from static string table",
                    expression.location,
                ) from error
            result = self._allocate(ast.TypeName.STRING, expression.location)
            self._emit(
                IRInstruction(
                    IROpcode.CONST_STR,
                    result=result,
                    static_string=static_string,
                    location=expression.location,
                )
            )
            return result
        if (
            isinstance(expression, ast.BinaryExpression)
            and expression.operator is ast.BinaryOperator.ADD
            and expression_type is ast.TypeName.STRING
        ):
            text = evaluate_constant_static_text_expression(expression)
            try:
                static_string = self.static_string_ids[text]
            except KeyError as error:
                raise LoweringError(
                    "constant static text expression is missing from static string table",
                    expression.location,
                ) from error
            result = self._allocate(ast.TypeName.STRING, expression.location)
            self._emit(
                IRInstruction(
                    IROpcode.CONST_STR,
                    result=result,
                    static_string=static_string,
                    location=expression.location,
                )
            )
            return result
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
        if isinstance(expression, ast.MatchExpression):
            return self._lower_match_expression(expression)
        if isinstance(expression, ast.LenExpression):
            return self._lower_len(expression)
        raise LoweringError("unsupported expression", expression.location)

    def _lower_len(self, expression: ast.LenExpression) -> int:
        argument_type = self.semantic_model.declared_type_of(expression.argument)
        if isinstance(argument_type, ast.ArrayType):
            return self._emit_constant(
                argument_type.length,
                ast.TypeName.TRYTE,
                expression.location,
            )
        if argument_type is ast.TypeName.STRING:
            text = evaluate_constant_static_text_expression(expression.argument)
            return self._emit_constant(
                len(text),
                ast.TypeName.TRYTE,
                expression.location,
            )
        raise LoweringError(
            "len expression has unsupported semantic argument type",
            expression.location,
        )

    def _lower_binary(
        self,
        expression: ast.BinaryExpression,
        result_type: ast.TypeName,
    ) -> int:
        if (
            expression.operator
            in (ast.BinaryOperator.EQUAL, ast.BinaryOperator.NOT_EQUAL)
            and self.semantic_model.declared_type_of(expression.left)
            is ast.TypeName.STRING
            and self.semantic_model.declared_type_of(expression.right)
            is ast.TypeName.STRING
        ):
            left_text = evaluate_constant_static_text_expression(expression.left)
            right_text = evaluate_constant_static_text_expression(expression.right)
            equal = left_text == right_text
            if expression.operator is ast.BinaryOperator.NOT_EQUAL:
                equal = not equal
            return self._emit_constant(
                -1 if equal else 0,
                ast.TypeName.TRIT,
                expression.location,
            )
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

        if expression.operator in (
            ast.BinaryOperator.EQUAL,
            ast.BinaryOperator.NOT_EQUAL,
            ast.BinaryOperator.LESS,
            ast.BinaryOperator.LESS_EQUAL,
            ast.BinaryOperator.GREATER,
            ast.BinaryOperator.GREATER_EQUAL,
        ):
            return self._lower_relational_expression(expression)

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

    def _lower_relational_expression(
        self,
        expression: ast.BinaryExpression,
    ) -> int:
        left = self._lower_expression(expression.left)
        right = self._lower_expression(expression.right)
        cmp_reg = self._allocate(ast.TypeName.TRIT, expression.location)
        self._emit(
            IRInstruction(
                IROpcode.COMPARE,
                result=cmp_reg,
                operands=(left, right),
                location=expression.location,
            )
        )
        op = expression.operator
        if op is ast.BinaryOperator.EQUAL:
            neg_val, zero_val, pos_val = 0, -1, 0
        elif op is ast.BinaryOperator.NOT_EQUAL:
            neg_val, zero_val, pos_val = -1, 0, -1
        elif op is ast.BinaryOperator.LESS:
            neg_val, zero_val, pos_val = -1, 0, 0
        elif op is ast.BinaryOperator.LESS_EQUAL:
            neg_val, zero_val, pos_val = -1, -1, 0
        elif op is ast.BinaryOperator.GREATER:
            neg_val, zero_val, pos_val = 0, 0, -1
        elif op is ast.BinaryOperator.GREATER_EQUAL:
            neg_val, zero_val, pos_val = 0, -1, -1
        else:
            raise LoweringError(f"unsupported relational operator '{op.value}'", expression.location)

        memory = self._allocate_memory(ast.TypeName.TRIT, 1, True, expression.location)

        neg_block = self._fresh_block("rel_neg", expression.location)
        zero_block = self._fresh_block("rel_zero", expression.location)
        pos_block = self._fresh_block("rel_pos", expression.location)
        cont_block = self._fresh_block("rel_cont", expression.location)

        self._emit(
            IRInstruction(
                IROpcode.BRANCH3,
                operands=(cmp_reg,),
                targets=(neg_block.name, zero_block.name, pos_block.name),
                location=expression.location,
            )
        )

        for blk, val in (
            (neg_block, neg_val),
            (zero_block, zero_val),
            (pos_block, pos_val),
        ):
            self.current = blk
            idx = self._emit_constant(0, ast.TypeName.TRYTE, expression.location)
            val_reg = self._emit_constant(val, ast.TypeName.TRIT, expression.location)
            self._emit(
                IRInstruction(
                    IROpcode.STORE,
                    operands=(idx, val_reg),
                    memory=memory,
                    initialization=True,
                    location=expression.location,
                )
            )
            self._emit(
                IRInstruction(
                    IROpcode.JUMP,
                    targets=(cont_block.name,),
                    location=expression.location,
                )
            )

        self.current = cont_block
        idx = self._emit_constant(0, ast.TypeName.TRYTE, expression.location)
        result_reg = self._allocate(ast.TypeName.TRIT, expression.location)
        self._emit(
            IRInstruction(
                IROpcode.LOAD,
                result=result_reg,
                operands=(idx,),
                memory=memory,
                location=expression.location,
            )
        )
        return result_reg

    def _lower_match_expression(
        self,
        expression: ast.MatchExpression,
    ) -> int:
        selector_reg = self._lower_expression(expression.selector)
        result_type = self.semantic_model.expression_types[id(expression)]
        memory = self._allocate_memory(result_type, 1, True, expression.location)
        explicit_cases = {c.label: c for c in expression.cases if c.label is not None}
        fallback_case = next((c for c in expression.cases if c.label is None), None)
        cases_by_label = {
            lbl: explicit_cases.get(lbl, fallback_case)
            for lbl in (-1, 0, 1)
        }

        case_blocks = {
            label: self._fresh_block(
                f"match_expr_{label}",
                cases_by_label[label].location,
            )
            for label in (-1, 0, 1)
        }

        continuation = self._fresh_block("match_expr_cont", expression.location)

        self._emit(
            IRInstruction(
                IROpcode.BRANCH3,
                operands=(selector_reg,),
                targets=tuple(case_blocks[label].name for label in (-1, 0, 1)),
                location=expression.location,
            )
        )

        lowered_cases: dict[int, _MutableBlock] = {}
        for label in (-1, 0, 1):
            case = cases_by_label[label]
            case_id = id(case)
            if case_id in lowered_cases:
                orig_block = lowered_cases[case_id]
                case_blocks[label].instructions.append(
                    IRInstruction(
                        IROpcode.JUMP,
                        targets=(orig_block.name,),
                        location=case.location,
                    )
                )
                continue
            self.current = case_blocks[label]
            lowered_cases[case_id] = case_blocks[label]
            val_reg = self._lower_expression(case.expression)
            idx = self._emit_constant(0, ast.TypeName.TRYTE, case.location)
            self._emit(
                IRInstruction(
                    IROpcode.STORE,
                    operands=(idx, val_reg),
                    memory=memory,
                    initialization=True,
                    location=case.location,
                )
            )
            self._emit(
                IRInstruction(
                    IROpcode.JUMP,
                    targets=(continuation.name,),
                    location=case.location,
                )
            )

        self.current = continuation
        val_idx = self._emit_constant(0, ast.TypeName.TRYTE, expression.location)
        result_reg = self._allocate(result_type, expression.location)
        self._emit(
            IRInstruction(
                IROpcode.LOAD,
                operands=(val_idx,),
                memory=memory,
                result=result_reg,
                location=expression.location,
            )
        )
        return result_reg


def evaluate_constant_static_text_expression(expression: ast.Expression) -> str:
    if isinstance(expression, ast.StringLiteral):
        return decode_static_text(expression.value)
    if (
        isinstance(expression, ast.BinaryExpression)
        and expression.operator is ast.BinaryOperator.ADD
    ):
        return normalize_static_text_newlines(
            evaluate_constant_static_text_expression(expression.left)
            + evaluate_constant_static_text_expression(expression.right)
        )
    raise LoweringError(
        "expected a compile-time static text expression",
        expression.location,
    )


def lower(program: ast.Program, semantic_model: SemanticModel) -> IRModule:
    static_table = collect_static_string_literals(program)
    static_strings = tuple(
        IRStaticString(entry.id, entry.text) for entry in static_table.entries
    )
    static_string_ids = {
        entry.value: entry.id for entry in static_table.entries
    }
    functions: list[IRFunction] = []
    for function in program.functions:
        try:
            functions.append(
                FunctionLowerer(
                    function,
                    semantic_model,
                    static_string_ids,
                ).lower()
            )
        except LoweringError as error:
            error.add_diagnostic_context(function=function.name)
            raise
    return IRModule(tuple(functions), static_strings)
