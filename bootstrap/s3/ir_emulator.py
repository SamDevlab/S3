"""Conservative hosted execution for reference-aware S3 IR."""

from __future__ import annotations

from dataclasses import dataclass

from .ir import (
    DYNAMIC_BUILTIN_SIGNATURES,
    IRFunction,
    IRInstruction,
    IRModule,
    IROpcode,
    IRType,
)
from .dynamic import (
    DynamicBytes,
    DynamicText,
    DynamicVector,
    DynamicMap,
    DynamicSet,
    bytes_from_text,
    bytes_new,
    f64_vector_new,
    i64_vector_new,
    tryte_vector_new,
    text_from_bytes,
    text_new,
)
from .host_services import SourceResourceRuntime
from .ternary import add, compare, invert, tritwise_max, tritwise_min, TernaryRangeError, TernaryWidth, validate
from .verifier import verify_ir
from .numeric import NumericType, validate_f64, validate_i64


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
    global functions_module, resource_runtime
    functions_module = module
    resource_runtime = SourceResourceRuntime()
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
            result_type = _register_type(function, instruction.result)
            if result_type is IRType.I64:
                _write(frame, instruction.result, validate_i64(_read(frame, instruction.operands[0]) + _read(frame, instruction.operands[1])))
            elif result_type is IRType.F64:
                _write(frame, instruction.result, validate_f64(_read(frame, instruction.operands[0]) + _read(frame, instruction.operands[1])))
            else:
                _write(frame, instruction.result, add(_read(frame, instruction.operands[0]), _read(frame, instruction.operands[1]), _width(result_type)))
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
            args = tuple(_read(frame, reg) for reg in instruction.operands)
            if instruction.callee in DYNAMIC_BUILTIN_SIGNATURES:
                result = _execute_dynamic_builtin(instruction.callee, args)
            else:
                callee = functions[instruction.callee]
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
    elif value_type is IRType.BYTES:
        if not isinstance(value, DynamicBytes):
            raise IRExecutionError("invalid bytes value")
    elif value_type is IRType.TEXT:
        if not isinstance(value, DynamicText):
            raise IRExecutionError("invalid text value")
    elif value_type is IRType.VECTOR:
        if not isinstance(value, (DynamicVector, DynamicMap, DynamicSet)):
            raise IRExecutionError("invalid vector value")
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


def _reference_owner(value):
    if not isinstance(value, ReferenceValue) or not value.cell.initialized:
        raise IRExecutionError("invalid dynamic buffer reference")
    return value.cell.value


def _execute_dynamic_builtin(name: str, args: tuple[object, ...]) -> object:
    if name == "host_capability_grant":
        return resource_runtime.grant(args[0])
    if name == "resource_open":
        return resource_runtime.open(args[0])
    if name == "resource_is_open":
        return resource_runtime.is_open(_reference_owner(args[0]))
    if name == "resource_kind":
        return resource_runtime.kind(_reference_owner(args[0]))
    if name == "resource_invoke":
        return resource_runtime.invoke(_reference_owner(args[0]), args[1])
    if name == "resource_close":
        reference = args[0]
        handle = _reference_owner(reference)
        resource_runtime.close(handle)
        reference.cell.value = 0
        return 0
    if name == "bytes_new":
        return bytes_new(args[0])
    if name == "bytes_len":
        return _reference_owner(args[0]).length
    if name == "bytes_capacity":
        return _reference_owner(args[0]).capacity
    if name == "bytes_get":
        return _reference_owner(args[0]).get(args[1])
    if name == "bytes_set":
        _reference_owner(args[0]).set(args[1], args[2])
        return 0
    if name == "bytes_push":
        _reference_owner(args[0]).push(args[1])
        return 0
    if name == "bytes_reserve":
        _reference_owner(args[0]).reserve(args[1])
        return 0
    if name == "bytes_clone":
        return _reference_owner(args[0]).clone()
    if name == "bytes_concat":
        return _reference_owner(args[0]).concat(_reference_owner(args[1]))
    if name == "bytes_slice":
        return _reference_owner(args[0]).slice(args[1], args[2])
    if name == "bytes_from_text":
        return bytes_from_text(_reference_owner(args[0]))
    if name == "text_new":
        return text_new(args[0])
    if name == "text_from_static":
        return DynamicText.from_static(args[0])
    if name == "text_len":
        return _reference_owner(args[0]).length
    if name == "text_capacity":
        return _reference_owner(args[0]).capacity
    if name == "text_reserve":
        _reference_owner(args[0]).reserve(args[1])
        return 0
    if name == "text_append":
        _reference_owner(args[0]).append(_reference_owner(args[1]))
        return 0
    if name == "text_append_static":
        _reference_owner(args[0]).append_static(args[1])
        return 0
    if name == "text_clone":
        return _reference_owner(args[0]).clone()
    if name == "text_concat":
        return _reference_owner(args[0]).concat(_reference_owner(args[1]))
    if name == "text_slice":
        return _reference_owner(args[0]).slice(args[1], args[2])
    if name == "text_find":
        return _reference_owner(args[0]).find(_reference_owner(args[1]))
    if name == "text_from_bytes":
        return text_from_bytes(_reference_owner(args[0]))
    if name.startswith("tryte_vector_"):
        return _execute_vector_builtin(name, args, "tryte", tryte_vector_new)
    if name.startswith("i64_vector_"):
        return _execute_vector_builtin(name, args, "i64", i64_vector_new)
    if name.startswith("f64_vector_"):
        return _execute_vector_builtin(name, args, "f64", f64_vector_new)
    if name.startswith("i64_map_"):
        return _execute_map_builtin(name, args)
    if name.startswith("i64_set_"):
        return _execute_set_builtin(name, args)
    raise IRExecutionError(f"unsupported dynamic builtin '{name}'")


def _execute_vector_builtin(name: str, args: tuple[object, ...], element_type: str, constructor) -> object:
    operation = name[len(element_type) + len("_vector_") :]
    if operation == "new":
        return constructor(args[0])
    owner = _reference_owner(args[0])
    if not isinstance(owner, DynamicVector) or owner.element_type != element_type:
        raise IRExecutionError(f"invalid {element_type} vector reference")
    if operation == "len":
        return owner.length
    if operation == "capacity":
        return owner.capacity
    if operation == "reserve":
        owner.reserve(args[1])
        return 0
    if operation == "push":
        owner.push(args[1])
        return 0
    if operation == "pop":
        return owner.pop()
    if operation == "get":
        return owner.get(args[1])
    if operation == "set":
        owner.set(args[1], args[2])
        return 0
    if operation == "clone":
        return owner.clone()
    if operation == "slice":
        return owner.slice(args[1], args[2])
    raise IRExecutionError(f"unsupported vector builtin '{name}'")


def _execute_map_builtin(name: str, args: tuple[object, ...]) -> object:
    from .dynamic import i64_map_new

    if name == "i64_map_new":
        return i64_map_new(args[0])
    owner = _reference_owner(args[0])
    if not isinstance(owner, DynamicMap):
        raise IRExecutionError("invalid i64 map reference")
    operation = name[len("i64_map_") :]
    if operation == "len":
        return owner.length
    if operation == "capacity":
        return owner.capacity
    if operation == "reserve":
        owner.reserve(args[1])
        return 0
    if operation == "put":
        owner.put(args[1], args[2])
        return 0
    if operation == "contains":
        return owner.contains(args[1])
    if operation == "get":
        return owner.get(args[1])
    if operation == "remove":
        owner.remove(args[1])
        return 0
    if operation == "key_at":
        return owner.key_at(args[1])
    if operation == "value_at":
        return owner.value_at(args[1])
    if operation == "clone":
        return owner.clone()
    raise IRExecutionError(f"unsupported map builtin '{name}'")


def _execute_set_builtin(name: str, args: tuple[object, ...]) -> object:
    from .dynamic import i64_set_new

    if name == "i64_set_new":
        return i64_set_new(args[0])
    owner = _reference_owner(args[0])
    if not isinstance(owner, DynamicSet):
        raise IRExecutionError("invalid i64 set reference")
    operation = name[len("i64_set_") :]
    if operation == "len":
        return owner.length
    if operation == "capacity":
        return owner.capacity
    if operation == "reserve":
        owner.reserve(args[1])
        return 0
    if operation == "add":
        owner.add(args[1])
        return 0
    if operation == "contains":
        return owner.contains(args[1])
    if operation == "remove":
        owner.remove(args[1])
        return 0
    if operation == "at":
        return owner.at(args[1])
    if operation == "clone":
        return owner.clone()
    raise IRExecutionError(f"unsupported set builtin '{name}'")


functions_module = IRModule(())
resource_runtime = SourceResourceRuntime()
