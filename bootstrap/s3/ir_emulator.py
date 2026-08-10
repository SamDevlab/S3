"""Conservative hosted execution for reference-aware S3 IR."""

from __future__ import annotations

from dataclasses import dataclass

from .ir import IRFunction, IRInstruction, IRModule, IROpcode, IRType
from .ternary import add, compare, invert, tritwise_max, tritwise_min, TernaryRangeError, TernaryWidth, validate
from .verifier import verify_ir
from .numeric import (
    NumericError, NumericValue, checked_i64_add, checked_i64_mul,
    checked_i64_div, checked_i64_neg, checked_i64_to_tryte,
    validate_f64, validate_i64,
)


class IRExecutionError(RuntimeError):
    pass


@dataclass
class _Cell:
    value: object = None
    initialized: bool = False
    mutable: bool = True


@dataclass(frozen=True)
class ReferenceValue:
    cell: _Cell
    offset: int
    mutable: bool


@dataclass
class _Frame:
    function: IRFunction
    registers: dict[int, _Cell]
    memory: dict[int, list[_Cell]]
    block: str = "entry"
    index: int = 0


def _width(type_name: IRType) -> TernaryWidth:
    return TernaryWidth.TRIT if type_name is IRType.TRIT else TernaryWidth.TRYTE


def execute_ir(module: IRModule, entry: str = "main", optimization: object = None) -> object:
    global functions_module
    functions_module = module
    verify_ir(module)
    functions = {function.name: function for function in module.functions}
    if entry not in functions:
        raise IRExecutionError(f"missing entry function '{entry}'")
    return _execute_function(functions, functions[entry], (), ())


def _execute_function(functions, function, arguments, caller):
    registers = {r.index: _Cell(mutable=True) for r in function.registers}
    memory = {
        obj.index: [_Cell(mutable=obj.mutable) for _ in range(obj.length)]
        for obj in function.memory_objects
    }
    frame = _Frame(function, registers, memory)
    for parameter, value in zip(function.parameters, arguments, strict=True):
        frame.registers[parameter.register].value = value
        frame.registers[parameter.register].initialized = True
    blocks = {block.name: block for block in function.blocks}
    while True:
        block = blocks[frame.block]
        instruction = block.instructions[frame.index]
        op = instruction.opcode
        if op is IROpcode.CONST:
            frame.registers[instruction.result].value = instruction.immediate
            frame.registers[instruction.result].initialized = True
        elif op is IROpcode.CONST_STR:
            frame.registers[instruction.result].value = next(s.value for s in functions_module.static_strings if s.id == instruction.static_string)
            frame.registers[instruction.result].initialized = True
        elif op is IROpcode.MOVE:
            src = _read(frame, instruction.operands[0])
            _write(frame, instruction.result, src)
        elif op is IROpcode.INVERT:
            result_type = _register_type(function, instruction.result)
            value = _read(frame, instruction.operands[0])
            if result_type is IRType.I64:
                result = checked_i64_neg(value)
            elif result_type is IRType.F64:
                result = validate_f64(-float(value))
            else:
                result = invert(value, _width(result_type))
            _write(frame, instruction.result, result)
        elif op in {IROpcode.ADD, IROpcode.MULTIPLY, IROpcode.DIVIDE}:
            result_type = _register_type(function, instruction.result)
            left = _read(frame, instruction.operands[0])
            right = _read(frame, instruction.operands[1])
            if result_type is IRType.I64:
                if op is IROpcode.ADD:
                    result = checked_i64_add(left, right)
                elif op is IROpcode.MULTIPLY:
                    result = checked_i64_mul(left, right)
                else:
                    result = checked_i64_div(left, right)
            elif result_type is IRType.F64:
                if op is IROpcode.ADD:
                    result = validate_f64(float(left) + float(right))
                elif op is IROpcode.MULTIPLY:
                    result = validate_f64(float(left) * float(right))
                else:
                    result = NumericValue.f64(float(left)).divide(NumericValue.f64(float(right))).value
            else:
                result = add(left, right, _width(result_type))
            _write(frame, instruction.result, result)
        elif op is IROpcode.RELATE:
            left = _read(frame, instruction.operands[0])
            right = _read(frame, instruction.operands[1])
            relation = instruction.immediate
            truth = {
                0: left == right,
                1: left != right,
                2: left < right,
                3: left <= right,
                4: left > right,
                5: left >= right,
            }[relation]
            _write(frame, instruction.result, -1 if truth else 0)
        elif op is IROpcode.CONVERT:
            source_type = _register_type(function, instruction.operands[0])
            result_type = _register_type(function, instruction.result)
            value = _read(frame, instruction.operands[0])
            if result_type is IRType.I64:
                result = validate_i64(int(value))
            elif result_type is IRType.F64:
                result = validate_f64(value)
            elif source_type is IRType.I64 and result_type is IRType.TRYTE:
                result = checked_i64_to_tryte(value)
            else:
                raise IRExecutionError(f"unsupported conversion {source_type.value} -> {result_type.value}")
            _write(frame, instruction.result, result)
        elif op in {IROpcode.MINIMUM, IROpcode.MAXIMUM}:
            fn = tritwise_min if op is IROpcode.MINIMUM else tritwise_max
            _write(frame, instruction.result, fn(_read(frame, instruction.operands[0]), _read(frame, instruction.operands[1]), _width(_register_type(function, instruction.result))))
        elif op is IROpcode.COMPARE:
            operand_type = _register_type(function, instruction.operands[0])
            left = _read(frame, instruction.operands[0])
            right = _read(frame, instruction.operands[1])
            if operand_type in {IRType.I64, IRType.F64}:
                result = -1 if left < right else 1 if left > right else 0
            else:
                result = compare(left, right, _width(operand_type))
            _write(frame, instruction.result, result)
        elif op is IROpcode.LOAD:
            cell = memory[instruction.memory][_read(frame, instruction.operands[0])]
            if not cell.initialized: raise IRExecutionError("uninitialized memory load")
            _write(frame, instruction.result, cell.value)
        elif op is IROpcode.STORE:
            cell = memory[instruction.memory][_read(frame, instruction.operands[0])]
            if not cell.mutable and cell.initialized and not instruction.initialization: raise IRExecutionError("immutable memory write")
            _store_value(cell, _read(frame, instruction.operands[1]), _memory_type(function, instruction.memory))
        elif op is IROpcode.ADDRESS_OF:
            if instruction.memory is not None:
                index = _read(frame, instruction.operands[0]) if instruction.operands else 0
                cells = memory[instruction.memory]
                if not isinstance(index, int) or not 0 <= index < len(cells):
                    raise IRExecutionError("array reference index is out of bounds")
                cell = cells[index]
            else:
                cell = frame.registers[instruction.operands[0]]
            _write(frame, instruction.result, ReferenceValue(cell, 0, instruction.reference_mutable))
        elif op is IROpcode.REFERENCE_LOAD:
            ref = _read(frame, instruction.operands[0])
            if not isinstance(ref, ReferenceValue) or not ref.cell.initialized: raise IRExecutionError("invalid reference load")
            _write(frame, instruction.result, ref.cell.value)
        elif op is IROpcode.REFERENCE_STORE:
            ref = _read(frame, instruction.operands[0])
            if not isinstance(ref, ReferenceValue) or not ref.mutable: raise IRExecutionError("shared reference store")
            _store_value(ref.cell, _read(frame, instruction.operands[1]), instruction.reference_target)
        elif op is IROpcode.CALL:
            callee = functions[instruction.callee]
            args = tuple(_read(frame, reg) for reg in instruction.operands)
            result = _execute_function(functions, callee, args, frame)
            if instruction.results: _write(frame, instruction.results[0], result)
        elif op is IROpcode.RETURN:
            return _read(frame, instruction.operands[0])
        elif op is IROpcode.JUMP:
            frame.block, frame.index = instruction.targets[0], 0; continue
        elif op is IROpcode.BRANCH3:
            value = _read(frame, instruction.operands[0]); frame.block, frame.index = instruction.targets[{ -1: 0, 0: 1, 1: 2}[value]], 0; continue
        else:
            raise IRExecutionError(f"unsupported IR opcode {op}")
        frame.index += 1


def _register_type(function, register):
    return next(item.type for item in function.registers if item.index == register)


def _read(frame, register):
    cell = frame.registers[register]
    if not cell.initialized: raise IRExecutionError(f"uninitialized register r{register}")
    return cell.value


def _write(frame, register, value):
    cell = frame.registers[register]
    _store_value(cell, value, _register_type(frame.function, register))


def _memory_type(function, memory_index):
    return next(item.element_type for item in function.memory_objects if item.index == memory_index)


def _store_value(cell, value, value_type):
    if value_type is IRType.REFERENCE:
        if not isinstance(value, ReferenceValue):
            raise IRExecutionError("invalid null or non-provenance reference")
    elif value_type is IRType.STRING:
        if not isinstance(value, str):
            raise IRExecutionError("invalid string value")
    elif value_type is IRType.I64:
        try:
            validate_i64(value)
        except (TypeError, ValueError) as error:
            raise IRExecutionError(f"invalid i64 value: {value!r}") from error
    elif value_type is IRType.F64:
        try:
            validate_f64(value)
        except (TypeError, ValueError) as error:
            raise IRExecutionError(f"invalid f64 value: {value!r}") from error
    else:
        try:
            validate(value, _width(value_type))
        except (TernaryRangeError, TypeError, ValueError) as error:
            raise IRExecutionError(f"invalid {value_type.value} value: {value!r}") from error
    cell.value = value
    cell.initialized = True


functions_module = IRModule(())
