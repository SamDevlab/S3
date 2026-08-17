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
    ast.TypeName.I64: IRType.I64,
    ast.TypeName.F64: IRType.F64,
    ast.TypeName.STRING: IRType.STRING,
    ast.TypeName.BYTES: IRType.BYTES,
    ast.TypeName.TEXT: IRType.TEXT,
    ast.TypeName.TRYTE_VECTOR: IRType.VECTOR,
    ast.TypeName.I64_VECTOR: IRType.VECTOR,
    ast.TypeName.F64_VECTOR: IRType.VECTOR,
    ast.TypeName.I64_MAP: IRType.VECTOR,
    ast.TypeName.I64_SET: IRType.VECTOR,
    ast.TypeName.HOST_CAPABILITY: IRType.I64,
    ast.TypeName.RESOURCE_HANDLE: IRType.I64,
}

_DYNAMIC_TYPES = {
    ast.TypeName.BYTES,
    ast.TypeName.TEXT,
    ast.TypeName.TRYTE_VECTOR,
    ast.TypeName.I64_VECTOR,
    ast.TypeName.F64_VECTOR,
    ast.TypeName.I64_MAP,
    ast.TypeName.I64_SET,
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
    fields: dict[str, _LoweredBinding] | None = None
    slice_length_register: int | None = None


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
        self.parameter_array_initializers: list[
            tuple[int, tuple[int, ...], SourceLocation]
        ] = []

    def lower(self, *, external: bool = False) -> IRFunction:
        for parameter in self.function.parameters:
            if isinstance(parameter.type_name, (ast.ReferenceType, ast.SliceType)):
                target = self._storage_type(parameter.type_name.target if isinstance(parameter.type_name, ast.ReferenceType) else parameter.type_name.element_type, parameter.location)
                register = self._allocate_reference(parameter.type_name, parameter.location)
                slice_length_register = (
                    self._allocate(ast.TypeName.I64, parameter.location)
                    if isinstance(parameter.type_name, ast.SliceType)
                    else None
                )
                self.parameters.append(IRParameter(
                    parameter.name, register, IRType.REFERENCE, parameter.location,
                    TYPE_MAP[target], parameter.type_name.mutable,
                    isinstance(parameter.type_name, ast.SliceType),
                    slice_length_register,
                ))
                if slice_length_register is not None:
                    self.parameters.append(IRParameter(
                        parameter.name + "__length",
                        slice_length_register,
                        IRType.I64,
                        parameter.location,
                    ))
                self.variable_scopes[0][parameter.name] = _LoweredBinding(
                    parameter.type_name, parameter.type_name.mutable, register=register,
                    slice_length_register=slice_length_register,
                )
                continue
            if isinstance(parameter.type_name, ast.ArrayType):
                element_layout = self.semantic_model.fixed_value_layout(
                    parameter.type_name.element_type
                )
                registers: list[int] = []
                for index in range(parameter.type_name.length):
                    for cell in element_layout.cells:
                        register = self._allocate(cell.type_name, parameter.location)
                        registers.append(register)
                        self.parameters.append(
                            IRParameter(
                                parameter.name
                                + "__"
                                + self._array_cell_name(index)
                                + ("__" + "__".join(cell.path) if cell.path else ""),
                                register,
                                TYPE_MAP[cell.type_name],
                                parameter.location,
                            )
                        )
                if isinstance(parameter.type_name.element_type, ast.TypeName):
                    memory = self._allocate_memory(
                        parameter.type_name.element_type,
                        parameter.type_name.length,
                        False,
                        parameter.location,
                    )
                    self.parameter_array_initializers.append(
                        (memory, tuple(registers), parameter.location)
                    )
                    binding = _LoweredBinding(
                        parameter.type_name,
                        mutable=False,
                        memory=memory,
                    )
                else:
                    binding = self._array_binding_from_registers(
                        parameter.type_name,
                        tuple(registers),
                        parameter.location,
                    )
                self.variable_scopes[0][parameter.name] = binding
                continue
            if (
                isinstance(parameter.type_name, ast.NominalType)
                and self.semantic_model.is_enum_type(parameter.type_name)
                and self.semantic_model.enum_cell_count(parameter.type_name.name) > 1
            ):
                fields: dict[str, _LoweredBinding] = {}
                layout = self.semantic_model.enum_layout(parameter.type_name.name)
                for index, slot_type in enumerate(layout.slot_types):
                    register = self._allocate(slot_type, parameter.location)
                    self.parameters.append(
                        IRParameter(
                            parameter.name + "__" + self._enum_cell_name(index),
                            register,
                            TYPE_MAP[slot_type],
                            parameter.location,
                        )
                    )
                    self._set_enum_cell_binding(fields, index, slot_type, register)
                self.variable_scopes[0][parameter.name] = _LoweredBinding(
                    parameter.type_name,
                    mutable=False,
                    fields=fields,
                )
                continue

            if (
                isinstance(parameter.type_name, ast.NominalType)
                and self.semantic_model.is_record_type(parameter.type_name)
            ):
                record = self.semantic_model.record(parameter.type_name.name)
                fields: dict[str, _LoweredBinding] = {}
                for leaf in self.semantic_model.record_leaves(record.name):
                    storage_type = leaf.type_name
                    register = self._allocate(storage_type, leaf.location)
                    self.parameters.append(
                        IRParameter(
                            parameter.name + "__" + "__".join(leaf.path),
                            register,
                            TYPE_MAP[storage_type],
                            leaf.location,
                        )
                    )
                    self._set_leaf_binding(
                        fields,
                        record,
                        leaf.path,
                        register,
                    )
                self.variable_scopes[0][parameter.name] = _LoweredBinding(
                    parameter.type_name,
                    mutable=False,
                    fields=fields,
                )
                continue

            storage_type = self._storage_type(parameter.type_name, parameter.location)
            register = self._allocate(storage_type, parameter.location)
            self.parameters.append(
                IRParameter(
                    parameter.name,
                    register,
                    TYPE_MAP[storage_type],
                    parameter.location,
                )
            )
            self.variable_scopes[0][parameter.name] = _LoweredBinding(
                parameter.type_name,
                mutable=False,
                register=register,
            )
        if external:
            result_types = self._result_types(
                self.function.return_type,
                self.function.signature.location,
            )
            return IRFunction(
                name=self.function.name,
                parameters=tuple(self.parameters),
                return_type=result_types[0],
                registers=tuple(self.registers),
                blocks=(),
                location=self.function.location,
                result_types=result_types,
                external=True,
            )
        self.current = self._create_block("entry", self.function.body.location)
        for memory, registers, location in self.parameter_array_initializers:
            self._store_array_registers(
                memory,
                registers,
                location,
                initialization=True,
            )
        self._lower_block(self.function.body, create_scope=False)
        if self.current is not None:
            raise LoweringError(
                f"function '{self.function.name}' ended without a terminator",
                self.function.location,
            )
        result_types = self._result_types(
            self.function.return_type,
            self.function.signature.location,
        )
        return IRFunction(
            name=self.function.name,
            parameters=tuple(self.parameters),
            return_type=result_types[0],
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
            result_types=result_types,
            exported=self.function.exported,
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
            values = self._lower_return_expression(statement.expression)
            self._emit(
                IRInstruction(
                    IROpcode.RETURN,
                    operands=values,
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
            if isinstance(statement.expression, ast.CallExpression):
                declared_type = self.semantic_model.declared_type_of(statement.expression)
                self._lower_call_result_registers(statement.expression, declared_type)
            else:
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

    def _allocate_reference(
        self, type_name: ast.ReferenceType | ast.SliceType, location: SourceLocation | None
    ) -> int:
        index = len(self.registers)
        target = self._storage_type(type_name.target if isinstance(type_name, ast.ReferenceType) else type_name.element_type, location)
        self.registers.append(IRRegister(
            index, IRType.REFERENCE, location, TYPE_MAP[target], type_name.mutable,
            isinstance(type_name, ast.SliceType)
        ))
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

    def _storage_type(
        self,
        type_name: ast.DeclaredType,
        location: SourceLocation | None,
    ) -> ast.TypeName:
        if isinstance(type_name, ast.TypeName):
            return type_name
        if isinstance(type_name, ast.SliceType):
            return type_name.element_type
        if (
            isinstance(type_name, ast.NominalType)
            and self.semantic_model.is_enum_type(type_name)
        ):
            return ast.TypeName.TRYTE
        if (
            isinstance(type_name, ast.NominalType)
            and self.semantic_model.is_record_type(type_name)
        ):
            leaves = self.semantic_model.record_leaves(type_name.name)
            if len(leaves) == 1:
                return leaves[0].type_name
            raise LoweringError(
                "multi-field record value cannot be lowered as a scalar value",
                location,
            )
        raise LoweringError("unsupported storage type", location)

    def _result_types(
        self,
        type_name: ast.DeclaredType,
        location: SourceLocation | None,
    ) -> tuple[IRType, ...]:
        if isinstance(type_name, ast.TypeName) and type_name in _DYNAMIC_TYPES:
            return (TYPE_MAP[type_name],)
        layout = self.semantic_model.fixed_value_layout(type_name)
        if not layout.cells:
            raise LoweringError("function result layout has no cells", location)
        return tuple(TYPE_MAP[cell.type_name] for cell in layout.cells)

    @staticmethod
    def _enum_cell_name(index: int) -> str:
        return f"cell{index}"

    @staticmethod
    def _array_cell_name(index: int) -> str:
        return f"index{index}"

    @staticmethod
    def _enum_cell_index(name: str, location: SourceLocation) -> int:
        if not name.startswith("cell"):
            raise LoweringError(f"enum cell '{name}' is unavailable", location)
        try:
            return int(name[4:])
        except ValueError as error:
            raise LoweringError(f"enum cell '{name}' is unavailable", location) from error

    def _set_enum_cell_binding(
        self,
        fields: dict[str, _LoweredBinding],
        index: int,
        slot_type: ast.TypeName,
        register: int,
    ) -> None:
        fields[self._enum_cell_name(index)] = _LoweredBinding(
            slot_type,
            mutable=False,
            register=register,
        )

    def _zero_value(
        self,
        type_name: ast.TypeName,
        location: SourceLocation,
    ) -> int:
        if type_name is ast.TypeName.STRING:
            try:
                static_string = self.static_string_ids[""]
            except KeyError as error:
                raise LoweringError(
                    "empty static string is missing from static string table",
                    location,
                ) from error
            result = self._allocate(ast.TypeName.STRING, location)
            self._emit(
                IRInstruction(
                    IROpcode.CONST_STR,
                    result=result,
                    static_string=static_string,
                    location=location,
                )
            )
            return result
        dynamic_constructors = {
            ast.TypeName.BYTES: "bytes_new",
            ast.TypeName.TEXT: "text_new",
            ast.TypeName.TRYTE_VECTOR: "tryte_vector_new",
            ast.TypeName.I64_VECTOR: "i64_vector_new",
            ast.TypeName.F64_VECTOR: "f64_vector_new",
            ast.TypeName.I64_MAP: "i64_map_new",
            ast.TypeName.I64_SET: "i64_set_new",
        }
        constructor = dynamic_constructors.get(type_name)
        if constructor is not None:
            capacity = self._emit_constant(0, ast.TypeName.I64, location)
            result = self._allocate(type_name, location)
            self._emit(
                IRInstruction(
                    IROpcode.CALL,
                    result=result,
                    results=(result,),
                    operands=(capacity,),
                    callee=constructor,
                    location=location,
                )
            )
            return result
        return self._emit_constant(0, type_name, location)

    def _set_leaf_binding(
        self,
        fields: dict[str, _LoweredBinding],
        record,
        path: tuple[str, ...],
        register: int,
    ) -> None:
        field = record.field(path[0])
        assert field is not None
        if len(path) == 1:
            fields[field.name] = _LoweredBinding(
                field.type_name,
                mutable=False,
                register=register,
            )
            return
        if isinstance(field.type_name, ast.ArrayType):
            assert isinstance(field.type_name.element_type, ast.TypeName)
            binding = fields.get(field.name)
            if binding is None:
                binding = _LoweredBinding(
                    field.type_name,
                    mutable=False,
                    fields={},
                )
                fields[field.name] = binding
            assert binding.fields is not None
            binding.fields[path[1]] = _LoweredBinding(
                field.type_name.element_type,
                mutable=False,
                register=register,
            )
            return
        assert isinstance(field.type_name, ast.NominalType)
        if self.semantic_model.is_enum_type(field.type_name):
            layout = self.semantic_model.enum_layout(field.type_name.name)
            index = self._enum_cell_index(path[1], field.location)
            binding = fields.get(field.name)
            if binding is None:
                nested_fields: dict[str, _LoweredBinding] = {}
                binding = _LoweredBinding(
                    field.type_name,
                    mutable=False,
                    fields=nested_fields,
                )
                fields[field.name] = binding
            assert binding.fields is not None
            self._set_enum_cell_binding(
                binding.fields,
                index,
                layout.slot_types[index],
                register,
            )
            return
        nested = self.semantic_model.record(field.type_name.name)
        binding = fields.get(field.name)
        if binding is None:
            nested_fields: dict[str, _LoweredBinding] = {}
            binding = _LoweredBinding(
                field.type_name,
                mutable=False,
                fields=nested_fields,
            )
            fields[field.name] = binding
        assert binding.fields is not None
        self._set_leaf_binding(binding.fields, nested, path[1:], register)

    def _fields_from_single_leaf_register(
        self,
        record,
        register: int,
    ) -> dict[str, _LoweredBinding]:
        leaves = self.semantic_model.record_leaves(record.name)
        if len(leaves) != 1:
            raise LoweringError(
                "multi-field record value cannot be lowered from one scalar",
                record.location,
            )
        fields: dict[str, _LoweredBinding] = {}
        self._set_leaf_binding(fields, record, leaves[0].path, register)
        return fields

    def _field_binding_at_path(
        self,
        fields: dict[str, _LoweredBinding],
        path: tuple[str, ...],
        location: SourceLocation,
    ) -> _LoweredBinding:
        binding = fields.get(path[0])
        if binding is None:
            raise LoweringError(
                f"record field '{path[0]}' is unavailable",
                location,
            )
        if len(path) == 1:
            return binding
        if binding.fields is None:
            raise LoweringError(
                f"record field '{path[0]}' is not a nested record",
                location,
            )
        return self._field_binding_at_path(binding.fields, path[1:], location)

    def _allocate_result_cells(
        self,
        type_name: ast.DeclaredType,
        location: SourceLocation,
    ) -> tuple[int, ...]:
        layout = self.semantic_model.fixed_value_layout(type_name)
        return tuple(self._allocate(cell.type_name, location) for cell in layout.cells)

    def _array_binding_from_registers(
        self,
        type_name: ast.ArrayType,
        registers: tuple[int, ...],
        location: SourceLocation,
    ) -> _LoweredBinding:
        element_width = self.semantic_model.fixed_value_layout(
            type_name.element_type
        ).cell_count
        if len(registers) != type_name.length * element_width:
            raise LoweringError(
                f"array expected {type_name.length * element_width} cells; got {len(registers)}",
                location,
            )
        elements: dict[str, _LoweredBinding] = {}
        for index in range(type_name.length):
            start = index * element_width
            elements[self._array_cell_name(index)] = self._binding_from_registers(
                type_name.element_type,
                registers[start : start + element_width],
                location,
            )
        return _LoweredBinding(
            type_name,
            mutable=False,
            fields=elements,
        )

    def _binding_from_registers(
        self,
        type_name: ast.DeclaredType,
        registers: tuple[int, ...],
        location: SourceLocation,
    ) -> _LoweredBinding:
        layout = self.semantic_model.fixed_value_layout(type_name)
        if len(registers) != layout.cell_count:
            raise LoweringError(
                f"value expected {layout.cell_count} cells; got {len(registers)}",
                location,
            )
        if isinstance(type_name, ast.TypeName):
            return _LoweredBinding(
                type_name,
                mutable=False,
                register=registers[0],
            )
        if isinstance(type_name, ast.ArrayType):
            return self._array_binding_from_registers(type_name, registers, location)
        if isinstance(type_name, ast.NominalType) and self.semantic_model.is_record_type(type_name):
            return self._record_binding_from_registers(
                self.semantic_model.record(type_name.name), registers, location
            )
        if isinstance(type_name, ast.NominalType) and self.semantic_model.is_enum_type(type_name):
            return self._enum_binding_from_registers(type_name.name, registers, location)
        raise LoweringError("unsupported aggregate value", location)

    def _flatten_value_registers(
        self,
        binding: _LoweredBinding,
        type_name: ast.DeclaredType,
        location: SourceLocation,
    ) -> tuple[int, ...]:
        if isinstance(type_name, ast.TypeName):
            if binding.register is None:
                raise LoweringError("scalar value register is unavailable", location)
            return (binding.register,)
        if isinstance(type_name, ast.ArrayType):
            return self._flatten_array_registers(binding, type_name, location)
        if isinstance(type_name, ast.NominalType) and self.semantic_model.is_record_type(type_name):
            if binding.fields is None:
                raise LoweringError("record fields are unavailable", location)
            return self._flatten_record_registers(type_name.name, binding.fields, location)
        if isinstance(type_name, ast.NominalType) and self.semantic_model.is_enum_type(type_name):
            return self._flatten_enum_registers(type_name.name, binding, location)
        raise LoweringError("unsupported aggregate value", location)

    def _flatten_array_registers(
        self,
        binding: _LoweredBinding,
        type_name: ast.ArrayType,
        location: SourceLocation,
    ) -> tuple[int, ...]:
        if binding.memory is not None:
            if not isinstance(type_name.element_type, ast.TypeName):
                raise LoweringError(
                    "aggregate array elements cannot use one memory object",
                    location,
                )
            registers: list[int] = []
            for index in range(type_name.length):
                index_register = self._emit_constant(
                    index,
                    ast.TypeName.TRYTE,
                    location,
                )
                result = self._allocate(type_name.element_type, location)
                self._emit(
                    IRInstruction(
                        IROpcode.LOAD,
                        result=result,
                        operands=(index_register,),
                        memory=binding.memory,
                        location=location,
                    )
                )
                registers.append(result)
            return tuple(registers)
        if binding.fields is not None:
            registers = []
            for index in range(type_name.length):
                cell = binding.fields.get(self._array_cell_name(index))
                if cell is None:
                    raise LoweringError(f"array cell {index} is unavailable", location)
                registers.extend(
                    self._flatten_value_registers(
                        cell,
                        type_name.element_type,
                        location,
                    )
                )
            return tuple(registers)
        raise LoweringError("array cells are unavailable", location)

    def _lower_array_registers(
        self,
        expression: ast.Expression,
        type_name: ast.ArrayType,
    ) -> tuple[int, ...]:
        if isinstance(expression, ast.ArrayLiteral):
            registers: list[int] = []
            for element in expression.elements:
                registers.extend(
                    self._lower_value_registers(
                        element,
                        type_name.element_type,
                    )
                )
            return tuple(registers)
        if isinstance(expression, ast.Identifier):
            binding = self._lookup_variable(expression.name, expression.location)
            return self._flatten_array_registers(binding, type_name, expression.location)
        if isinstance(expression, ast.CallExpression):
            return self._lower_call_result_registers(expression, type_name)
        if isinstance(expression, ast.FieldAccessExpression):
            target_type = self.semantic_model.declared_type_of(expression.target)
            if (
                isinstance(target_type, ast.NominalType)
                and self.semantic_model.is_record_type(target_type)
            ):
                record = self.semantic_model.record(target_type.name)
                target = self._lower_record_binding_from_expression(
                    expression.target,
                    record,
                    expression.target.location,
                )
                assert target.fields is not None
                field = target.fields.get(expression.field_name)
                if field is not None:
                    return self._flatten_array_registers(
                        field,
                        type_name,
                        expression.location,
                    )
        raise LoweringError("array value requires a binding, field, or call", expression.location)

    def _lower_value_registers(
        self,
        expression: ast.Expression,
        type_name: ast.DeclaredType,
    ) -> tuple[int, ...]:
        if isinstance(type_name, ast.TypeName):
            return (self._lower_expression(expression),)
        if isinstance(type_name, ast.ArrayType):
            return self._lower_array_registers(expression, type_name)
        if isinstance(type_name, ast.NominalType) and self.semantic_model.is_record_type(type_name):
            record = self.semantic_model.record(type_name.name)
            fields = self._lower_record_fields_from_expression(
                expression, record, expression.location
            )
            return self._flatten_record_registers(record.name, fields, expression.location)
        if isinstance(type_name, ast.NominalType) and self.semantic_model.is_enum_type(type_name):
            binding = self._lower_enum_binding_from_expression(
                expression, type_name.name, expression.location
            )
            return self._flatten_enum_registers(type_name.name, binding, expression.location)
        raise LoweringError("unsupported array element type", expression.location)

    def _store_array_registers(
        self,
        memory: int,
        registers: tuple[int, ...],
        location: SourceLocation,
        *,
        initialization: bool,
    ) -> None:
        for index, register in enumerate(registers):
            index_register = self._emit_constant(index, ast.TypeName.TRYTE, location)
            self._emit(
                IRInstruction(
                    IROpcode.STORE,
                    operands=(index_register, register),
                    memory=memory,
                    initialization=initialization,
                    location=location,
                )
            )

    def _lower_call_result_registers(
        self,
        expression: ast.CallExpression,
        type_name: ast.DeclaredType,
    ) -> tuple[int, ...]:
        arguments = self._lower_call_arguments(expression)
        results = self._allocate_result_cells(type_name, expression.location)
        self._emit(
            IRInstruction(
                IROpcode.CALL,
                results=results,
                operands=arguments,
                callee=expression.function_name,
                location=expression.location,
            )
        )
        return results

    def _record_binding_from_registers(
        self,
        record,
        registers: tuple[int, ...],
        location: SourceLocation,
    ) -> _LoweredBinding:
        leaves = self.semantic_model.record_leaves(record.name)
        if len(registers) != len(leaves):
            raise LoweringError(
                f"record '{record.name}' expected {len(leaves)} cells; got {len(registers)}",
                location,
            )
        fields: dict[str, _LoweredBinding] = {}
        for leaf, register in zip(leaves, registers, strict=True):
            self._set_leaf_binding(fields, record, leaf.path, register)
        return _LoweredBinding(
            ast.NominalType(record.name, location),
            mutable=False,
            fields=fields,
        )

    def _flatten_record_registers(
        self,
        record_name: str,
        fields: dict[str, _LoweredBinding],
        location: SourceLocation,
    ) -> tuple[int, ...]:
        registers: list[int] = []
        for leaf in self.semantic_model.record_leaves(record_name):
            binding = self._field_binding_at_path(fields, leaf.path, location)
            if binding.register is None:
                raise LoweringError(
                    (
                        "record argument field '"
                        + ".".join(leaf.path)
                        + "' is unavailable"
                    ),
                    location,
                )
            registers.append(binding.register)
        return tuple(registers)

    def _lookup_variable(
        self,
        name: str,
        location: SourceLocation,
    ) -> _LoweredBinding:
        binding = self._lookup_variable_or_none(name)
        if binding is not None:
            return binding
        raise LoweringError(f"unknown variable '{name}'", location)

    def _lookup_variable_or_none(self, name: str) -> _LoweredBinding | None:
        for scope in reversed(self.variable_scopes):
            if name in scope:
                return scope[name]
        return None

    def _lower_record_fields_from_expression(
        self,
        expression: ast.Initializer,
        record,
        location: SourceLocation,
    ) -> dict[str, _LoweredBinding]:
        return self._lower_record_binding_from_expression(
            expression,
            record,
            location,
        ).fields or {}

    def _lower_record_binding_from_expression(
        self,
        expression: ast.Initializer,
        record,
        location: SourceLocation,
    ) -> _LoweredBinding:
        if isinstance(expression, ast.ArrayLiteral):
            raise LoweringError(
                "record value cannot be initialized from an array literal",
                expression.location,
            )
        if isinstance(expression, ast.RecordExpression):
            values = {field.name: field.expression for field in expression.fields}
            fields: dict[str, _LoweredBinding] = {}
            for field in record.fields:
                value = values[field.name]
                if isinstance(field.type_name, ast.ArrayType):
                    fields[field.name] = self._array_binding_from_registers(
                        field.type_name,
                        self._lower_array_registers(value, field.type_name),
                        value.location,
                    )
                    continue
                if (
                    isinstance(field.type_name, ast.NominalType)
                    and self.semantic_model.is_record_type(field.type_name)
                ):
                    nested = self.semantic_model.record(field.type_name.name)
                    fields[field.name] = self._lower_record_binding_from_expression(
                        value,
                        nested,
                        value.location,
                    )
                    continue
                if (
                    isinstance(field.type_name, ast.NominalType)
                    and self.semantic_model.is_enum_type(field.type_name)
                    and self.semantic_model.enum_cell_count(field.type_name.name) > 1
                ):
                    fields[field.name] = self._lower_enum_binding_from_expression(
                        value,
                        field.type_name.name,
                        value.location,
                    )
                    continue
                fields[field.name] = _LoweredBinding(
                    field.type_name,
                    mutable=False,
                    register=self._lower_expression(value),
                )
            return _LoweredBinding(
                ast.NominalType(record.name, location),
                mutable=False,
                fields=fields,
            )
        if isinstance(expression, ast.Identifier):
            binding = self._lookup_variable(expression.name, expression.location)
            if binding.fields is not None:
                return _LoweredBinding(
                    ast.NominalType(record.name, location),
                    mutable=False,
                    fields={
                        field.name: binding.fields[field.name]
                        for field in record.fields
                    },
                )
        if isinstance(expression, ast.FieldAccessExpression):
            target_type = self.semantic_model.declared_type_of(expression.target)
            if (
                isinstance(target_type, ast.NominalType)
                and self.semantic_model.is_record_type(target_type)
            ):
                target_record = self.semantic_model.record(target_type.name)
                target = self._lower_record_binding_from_expression(
                    expression.target,
                    target_record,
                    expression.target.location,
                )
                assert target.fields is not None
                field = target.fields.get(expression.field_name)
                if field is not None and field.fields is not None:
                    return field
        if isinstance(expression, ast.CallExpression):
            return self._record_binding_from_registers(
                record,
                self._lower_call_result_registers(
                    expression,
                    ast.NominalType(record.name, location),
                ),
                location,
            )
        if self.semantic_model.record_leaf_count(record.name) == 1:
            register = self._lower_expression(expression)
            return _LoweredBinding(
                ast.NominalType(record.name, location),
                mutable=False,
                fields=self._fields_from_single_leaf_register(record, register),
            )
        raise LoweringError(
            "multi-field record value requires an explicit record literal or binding",
            location,
        )

    def _lower_enum_binding_from_expression(
        self,
        expression: ast.Initializer,
        enum_name: str,
        location: SourceLocation,
    ) -> _LoweredBinding:
        layout = self.semantic_model.enum_layout(enum_name)
        if isinstance(expression, ast.ArrayLiteral):
            raise LoweringError(
                "enum value cannot be initialized from an array literal",
                expression.location,
            )
        if isinstance(expression, ast.RecordExpression):
            constructor = self._enum_constructor(expression)
            if constructor is None:
                raise LoweringError(
                    f"enum '{enum_name}' requires an enum variant constructor",
                    expression.location,
                )
            constructor_enum, variant = constructor
            if constructor_enum.name != enum_name:
                raise LoweringError(
                    f"enum constructor has type {constructor_enum.name}; expected {enum_name}",
                    expression.location,
                )
            values = {field.name: field.expression for field in expression.fields}
            registers: list[int] = [
                self._emit_constant(
                    constructor_enum.discriminant(variant.name),
                    ast.TypeName.TRYTE,
                    expression.location,
                )
            ]
            for field in variant.payload_fields:
                registers.extend(
                    self._lower_payload_field_registers(
                        values[field.name],
                        field.type_name,
                        values[field.name].location,
                    )
                )
            while len(registers) < layout.cell_count:
                registers.append(
                    self._zero_value(
                        layout.slot_types[len(registers)],
                        expression.location,
                    )
                )
            return self._enum_binding_from_registers(enum_name, tuple(registers), location)
        if isinstance(expression, ast.FieldAccessExpression):
            constructor = self._enum_variant_access(expression)
            if constructor is not None:
                constructor_enum, variant = constructor
                if constructor_enum.name != enum_name:
                    raise LoweringError(
                        f"enum constructor has type {constructor_enum.name}; expected {enum_name}",
                        expression.location,
                    )
                registers = [
                    self._emit_constant(
                        constructor_enum.discriminant(variant.name),
                        ast.TypeName.TRYTE,
                        expression.location,
                    )
                ]
                while len(registers) < layout.cell_count:
                    registers.append(
                        self._zero_value(
                            layout.slot_types[len(registers)],
                            expression.location,
                        )
                    )
                return self._enum_binding_from_registers(enum_name, tuple(registers), location)
        if isinstance(expression, ast.Identifier):
            binding = self._lookup_variable(expression.name, expression.location)
            if binding.fields is not None:
                return _LoweredBinding(
                    ast.NominalType(enum_name, location),
                    mutable=False,
                    fields={
                        self._enum_cell_name(index): binding.fields[
                            self._enum_cell_name(index)
                        ]
                        for index in range(layout.cell_count)
                    },
                )
        if isinstance(expression, ast.CallExpression):
            return self._enum_binding_from_registers(
                enum_name,
                self._lower_call_result_registers(
                    expression,
                    ast.NominalType(enum_name, location),
                ),
                location,
            )
        if layout.cell_count == 1:
            register = self._lower_expression(expression)
            return self._enum_binding_from_registers(enum_name, (register,), location)
        raise LoweringError(
            "multi-cell enum value requires an explicit enum literal or binding",
            location,
        )

    def _lower_payload_field_registers(
        self,
        expression: ast.Expression,
        type_name: ast.DeclaredType,
        location: SourceLocation,
    ) -> tuple[int, ...]:
        if isinstance(type_name, ast.TypeName):
            return (self._lower_expression(expression),)
        if isinstance(type_name, ast.ArrayType):
            return self._lower_array_registers(expression, type_name)
        if (
            isinstance(type_name, ast.NominalType)
            and self.semantic_model.is_record_type(type_name)
        ):
            record = self.semantic_model.record(type_name.name)
            fields = self._lower_record_fields_from_expression(
                expression,
                record,
                location,
            )
            return self._flatten_record_registers(record.name, fields, location)
        if (
            isinstance(type_name, ast.NominalType)
            and self.semantic_model.is_enum_type(type_name)
        ):
            binding = self._lower_enum_binding_from_expression(
                expression,
                type_name.name,
                location,
            )
            return self._flatten_enum_registers(type_name.name, binding, location)
        raise LoweringError("unsupported enum payload field type", location)

    def _enum_binding_from_registers(
        self,
        enum_name: str,
        registers: tuple[int, ...],
        location: SourceLocation,
    ) -> _LoweredBinding:
        layout = self.semantic_model.enum_layout(enum_name)
        if len(registers) != layout.cell_count:
            raise LoweringError(
                f"enum '{enum_name}' expected {layout.cell_count} cells; got {len(registers)}",
                location,
            )
        fields: dict[str, _LoweredBinding] = {}
        for index, register in enumerate(registers):
            self._set_enum_cell_binding(fields, index, layout.slot_types[index], register)
        return _LoweredBinding(
            ast.NominalType(enum_name, location),
            mutable=False,
            fields=fields,
        )

    def _flatten_enum_registers(
        self,
        enum_name: str,
        binding: _LoweredBinding,
        location: SourceLocation,
    ) -> tuple[int, ...]:
        layout = self.semantic_model.enum_layout(enum_name)
        if binding.fields is None:
            if layout.cell_count == 1 and binding.register is not None:
                return (binding.register,)
            raise LoweringError(f"enum '{enum_name}' cells are unavailable", location)
        registers: list[int] = []
        for index in range(layout.cell_count):
            cell = binding.fields.get(self._enum_cell_name(index))
            if cell is None or cell.register is None:
                raise LoweringError(
                    f"enum '{enum_name}' cell {index} is unavailable",
                    location,
                )
            registers.append(cell.register)
        return tuple(registers)

    def _enum_constructor(
        self,
        expression: ast.RecordExpression,
    ) -> tuple | None:
        if "." not in expression.type_name:
            return None
        enum_name, variant_name = expression.type_name.rsplit(".", 1)
        enum = self.semantic_model.enums.get(enum_name)
        if enum is None:
            return None
        variant = enum.variant(variant_name)
        if variant is None:
            raise LoweringError(
                f"enum '{enum.name}' has no variant '{variant_name}'",
                expression.location,
            )
        return enum, variant

    def _enum_variant_access(
        self,
        expression: ast.FieldAccessExpression,
    ) -> tuple | None:
        if not isinstance(expression.target, ast.Identifier):
            return None
        enum = self.semantic_model.enums.get(expression.target.name)
        if enum is None:
            return None
        variant = enum.variant(expression.field_name)
        if variant is None:
            raise LoweringError(
                f"enum '{enum.name}' has no variant '{expression.field_name}'",
                expression.location,
            )
        return enum, variant

    def _lower_return_expression(self, expression: ast.Expression) -> tuple[int, ...]:
        if isinstance(self.function.return_type, ast.ArrayType):
            return self._lower_array_registers(expression, self.function.return_type)
        if (
            isinstance(self.function.return_type, ast.NominalType)
            and self.semantic_model.is_record_type(self.function.return_type)
        ):
            record = self.semantic_model.record(self.function.return_type.name)
            fields = self._lower_record_fields_from_expression(
                expression,
                record,
                expression.location,
            )
            registers = self._flatten_record_registers(
                record.name,
                fields,
                expression.location,
            )
            if not registers:
                raise LoweringError("record return is missing cells", expression.location)
            return registers
        if (
            isinstance(self.function.return_type, ast.NominalType)
            and self.semantic_model.is_enum_type(self.function.return_type)
        ):
            binding = self._lower_enum_binding_from_expression(
                expression,
                self.function.return_type.name,
                expression.location,
            )
            return self._flatten_enum_registers(
                self.function.return_type.name,
                binding,
                expression.location,
            )
        return (self._lower_expression(expression),)

    def _lower_declaration(self, declaration: ast.VariableDeclaration) -> None:
        if isinstance(declaration.type_name, (ast.ReferenceType, ast.SliceType)):
            register = self._allocate_reference(declaration.type_name, declaration.location)
            initializer = declaration.initializer
            if isinstance(initializer, ast.Identifier):
                binding = self._lookup_variable(initializer.name, initializer.location)
                if isinstance(binding.type_name, (ast.ReferenceType, ast.SliceType)):
                    self._emit(IRInstruction(IROpcode.MOVE, result=register, operands=(binding.register,), location=declaration.location))
                    self.variable_scopes[-1][declaration.name] = _LoweredBinding(
                        declaration.type_name, declaration.mutable, register=register
                    )
                    return
                if binding.register is not None:
                    instruction = IRInstruction(
                        IROpcode.ADDRESS_OF, result=register,
                        operands=(binding.register,),
                        reference_target=TYPE_MAP[self._storage_type(declaration.type_name.target if isinstance(declaration.type_name, ast.ReferenceType) else declaration.type_name.element_type, declaration.location)],
                        reference_mutable=declaration.type_name.mutable,
                        reference_is_slice=isinstance(declaration.type_name, ast.SliceType),
                        location=declaration.location,
                    )
                else:
                    instruction = IRInstruction(
                        IROpcode.ADDRESS_OF, result=register, memory=binding.memory,
                        reference_target=TYPE_MAP[self._storage_type(declaration.type_name.target if isinstance(declaration.type_name, ast.ReferenceType) else declaration.type_name.element_type, declaration.location)],
                        reference_mutable=declaration.type_name.mutable,
                        reference_is_slice=isinstance(declaration.type_name, ast.SliceType),
                        location=declaration.location,
                    )
                self._emit(instruction)
            else:
                source = self._lower_expression(initializer)
                self._emit(IRInstruction(IROpcode.MOVE, result=register, operands=(source,), location=declaration.location))
            self.variable_scopes[-1][declaration.name] = _LoweredBinding(
                declaration.type_name, declaration.mutable, register=register
            )
            return
        if isinstance(declaration.type_name, ast.ArrayType):
            if isinstance(declaration.type_name.element_type, ast.TypeName):
                memory = self._allocate_memory(
                    declaration.type_name.element_type,
                    declaration.type_name.length,
                    declaration.mutable,
                    declaration.location,
                )
                registers = self._lower_array_registers(
                    declaration.initializer,
                    declaration.type_name,
                )
                self._store_array_registers(
                    memory,
                    registers,
                    declaration.location,
                    initialization=True,
                )
                binding = _LoweredBinding(
                    declaration.type_name,
                    declaration.mutable,
                    memory=memory,
                )
            else:
                binding = self._array_binding_from_registers(
                    declaration.type_name,
                    self._lower_array_registers(
                        declaration.initializer,
                        declaration.type_name,
                    ),
                    declaration.location,
                )
            self.variable_scopes[-1][declaration.name] = binding
            return

        if (
            isinstance(declaration.type_name, ast.NominalType)
            and self.semantic_model.is_record_type(declaration.type_name)
        ):
            record = self.semantic_model.record(declaration.type_name.name)
            lowered_fields = self._lower_record_fields_from_expression(
                declaration.initializer,
                record,
                declaration.location,
            )
            self.variable_scopes[-1][declaration.name] = _LoweredBinding(
                declaration.type_name,
                mutable=declaration.mutable,
                fields=lowered_fields,
            )
            return

        if (
            isinstance(declaration.type_name, ast.NominalType)
            and self.semantic_model.is_enum_type(declaration.type_name)
            and self.semantic_model.enum_cell_count(declaration.type_name.name) > 1
        ):
            if declaration.mutable:
                raise LoweringError(
                    "mutable enum payload bindings are not supported yet",
                    declaration.location,
                )
            binding = self._lower_enum_binding_from_expression(
                declaration.initializer,
                declaration.type_name.name,
                declaration.location,
            )
            self.variable_scopes[-1][declaration.name] = binding
            return

        if isinstance(declaration.initializer, ast.ArrayLiteral):
            raise LoweringError(
                "scalar declaration received an array initializer",
                declaration.initializer.location,
            )
        storage_type = self._storage_type(declaration.type_name, declaration.location)
        initializer = self._lower_expression(declaration.initializer)
        if storage_type in _DYNAMIC_TYPES:
            variable = self._allocate(storage_type, declaration.location)
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
                declaration.mutable,
                register=variable,
            )
            return
        if declaration.mutable:
            memory = self._allocate_memory(
                storage_type,
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

        variable = self._allocate(storage_type, declaration.location)
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
        if isinstance(statement.target, ast.FieldTarget):
            container = self._lower_field_container(statement.target.target)
            if container.fields is None:
                raise LoweringError(
                    "owned field replacement has no aggregate storage",
                    statement.target.location,
                )
            field = container.fields.get(statement.target.field_name)
            if field is None:
                raise LoweringError(
                    f"record field '{statement.target.field_name}' is unavailable",
                    statement.target.location,
                )
            container_type = container.type_name
            if not (
                isinstance(container_type, ast.NominalType)
                and self.semantic_model.is_record_type(container_type)
            ):
                raise LoweringError(
                    "owned field replacement requires a record container",
                    statement.target.location,
                )
            record_field = self.semantic_model.record(container_type.name).field(
                statement.target.field_name
            )
            if record_field is None:
                raise LoweringError(
                    f"record field '{statement.target.field_name}' is unavailable",
                    statement.target.location,
                )
            field_type = record_field.type_name
            if isinstance(statement.value, ast.ArrayLiteral):
                if not isinstance(field_type, ast.ArrayType):
                    raise LoweringError(
                        "field replacement received an array initializer",
                        statement.value.location,
                    )
                registers = self._lower_array_registers(statement.value, field_type)
            else:
                registers = self._lower_value_registers(statement.value, field_type)
            container.fields[statement.target.field_name] = self._binding_from_registers(
                field_type,
                registers,
                statement.target.location,
            )
            return
        if isinstance(statement.target, ast.DereferenceTarget):
            reference = self._lower_expression(statement.target.reference)
            value = self._lower_expression(statement.value)
            reference_type = self.semantic_model.declared_type_of(statement.target.reference)
            self._emit(IRInstruction(
                IROpcode.REFERENCE_STORE, operands=(reference, value),
                reference_target=TYPE_MAP[self._storage_type(reference_type.target, statement.location)],
                reference_mutable=reference_type.mutable,
                location=statement.location,
            ))
            return
        if isinstance(statement.target, ast.VariableTarget):
            binding = self._lookup_variable(
                statement.target.name,
                statement.target.location,
            )
            if isinstance(binding.type_name, ast.ArrayType):
                registers = self._lower_array_registers(
                    statement.value,
                    binding.type_name,
                )
                if binding.memory is not None:
                    self._store_array_registers(
                        binding.memory,
                        registers,
                        statement.location,
                        initialization=False,
                    )
                else:
                    self.variable_scopes[-1][statement.target.name] = (
                        self._array_binding_from_registers(
                            binding.type_name,
                            registers,
                            statement.location,
                        )
                    )
                return
            if isinstance(statement.value, ast.ArrayLiteral):
                raise LoweringError(
                    "scalar assignment received an array literal",
                    statement.value.location,
                )
            value = self._lower_expression(statement.value)
            if (
                isinstance(binding.type_name, ast.TypeName)
                and binding.type_name in _DYNAMIC_TYPES
            ):
                if binding.register is None:
                    raise LoweringError(
                        "dynamic binding has no stable storage",
                        statement.target.location,
                    )
                reference_type = ast.ReferenceType(
                    binding.type_name,
                    True,
                    statement.target.location,
                )
                reference = self._allocate_reference(
                    reference_type,
                    statement.target.location,
                )
                self._emit(
                    IRInstruction(
                        IROpcode.ADDRESS_OF,
                        result=reference,
                        operands=(binding.register,),
                        reference_target=TYPE_MAP[binding.type_name],
                        reference_mutable=True,
                        location=statement.target.location,
                    )
                )
                self._emit(
                    IRInstruction(
                        IROpcode.REFERENCE_STORE,
                        operands=(reference, value),
                        reference_target=TYPE_MAP[binding.type_name],
                        reference_mutable=True,
                        location=statement.location,
                    )
                )
                return
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
        if isinstance(binding.type_name, ast.SliceType):
            if isinstance(statement.value, ast.ArrayLiteral):
                raise LoweringError(
                    "slice element assignment received an array literal",
                    statement.value.location,
                )
            index = self._lower_expression(statement.target.index)
            value = self._lower_expression(statement.value)
            if binding.slice_length_register is None:
                raise LoweringError("slice has no runtime length", statement.location)
            self._emit(
                IRInstruction(
                    IROpcode.SLICE_STORE,
                    operands=(binding.register, binding.slice_length_register, index, value),
                    reference_target=TYPE_MAP[binding.type_name.element_type],
                    reference_mutable=True,
                    location=statement.location,
                )
            )
            return
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
        value: int | float,
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
        selector_type = self.semantic_model.declared_type_of(statement.expression)
        if self.semantic_model.is_enum_type(selector_type):
            self._lower_enum_switch(statement)
            return

        cond_val = self.semantic_model.constant_value_of(statement.expression)
        if cond_val is not None:
            explicit_cases = {c.label: c for c in statement.cases if c.label is not None}
            fallback_case = next((c for c in statement.cases if c.label is None), None)
            target_case = explicit_cases.get(cond_val, fallback_case)
            if target_case is not None:
                self._lower_block(target_case.body, create_scope=True)
                return
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

    def _lower_enum_selector_registers(
        self,
        expression: ast.Expression,
        location: SourceLocation,
    ) -> tuple[int, ...]:
        selector_type = self.semantic_model.declared_type_of(expression)
        if not (
            isinstance(selector_type, ast.NominalType)
            and self.semantic_model.is_enum_type(selector_type)
        ):
            raise LoweringError("enum selector has unsupported type", location)
        if self.semantic_model.enum_cell_count(selector_type.name) == 1:
            return (self._lower_expression(expression),)
        binding = self._lower_enum_binding_from_expression(
            expression,
            selector_type.name,
            location,
        )
        return self._flatten_enum_registers(selector_type.name, binding, location)

    def _lower_enum_switch(self, statement: ast.SwitchStatement) -> None:
        explicit_entries = self._enum_case_entries(statement.cases)
        explicit_cases = dict(explicit_entries)
        fallback_case = next((c for c in statement.cases if c.label is None), None)
        cond_val = self.semantic_model.constant_value_of(statement.expression)
        if cond_val is not None:
            target_case = explicit_cases.get(cond_val, fallback_case)
            if target_case is not None:
                self._lower_block(target_case.body, create_scope=True)
                return

        selector_registers = self._lower_enum_selector_registers(
            statement.expression,
            statement.location,
        )
        selector_reg = selector_registers[0]
        default_case = fallback_case or explicit_entries[-1][1]
        test_entries = explicit_entries if fallback_case is not None else explicit_entries[:-1]
        open_blocks: list[tuple[_MutableBlock, SourceLocation]] = []

        for discriminant, case in test_entries:
            less_block = self._fresh_block("enum_match_less", case.location)
            case_block = self._fresh_block("enum_match_case", case.location)
            greater_block = self._fresh_block("enum_match_greater", case.location)
            next_block = self._fresh_block("enum_match_next", statement.location)
            discriminant_reg = self._emit_constant(
                discriminant,
                ast.TypeName.TRYTE,
                case.location,
            )
            compare_reg = self._allocate(ast.TypeName.TRIT, case.location)
            self._emit(
                IRInstruction(
                    IROpcode.COMPARE,
                    result=compare_reg,
                    operands=(selector_reg, discriminant_reg),
                    location=case.location,
                )
            )
            self._emit(
                IRInstruction(
                    IROpcode.BRANCH3,
                    operands=(compare_reg,),
                    targets=(less_block.name, case_block.name, greater_block.name),
                    location=case.location,
                )
            )

            for branch_block in (less_block, greater_block):
                self.current = branch_block
                self._emit(
                    IRInstruction(
                        IROpcode.JUMP,
                        targets=(next_block.name,),
                        location=case.location,
                    )
                )

            self.current = case_block
            self._lower_enum_case_block(
                case,
                self.semantic_model.declared_type_of(statement.expression),
                selector_registers,
            )
            if self.current is not None:
                open_blocks.append((self.current, case.location))
            self.current = next_block

        self._lower_enum_case_block(
            default_case,
            self.semantic_model.declared_type_of(statement.expression),
            selector_registers,
        )
        if self.current is not None:
            open_blocks.append((self.current, default_case.location))

        if not open_blocks:
            self.current = None
            return
        continuation = self._fresh_block(
            "enum_match_continue",
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

    def _lower_enum_case_block(
        self,
        case: ast.TernaryCase,
        selector_type: ast.DeclaredType,
        selector_registers: tuple[int, ...],
    ) -> None:
        self.variable_scopes.append({})
        try:
            self._bind_enum_payload_case(case.label, selector_type, selector_registers)
            self._lower_block(case.body, create_scope=False)
        finally:
            self.variable_scopes.pop()

    def _bind_enum_payload_case(
        self,
        label: ast.MatchCaseLabel,
        selector_type: ast.DeclaredType,
        selector_registers: tuple[int, ...],
    ) -> None:
        if not isinstance(label, ast.MatchPayloadLabel):
            return
        assert isinstance(selector_type, ast.NominalType)
        enum = self.semantic_model.enum(selector_type.name)
        discriminant = self._match_label_discriminant(label)
        variant = enum.variants[discriminant]
        offset = 1
        fields_by_name = {field.name: field for field in variant.payload_fields}
        for binding_name in label.bindings:
            field = fields_by_name[binding_name]
            registers = self._payload_field_register_slice(
                field.type_name,
                selector_registers,
                offset,
                label.location,
            )
            self.variable_scopes[-1][binding_name] = self._binding_from_payload_registers(
                field.type_name,
                registers,
                label.location,
            )
            offset += len(registers)

    def _payload_field_register_slice(
        self,
        type_name: ast.DeclaredType,
        selector_registers: tuple[int, ...],
        offset: int,
        location: SourceLocation,
    ) -> tuple[int, ...]:
        width = 1
        if isinstance(type_name, ast.ArrayType):
            width = type_name.length
        elif (
            isinstance(type_name, ast.NominalType)
            and self.semantic_model.is_record_type(type_name)
        ):
            width = self.semantic_model.record_leaf_count(type_name.name)
        elif (
            isinstance(type_name, ast.NominalType)
            and self.semantic_model.is_enum_type(type_name)
        ):
            width = self.semantic_model.enum_cell_count(type_name.name)
        return selector_registers[offset : offset + width]

    def _binding_from_payload_registers(
        self,
        type_name: ast.DeclaredType,
        registers: tuple[int, ...],
        location: SourceLocation,
    ) -> _LoweredBinding:
        if isinstance(type_name, ast.TypeName):
            return _LoweredBinding(
                type_name,
                mutable=False,
                register=registers[0],
            )
        if isinstance(type_name, ast.ArrayType):
            return self._array_binding_from_registers(
                type_name,
                registers,
                location,
            )
        if (
            isinstance(type_name, ast.NominalType)
            and self.semantic_model.is_record_type(type_name)
        ):
            record = self.semantic_model.record(type_name.name)
            fields: dict[str, _LoweredBinding] = {}
            for leaf, register in zip(
                self.semantic_model.record_leaves(record.name),
                registers,
                strict=True,
            ):
                self._set_leaf_binding(fields, record, leaf.path, register)
            return _LoweredBinding(type_name, mutable=False, fields=fields)
        if (
            isinstance(type_name, ast.NominalType)
            and self.semantic_model.is_enum_type(type_name)
        ):
            return self._enum_binding_from_registers(type_name.name, registers, location)
        raise LoweringError("unsupported enum payload binding type", location)

    def _lower_while(self, statement: ast.WhileStatement) -> None:
        cond_val = self.semantic_model.constant_value_of(statement.condition)
        if cond_val in (0, 1):
            return
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
        simplified = self.semantic_model.simplified_expression_of(expression)
        if simplified is not None:
            return self._lower_expression(simplified)
        declared_type = self.semantic_model.declared_type_of(expression)
        if isinstance(declared_type, (ast.ReferenceType, ast.SliceType)):
            if isinstance(expression, ast.Identifier):
                return self._lookup_variable(expression.name, expression.location).register  # type: ignore[return-value]
            if isinstance(expression, ast.AddressOfExpression):
                target = expression.operand
                if isinstance(target, ast.DereferenceExpression):
                    source = self._lower_expression(target.operand)
                    result = self._allocate_reference(declared_type, expression.location)
                    self._emit(IRInstruction(
                        IROpcode.MOVE,
                        result=result,
                        operands=(source,),
                        location=expression.location,
                    ))
                    return result
                if isinstance(target, ast.IndexExpression):
                    if not isinstance(target.target, ast.Identifier):
                        raise LoweringError("unsupported projected address-of target", expression.location)
                    binding = self._lookup_variable(target.target.name, target.target.location)
                    if binding.memory is None:
                        raise LoweringError("array element has no stable memory storage", expression.location)
                    index = self._lower_expression(target.index)
                    result = self._allocate_reference(declared_type, expression.location)
                    self._emit(IRInstruction(
                        IROpcode.ADDRESS_OF,
                        result=result,
                        operands=(index,),
                        memory=binding.memory,
                        reference_target=TYPE_MAP[self._storage_type(declared_type.target if isinstance(declared_type, ast.ReferenceType) else declared_type.element_type, expression.location)],
                        reference_mutable=declared_type.mutable,
                        reference_is_slice=isinstance(declared_type, ast.SliceType),
                        location=expression.location,
                    ))
                    return result
                if isinstance(target, ast.FieldAccessExpression):
                    source = self._lower_field_access(target)
                    result = self._allocate_reference(declared_type, expression.location)
                    self._emit(IRInstruction(
                        IROpcode.ADDRESS_OF,
                        result=result,
                        operands=(source,),
                        reference_target=TYPE_MAP[self._storage_type(declared_type.target if isinstance(declared_type, ast.ReferenceType) else declared_type.element_type, expression.location)],
                        reference_mutable=declared_type.mutable,
                        reference_is_slice=isinstance(declared_type, ast.SliceType),
                        location=expression.location,
                    ))
                    return result
                if not isinstance(target, ast.Identifier):
                    raise LoweringError("unsupported address-of target", expression.location)
                binding = self._lookup_variable(target.name, target.location)
                result = self._allocate_reference(declared_type, expression.location)
                self._emit(IRInstruction(
                    IROpcode.ADDRESS_OF, result=result,
                    operands=() if binding.register is None else (binding.register,),
                    memory=binding.memory,
                    reference_target=TYPE_MAP[self._storage_type(declared_type.target if isinstance(declared_type, ast.ReferenceType) else declared_type.element_type, expression.location)],
                    reference_mutable=declared_type.mutable,
                    reference_is_slice=isinstance(declared_type, ast.SliceType),
                    location=expression.location,
                ))
                return result
        expression_type = self._storage_type(declared_type, expression.location)
        if expression_type in (ast.TypeName.TRIT, ast.TypeName.TRYTE, ast.TypeName.I64, ast.TypeName.F64):
            constant = self.semantic_model.constant_value_of(expression)
            if constant is not None:
                return self._emit_constant(
                    constant,
                    expression_type,
                    expression.location,
                )
        if isinstance(expression, ast.IntegerLiteral):
            return self._emit_constant(
                expression.value,
                expression_type,
                expression.location,
            )
        if isinstance(expression, ast.FloatLiteral):
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
            text = self.semantic_model.static_text_of(expression)
            assert text is not None
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
            storage_type = self._storage_type(binding.type_name, expression.location)
            index = self._emit_constant(
                0,
                ast.TypeName.TRYTE,
                expression.location,
            )
            result = self._allocate(storage_type, expression.location)
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
        if isinstance(expression, ast.DereferenceExpression):
            reference = self._lower_expression(expression.operand)
            result = self._allocate(self._storage_type(declared_type, expression.location), expression.location)
            self._emit(IRInstruction(
                IROpcode.REFERENCE_LOAD, result=result, operands=(reference,),
                reference_target=TYPE_MAP[self._storage_type(declared_type, expression.location)],
                location=expression.location,
            ))
            return result
        if isinstance(expression, ast.IndexExpression):
            if expression_type is ast.TypeName.STRING:
                text = self.semantic_model.static_text_of(expression)
                assert text is not None
                try:
                    static_string = self.static_string_ids[text]
                except KeyError as error:
                    raise LoweringError(
                        "constant static text index expression is missing from static string table",
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
            array_type = self.semantic_model.declared_type_of(expression.target)
            if isinstance(array_type, ast.SliceType):
                if not isinstance(expression.target, ast.Identifier):
                    raise LoweringError("slice target must be a named slice", expression.location)
                binding = self._lookup_variable(expression.target.name, expression.target.location)
                if binding.register is None:
                    raise LoweringError("slice has no register storage", expression.location)
                index = self._lower_expression(expression.index)
                if binding.slice_length_register is None:
                    raise LoweringError("slice has no runtime length", expression.location)
                result = self._allocate(array_type.element_type, expression.location)
                self._emit(IRInstruction(
                    IROpcode.SLICE_LOAD,
                    result=result,
                    operands=(binding.register, binding.slice_length_register, index),
                    reference_target=TYPE_MAP[array_type.element_type],
                    location=expression.location,
                ))
                return result
            assert isinstance(array_type, ast.ArrayType)
            assert isinstance(array_type.element_type, ast.TypeName)
            memory: int
            if isinstance(expression.target, ast.Identifier):
                binding = self._lookup_variable(
                    expression.target.name,
                    expression.location,
                )
                if binding.memory is not None:
                    memory = binding.memory
                else:
                    memory = self._allocate_memory(
                        array_type.element_type,
                        array_type.length,
                        False,
                        expression.location,
                    )
                    self._store_array_registers(
                        memory,
                        self._flatten_array_registers(
                            binding,
                            array_type,
                            expression.location,
                        ),
                        expression.location,
                        initialization=True,
                    )
            else:
                registers = self._lower_array_registers(
                    expression.target,
                    array_type,
                )
                memory = self._allocate_memory(
                    array_type.element_type,
                    array_type.length,
                    False,
                    expression.location,
                )
                self._store_array_registers(
                    memory,
                    registers,
                    expression.location,
                    initialization=True,
                )
            index = self._lower_expression(expression.index)
            result = self._allocate(
                array_type.element_type,
                expression.location,
            )
            self._emit(
                IRInstruction(
                    IROpcode.LOAD,
                    result=result,
                    operands=(index,),
                    memory=memory,
                    location=expression.location,
                )
            )
            return result
        if isinstance(expression, ast.SliceExpression):
            text = self.semantic_model.static_text_of(expression)
            assert text is not None
            try:
                static_string = self.static_string_ids[text]
            except KeyError as error:
                raise LoweringError(
                    "constant static text slice expression is missing from static string table",
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
        if isinstance(expression, ast.CallExpression):
            constant = self.semantic_model.constant_value_of(expression)
            if constant is not None:
                return self._emit_constant(
                    constant,
                    expression_type,
                    expression.location,
                )
            text = self.semantic_model.static_text_of(expression)
            if text is not None:
                try:
                    static_string = self.static_string_ids[text]
                except KeyError as error:
                    raise LoweringError(
                        "constant static text call expression is missing from static string table",
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
            if expression.simple_function_name in {"to_i64", "to_f64", "to_tryte"}:
                if len(expression.arguments) != 1:
                    raise LoweringError("numeric conversion requires one argument", expression.location)
                source = self._lower_expression(expression.arguments[0].expression)
                result = self._allocate(expression_type, expression.location)
                self._emit(
                    IRInstruction(
                        IROpcode.CONVERT,
                        result=result,
                        operands=(source,),
                        location=expression.location,
                    )
                )
                return result
            arguments = self._lower_call_arguments(expression)
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
        if isinstance(expression, ast.RecordExpression):
            raise LoweringError(
                "record literal cannot be lowered as a scalar value",
                expression.location,
            )
        if isinstance(expression, ast.FieldAccessExpression):
            return self._lower_field_access(expression)
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

    def _lower_field_access(self, expression: ast.FieldAccessExpression) -> int:
        if isinstance(expression.target, ast.Identifier):
            binding = self._lookup_variable_or_none(expression.target.name)
            if binding is None and (
                enum := self.semantic_model.enums.get(expression.target.name)
            ) is not None:
                try:
                    discriminant = enum.discriminant(expression.field_name)
                except KeyError as error:
                    raise LoweringError(
                        (
                            f"enum '{enum.name}' has no variant "
                            f"'{expression.field_name}'"
                        ),
                        expression.location,
                    ) from error
                return self._emit_constant(
                    discriminant,
                    ast.TypeName.TRYTE,
                    expression.location,
                )
        if isinstance(expression.target, ast.Identifier):
            if binding is None:
                binding = self._lookup_variable(
                    expression.target.name,
                    expression.target.location,
                )
            if binding.fields is None:
                raise LoweringError(
                    f"variable '{expression.target.name}' is not a record",
                    expression.location,
                )
            field = binding.fields.get(expression.field_name)
            if field is None or field.register is None:
                raise LoweringError(
                    f"record field '{expression.field_name}' is unavailable",
                    expression.location,
                )
            return field.register
        if isinstance(expression.target, ast.IndexExpression):
            target = self._lower_indexed_aggregate_binding(expression.target)
            if target.fields is None:
                raise LoweringError(
                    "indexed aggregate has no projected fields",
                    expression.location,
                )
            field = target.fields.get(expression.field_name)
            if field is None:
                raise LoweringError(
                    f"record field '{expression.field_name}' is unavailable",
                    expression.location,
                )
            if field.register is not None:
                return field.register
            raise LoweringError(
                "indexed aggregate field is not a scalar leaf",
                expression.location,
            )
        target_type = self.semantic_model.declared_type_of(expression.target)
        if (
            isinstance(target_type, ast.NominalType)
            and self.semantic_model.is_record_type(target_type)
        ):
            record = self.semantic_model.record(target_type.name)
            target = self._lower_record_binding_from_expression(
                expression.target,
                record,
                expression.target.location,
            )
            assert target.fields is not None
            field = target.fields.get(expression.field_name)
            if field is None:
                raise LoweringError(
                    f"record field '{expression.field_name}' is unavailable",
                    expression.location,
                )
            if field.register is not None:
                return field.register
            if (
                isinstance(field.type_name, ast.NominalType)
                and self.semantic_model.is_record_type(field.type_name)
                and field.fields is not None
                and self.semantic_model.record_leaf_count(field.type_name.name) == 1
            ):
                registers = self._flatten_record_registers(
                    field.type_name.name,
                    field.fields,
                    expression.location,
                )
                return registers[0]
        raise LoweringError(
            "field access requires a lowered record binding",
            expression.location,
        )

    def _lower_field_container(
        self,
        expression: ast.Expression,
    ) -> _LoweredBinding:
        if isinstance(expression, ast.Identifier):
            binding = self._lookup_variable(expression.name, expression.location)
            if binding.fields is None:
                raise LoweringError(
                    "field assignment requires aggregate storage",
                    expression.location,
                )
            return binding
        if isinstance(expression, ast.FieldAccessExpression):
            return self._lower_field_binding(expression)
        if isinstance(expression, ast.IndexExpression):
            return self._lower_indexed_aggregate_binding(expression)
        raise LoweringError(
            "field assignment requires a lowered aggregate value",
            expression.location,
        )

    def _lower_field_binding(
        self,
        expression: ast.FieldAccessExpression,
    ) -> _LoweredBinding:
        container = self._lower_field_container(expression.target)
        if container.fields is None:
            raise LoweringError(
                "field access has no aggregate storage",
                expression.location,
            )
        field = container.fields.get(expression.field_name)
        if field is None:
            raise LoweringError(
                f"record field '{expression.field_name}' is unavailable",
                expression.location,
            )
        return field

    def _lower_indexed_aggregate_binding(
        self,
        expression: ast.IndexExpression,
    ) -> _LoweredBinding:
        array_type = self.semantic_model.declared_type_of(expression.target)
        if not isinstance(array_type, ast.ArrayType):
            raise LoweringError("indexed target is not an array", expression.location)
        constant = self.semantic_model.constant_value_of(expression.index)
        if not isinstance(constant, int) or not 0 <= constant < array_type.length:
            raise LoweringError(
                "aggregate array projection requires a constant index",
                expression.location,
            )
        if not isinstance(expression.target, ast.Identifier):
            raise LoweringError(
                "aggregate array projection requires named storage",
                expression.location,
            )
        binding = self._lookup_variable(expression.target.name, expression.target.location)
        if binding.fields is None:
            raise LoweringError(
                "aggregate array has no projected element storage",
                expression.location,
            )
        element = binding.fields.get(self._array_cell_name(constant))
        if element is None:
            raise LoweringError(
                f"array cell {constant} is unavailable",
                expression.location,
            )
        return element

    def _lower_call_arguments(self, expression: ast.CallExpression) -> tuple[int, ...]:
        signature = self.semantic_model.function(expression.function_name)
        registers: list[int] = []
        for argument, parameter_type in zip(
            expression.arguments,
            signature.parameter_types,
            strict=True,
        ):
            if isinstance(parameter_type, ast.SliceType):
                registers.append(self._lower_expression(argument.expression))
                source_type = self.semantic_model.declared_type_of(argument.expression)
                if isinstance(argument.expression, ast.Identifier):
                    binding = self._lookup_variable(argument.expression.name, argument.expression.location)
                    length_register = binding.slice_length_register
                    if length_register is None:
                        raise LoweringError("slice argument has no runtime length", argument.location)
                    registers.append(length_register)
                elif isinstance(argument.expression, ast.AddressOfExpression):
                    target = argument.expression.operand
                    if not isinstance(target, ast.Identifier):
                        raise LoweringError("slice address argument must name storage", argument.location)
                    binding = self._lookup_variable(target.name, target.location)
                    if not isinstance(binding.type_name, ast.ArrayType):
                        raise LoweringError("slice address argument has no static length", argument.location)
                    registers.append(self._emit_constant(binding.type_name.length, ast.TypeName.I64, argument.location))
                else:
                    raise LoweringError("unsupported slice argument", argument.location)
                continue
            if isinstance(parameter_type, ast.ArrayType):
                registers.extend(
                    self._lower_array_registers(argument.expression, parameter_type)
                )
                continue
            if (
                isinstance(parameter_type, ast.NominalType)
                and self.semantic_model.is_record_type(parameter_type)
            ):
                record = self.semantic_model.record(parameter_type.name)
                fields = self._lower_record_fields_from_expression(
                    argument.expression,
                    record,
                    argument.location,
                )
                registers.extend(
                    self._flatten_record_registers(
                        record.name,
                        fields,
                        argument.location,
                    )
                )
                continue
            if (
                isinstance(parameter_type, ast.NominalType)
                and self.semantic_model.is_enum_type(parameter_type)
                and self.semantic_model.enum_cell_count(parameter_type.name) > 1
            ):
                binding = self._lower_enum_binding_from_expression(
                    argument.expression,
                    parameter_type.name,
                    argument.location,
                )
                registers.extend(
                    self._flatten_enum_registers(
                        parameter_type.name,
                        binding,
                        argument.location,
                    )
                )
                continue
            registers.append(self._lower_expression(argument.expression))
        return tuple(registers)

    def _match_label_discriminant(self, label: ast.MatchCaseLabel) -> int:
        if isinstance(label, int):
            return label
        if isinstance(label, ast.MatchPayloadLabel):
            return self._match_label_discriminant(label.variant)
        if isinstance(label, ast.FieldAccessExpression):
            discriminant = self.semantic_model.constant_value_of(label)
            if discriminant is not None:
                return discriminant
            if isinstance(label.target, ast.Identifier):
                enum = self.semantic_model.enums.get(label.target.name)
                if enum is not None:
                    try:
                        return enum.discriminant(label.field_name)
                    except KeyError as error:
                        raise LoweringError(
                            (
                                f"enum '{enum.name}' has no variant "
                                f"'{label.field_name}'"
                            ),
                            label.location,
                        ) from error
        raise LoweringError("unsupported match case label")

    def _enum_case_entries(self, cases):
        return tuple(
            (self._match_label_discriminant(case.label), case)
            for case in cases
            if case.label is not None
        )

    def _lower_len(self, expression: ast.LenExpression) -> int:
        argument_type = self.semantic_model.declared_type_of(expression.argument)
        if isinstance(argument_type, ast.SliceType):
            argument = self._lower_expression(expression.argument)
            binding = (
                self._lookup_variable(expression.argument.name, expression.argument.location)
                if isinstance(expression.argument, ast.Identifier)
                else None
            )
            if binding is None or binding.slice_length_register is None:
                raise LoweringError("slice has no runtime length", expression.location)
            result = self._allocate(ast.TypeName.I64, expression.location)
            self._emit(IRInstruction(
                IROpcode.SLICE_LENGTH,
                result=result,
                operands=(argument, binding.slice_length_register),
                location=expression.location,
            ))
            return result
        if isinstance(argument_type, ast.ArrayType):
            return self._emit_constant(
                argument_type.length,
                ast.TypeName.TRYTE,
                expression.location,
            )
        if argument_type is ast.TypeName.STRING:
            text = self.semantic_model.static_text_of(expression.argument)
            assert text is not None
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
        RELATIONAL_OPS = (
            ast.BinaryOperator.EQUAL,
            ast.BinaryOperator.NOT_EQUAL,
            ast.BinaryOperator.LESS,
            ast.BinaryOperator.LESS_EQUAL,
            ast.BinaryOperator.GREATER,
            ast.BinaryOperator.GREATER_EQUAL,
        )
        if expression.operator in RELATIONAL_OPS:
            operand_type = self._storage_type(
                self.semantic_model.declared_type_of(expression.left),
                expression.left.location,
            )
            if operand_type is not ast.TypeName.F64:
                return self._lower_relational_expression(expression)
        left = self._lower_expression(expression.left)
        right = self._lower_expression(expression.right)
        if expression.operator is ast.BinaryOperator.SUBTRACT:
            if result_type in (ast.TypeName.I64, ast.TypeName.F64):
                result = self._allocate(result_type, expression.location)
                self._emit(
                    IRInstruction(
                        IROpcode.NUMERIC_DIFFERENCE,
                        result=result,
                        operands=(left, right),
                        location=expression.location,
                    )
                )
                return result
            inverted = self._allocate(
                self._storage_type(
                    self.semantic_model.declared_type_of(expression.right),
                    expression.right.location,
                ),
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

        if expression.operator in RELATIONAL_OPS:
            relation_codes = {
                ast.BinaryOperator.EQUAL: 0,
                ast.BinaryOperator.NOT_EQUAL: 1,
                ast.BinaryOperator.LESS: 2,
                ast.BinaryOperator.LESS_EQUAL: 3,
                ast.BinaryOperator.GREATER: 4,
                ast.BinaryOperator.GREATER_EQUAL: 5,
            }
            result = self._allocate(ast.TypeName.TRIT, expression.location)
            self._emit(
                IRInstruction(
                    IROpcode.RELATE,
                    result=result,
                    operands=(left, right),
                    immediate=relation_codes[expression.operator],
                    location=expression.location,
                )
            )
            return result

        opcode_map = {
            ast.BinaryOperator.ADD: IROpcode.ADD,
            ast.BinaryOperator.MULTIPLY: IROpcode.MULTIPLY,
            ast.BinaryOperator.DIVIDE: IROpcode.DIVIDE,
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
        selector_type = self.semantic_model.declared_type_of(expression.selector)
        if self.semantic_model.is_enum_type(selector_type):
            return self._lower_enum_match_expression(expression)

        cond_val = self.semantic_model.constant_value_of(expression.selector)
        if cond_val is not None:
            explicit_cases = {c.label: c for c in expression.cases if c.label is not None}
            fallback_case = next((c for c in expression.cases if c.label is None), None)
            target_case = explicit_cases.get(cond_val, fallback_case)
            if target_case is not None:
                return self._lower_expression(target_case.expression)
        selector_reg = self._lower_expression(expression.selector)
        result_type = self._storage_type(
            self.semantic_model.expression_types[id(expression)],
            expression.location,
        )
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

    def _lower_enum_match_expression(
        self,
        expression: ast.MatchExpression,
    ) -> int:
        explicit_entries = self._enum_case_entries(expression.cases)
        explicit_cases = dict(explicit_entries)
        fallback_case = next((c for c in expression.cases if c.label is None), None)
        cond_val = self.semantic_model.constant_value_of(expression.selector)
        if cond_val is not None:
            target_case = explicit_cases.get(cond_val, fallback_case)
            if target_case is not None:
                return self._lower_expression(target_case.expression)

        selector_registers = self._lower_enum_selector_registers(
            expression.selector,
            expression.location,
        )
        selector_reg = selector_registers[0]
        result_type = self._storage_type(
            self.semantic_model.expression_types[id(expression)],
            expression.location,
        )
        memory = self._allocate_memory(result_type, 1, True, expression.location)
        default_case = fallback_case or explicit_entries[-1][1]
        test_entries = explicit_entries if fallback_case is not None else explicit_entries[:-1]
        continuation = self._fresh_block("enum_match_expr_cont", expression.location)

        for discriminant, case in test_entries:
            less_block = self._fresh_block("enum_match_expr_less", case.location)
            case_block = self._fresh_block("enum_match_expr_case", case.location)
            greater_block = self._fresh_block("enum_match_expr_greater", case.location)
            next_block = self._fresh_block("enum_match_expr_next", expression.location)
            discriminant_reg = self._emit_constant(
                discriminant,
                ast.TypeName.TRYTE,
                case.location,
            )
            compare_reg = self._allocate(ast.TypeName.TRIT, case.location)
            self._emit(
                IRInstruction(
                    IROpcode.COMPARE,
                    result=compare_reg,
                    operands=(selector_reg, discriminant_reg),
                    location=case.location,
                )
            )
            self._emit(
                IRInstruction(
                    IROpcode.BRANCH3,
                    operands=(compare_reg,),
                    targets=(less_block.name, case_block.name, greater_block.name),
                    location=case.location,
                )
            )

            for branch_block in (less_block, greater_block):
                self.current = branch_block
                self._emit(
                    IRInstruction(
                        IROpcode.JUMP,
                        targets=(next_block.name,),
                        location=case.location,
                    )
                )

            self.current = case_block
            val_reg = self._lower_enum_case_expression(
                case,
                self.semantic_model.declared_type_of(expression.selector),
                selector_registers,
            )
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
            self.current = next_block

        val_reg = self._lower_enum_case_expression(
            default_case,
            self.semantic_model.declared_type_of(expression.selector),
            selector_registers,
        )
        idx = self._emit_constant(0, ast.TypeName.TRYTE, default_case.location)
        self._emit(
            IRInstruction(
                IROpcode.STORE,
                operands=(idx, val_reg),
                memory=memory,
                initialization=True,
                location=default_case.location,
            )
        )
        self._emit(
            IRInstruction(
                IROpcode.JUMP,
                targets=(continuation.name,),
                location=default_case.location,
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

    def _lower_enum_case_expression(
        self,
        case: ast.MatchExpressionCase,
        selector_type: ast.DeclaredType,
        selector_registers: tuple[int, ...],
    ) -> int:
        self.variable_scopes.append({})
        try:
            self._bind_enum_payload_case(case.label, selector_type, selector_registers)
            return self._lower_expression(case.expression)
        finally:
            self.variable_scopes.pop()


def lower(program: ast.Program, semantic_model: SemanticModel) -> IRModule:
    static_table = collect_static_string_literals(
        program,
        semantic_model.static_text_of,
    )
    static_strings = [
        IRStaticString(entry.id, entry.text) for entry in static_table.entries
    ]
    static_string_ids = {
        entry.value: entry.id for entry in static_table.entries
    }
    needs_empty_static_string = any(
        ast.TypeName.STRING in semantic_model.enum_layout(name).slot_types
        for name in semantic_model.enums
    )
    if needs_empty_static_string and "" not in static_string_ids:
        static_id = f"s{len(static_strings)}"
        static_strings.append(IRStaticString(static_id, ""))
        static_string_ids[""] = static_id
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
    for function in program.foreign_functions:
        functions.append(
            FunctionLowerer(
                ast.FunctionDeclaration(function.signature, ast.Block((), function.location), function.location),
                semantic_model,
                static_string_ids,
            ).lower(external=True)
        )
    return IRModule(tuple(functions), tuple(static_strings))
