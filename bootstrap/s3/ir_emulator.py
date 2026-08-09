"""Conservative hosted execution for reference-aware S3 IR."""

from __future__ import annotations

from dataclasses import dataclass

from .ir import IRFunction, IRInstruction, IRModule, IROpcode, IRType
from .ternary import add, compare, invert, tritwise_max, tritwise_min, TernaryRangeError, TernaryWidth, validate
from .verifier import verify_ir


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


def execute_ir(module: IRModule, entry: str = "main", optimization: object = None) -> int:
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
            _write(frame, instruction.result, invert(_read(frame, instruction.operands[0]), _width(_register_type(function, instruction.result))))
        elif op is IROpcode.ADD:
            _write(frame, instruction.result, add(_read(frame, instruction.operands[0]), _read(frame, instruction.operands[1]), _width(_register_type(function, instruction.result))))
        elif op in {IROpcode.MINIMUM, IROpcode.MAXIMUM}:
            fn = tritwise_min if op is IROpcode.MINIMUM else tritwise_max
            _write(frame, instruction.result, fn(_read(frame, instruction.operands[0]), _read(frame, instruction.operands[1]), _width(_register_type(function, instruction.result))))
        elif op is IROpcode.COMPARE:
            _write(frame, instruction.result, compare(_read(frame, instruction.operands[0]), _read(frame, instruction.operands[1]), _width(_register_type(function, instruction.operands[0]))))
        elif op is IROpcode.LOAD:
            cell = memory[instruction.memory][_read(frame, instruction.operands[0])]
            if not cell.initialized: raise IRExecutionError("uninitialized memory load")
            _write(frame, instruction.result, cell.value)
        elif op is IROpcode.STORE:
            cell = memory[instruction.memory][_read(frame, instruction.operands[0])]
            if not cell.mutable and cell.initialized and not instruction.initialization: raise IRExecutionError("immutable memory write")
            _store_value(cell, _read(frame, instruction.operands[1]), _memory_type(function, instruction.memory))
        elif op is IROpcode.ADDRESS_OF:
            cell = memory[instruction.memory][0] if instruction.memory is not None else frame.registers[instruction.operands[0]]
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
    else:
        try:
            validate(value, _width(value_type))
        except (TernaryRangeError, TypeError, ValueError) as error:
            raise IRExecutionError(f"invalid {value_type.value} value: {value!r}") from error
    cell.value = value
    cell.initialized = True


functions_module = IRModule(())
