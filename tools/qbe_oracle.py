"""Experimental, fail-closed translator from verified S3 IR to QBE IL."""

from __future__ import annotations

import re

from bootstrap.s3.ir import (
    DYNAMIC_BUILTIN_SIGNATURES,
    IRFunction,
    IRInstruction,
    IRModule,
    IROpcode,
    IRType,
)
from bootstrap.s3.verifier import verify_ir


class QBETranslationError(ValueError):
    """The verified S3 program uses semantics outside the experimental subset."""


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_QBE_TYPES = {
    IRType.I64: "l",
    IRType.F64: "d",
    IRType.TRIT: "l",
    IRType.TRYTE: "l",
    IRType.STRING: "l",
    IRType.BYTES: "l",
    IRType.TEXT: "l",
    IRType.VECTOR: "l",
    IRType.REFERENCE: "l",
}
_QBE_SCALAR_TYPES = frozenset(
    {IRType.I64, IRType.F64, IRType.TRIT, IRType.TRYTE}
)
_QBE_FUNCTION_RESULT_TYPES = _QBE_SCALAR_TYPES | {
    IRType.STRING,
    IRType.BYTES,
    IRType.TEXT,
    IRType.VECTOR,
}
_QBE_ABI_TYPES = _QBE_SCALAR_TYPES | {
    IRType.STRING,
    IRType.BYTES,
    IRType.TEXT,
    IRType.VECTOR,
    IRType.REFERENCE,
}
_QBE_REFERENCE_OWNER_NAMES = {
    IRType.VECTOR: "vector",
    IRType.BYTES: "bytes",
    IRType.TEXT: "text",
}
_QBE_I64_VECTOR_BUILTINS = frozenset(
    {
        "i64_vector_new",
        "i64_vector_len",
        "i64_vector_capacity",
        "i64_vector_reserve",
        "i64_vector_push",
        "i64_vector_pop",
        "i64_vector_get",
        "i64_vector_set",
        "i64_vector_clone",
        "i64_vector_slice",
    }
)
_QBE_TRYTE_VECTOR_BUILTINS = frozenset(
    builtin.replace("i64_", "tryte_", 1) for builtin in _QBE_I64_VECTOR_BUILTINS
)
_QBE_F64_VECTOR_BUILTINS = frozenset(
    builtin.replace("i64_", "f64_", 1) for builtin in _QBE_I64_VECTOR_BUILTINS
)
_QBE_F64_VECTOR_ABI_ADAPTERS = frozenset(
    {
        "f64_vector_get",
        "f64_vector_pop",
        "f64_vector_push",
        "f64_vector_set",
    }
)
_QBE_I64_MAP_SET_BUILTINS = frozenset(
    {
        "i64_map_new",
        "i64_map_len",
        "i64_map_capacity",
        "i64_map_reserve",
        "i64_map_put",
        "i64_map_contains",
        "i64_map_get",
        "i64_map_remove",
        "i64_map_key_at",
        "i64_map_value_at",
        "i64_map_clone",
        "i64_set_new",
        "i64_set_len",
        "i64_set_capacity",
        "i64_set_reserve",
        "i64_set_add",
        "i64_set_contains",
        "i64_set_remove",
        "i64_set_at",
        "i64_set_clone",
    }
)
_QBE_BYTES_BUILTINS = frozenset(
    {
        "bytes_new",
        "bytes_len",
        "bytes_capacity",
        "bytes_reserve",
        "bytes_push",
        "bytes_get",
        "bytes_set",
        "bytes_clone",
        "bytes_concat",
        "bytes_slice",
    }
)
_QBE_TEXT_BUILTINS = frozenset(
    {
        "text_new",
        "text_from_static",
        "text_len",
        "text_capacity",
        "text_reserve",
        "text_append",
        "text_append_static",
        "text_clone",
        "text_concat",
        "text_slice",
        "text_find",
        "text_from_bytes",
        "bytes_from_text",
    }
)
_QBE_TEXT_MAP_BUILTINS = frozenset(
    {
        "text_i64_map_new",
        "text_i64_map_len",
        "text_i64_map_capacity",
        "text_i64_map_reserve",
        "text_i64_map_put",
        "text_i64_map_contains",
        "text_i64_map_get",
        "text_i64_map_remove",
        "text_i64_map_key_at",
        "text_i64_map_value_at",
        "text_i64_map_clone",
    }
)
_QBE_DYNAMIC_CONTAINER_BUILTINS = (
    _QBE_I64_VECTOR_BUILTINS
    | _QBE_TRYTE_VECTOR_BUILTINS
    | _QBE_F64_VECTOR_BUILTINS
    | _QBE_I64_MAP_SET_BUILTINS
    | _QBE_BYTES_BUILTINS
    | _QBE_TEXT_BUILTINS
    | _QBE_TEXT_MAP_BUILTINS
)
_QBE_DYNAMIC_CONTAINER_RUNTIME_SYMBOLS = {
    builtin: f"__s3_builtin_{builtin}" for builtin in _QBE_I64_VECTOR_BUILTINS
}
_QBE_DYNAMIC_CONTAINER_RUNTIME_SYMBOLS.update(
    {builtin: f"__s3_builtin_{builtin}" for builtin in _QBE_TRYTE_VECTOR_BUILTINS}
)
_QBE_DYNAMIC_CONTAINER_RUNTIME_SYMBOLS.update(
    {builtin: f"__s3_builtin_{builtin}" for builtin in _QBE_F64_VECTOR_BUILTINS}
)
_QBE_DYNAMIC_CONTAINER_RUNTIME_SYMBOLS.update(
    {builtin: f"__s3_qbe_{builtin}" for builtin in _QBE_F64_VECTOR_ABI_ADAPTERS}
)
_QBE_DYNAMIC_CONTAINER_RUNTIME_SYMBOLS.update(
    {builtin: f"__s3_builtin_{builtin}" for builtin in _QBE_I64_MAP_SET_BUILTINS}
)
_QBE_DYNAMIC_CONTAINER_RUNTIME_SYMBOLS.update(
    {builtin: f"__s3_builtin_{builtin}" for builtin in _QBE_BYTES_BUILTINS}
)
_QBE_DYNAMIC_CONTAINER_RUNTIME_SYMBOLS.update(
    {builtin: f"__s3_builtin_{builtin}" for builtin in _QBE_TEXT_BUILTINS}
)
_QBE_DYNAMIC_CONTAINER_RUNTIME_SYMBOLS.update(
    {builtin: f"__s3_builtin_{builtin}" for builtin in _QBE_TEXT_MAP_BUILTINS}
)
_I64_MIN = -(1 << 63)
_I64_MAX = (1 << 63) - 1
_TRIT_MIN, _TRIT_MAX = -1, 1
_TRYTE_MIN, _TRYTE_MAX = -364, 364


def translate_verified_ir(module: IRModule) -> str:
    """Verify and translate the supported experimental QBE subset.

    Checked numeric operations and memory accesses are guarded before QBE
    machine operations. Dynamic builtins outside the explicitly supported
    shared-runtime families are rejected.
    """

    verify_ir(module)
    _validate_supported_module(module)
    emitted = ["# Experimental QBE oracle; generated from verified S3 IR."]
    static_string_symbols = _static_string_symbols(module)
    emitted.extend(_emit_static_string_data(module, static_string_symbols))
    functions = {function.name: function for function in module.functions}
    for function_index, function in enumerate(module.functions):
        emitted.extend(
            _translate_function(
                function, function_index, functions, static_string_symbols
            )
        )
    return "\n".join(emitted) + "\n"


def _validate_supported_module(module: IRModule) -> None:
    functions = {function.name: function for function in module.functions}
    for function in module.functions:
        if function.external:
            raise QBETranslationError(
                f"external function '{function.name}' is outside QBE oracle V5"
            )
        if not _IDENTIFIER.fullmatch(function.name):
            raise QBETranslationError(
                f"function name '{function.name}' cannot be represented safely in QBE IL"
            )
        if function.return_type not in _QBE_FUNCTION_RESULT_TYPES:
            raise QBETranslationError(
                f"function '{function.name}' result type {function.return_type.value} "
                "is outside QBE oracle V5"
            )
        if any(type_ not in _QBE_FUNCTION_RESULT_TYPES for type_ in function.result_types):
            raise QBETranslationError(
                f"function '{function.name}' has a result cell outside QBE oracle V5"
            )
        if function.name == "main" and function.result_width != 1:
            raise QBETranslationError("QBE entry function 'main' must have one result cell")
        if any(parameter.type not in _QBE_ABI_TYPES for parameter in function.parameters):
            raise QBETranslationError(
                f"function '{function.name}' has a non-scalar ABI parameter"
            )
        if any(register.type not in _QBE_TYPES for register in function.registers):
            unsupported = next(
                register.type.value
                for register in function.registers
                if register.type not in _QBE_TYPES
            )
            raise QBETranslationError(
                f"function '{function.name}' uses unsupported register type {unsupported}; "
                "this is outside QBE oracle V5"
            )
        for memory in function.memory_objects:
            if memory.element_type not in _QBE_SCALAR_TYPES:
                raise QBETranslationError(
                    f"function '{function.name}' memory m{memory.index} has non-scalar "
                    f"element type {memory.element_type.value}; this is outside QBE oracle V5"
                )
            if memory.length <= 0 or memory.length > _I64_MAX // 8:
                raise QBETranslationError(
                    f"function '{function.name}' memory m{memory.index} has a length "
                    "that cannot be represented by the QBE stack layout"
                )
        for block in function.blocks:
            for instruction in block.instructions:
                _validate_instruction(function, block.name, instruction, functions)
        _validate_memory_initialization(function)


def _validate_memory_initialization(function: IRFunction) -> None:
    """Reject loads that verified IR permits but S3 would trap at runtime."""

    if not any(
        instruction.opcode is IROpcode.LOAD
        for block in function.blocks
        for instruction in block.instructions
    ):
        return

    constants: dict[int, int] = {}
    moves: dict[int, int] = {}
    for block in function.blocks:
        for instruction in block.instructions:
            if instruction.opcode is IROpcode.CONST and instruction.result is not None:
                if isinstance(instruction.immediate, int):
                    constants[instruction.result] = instruction.immediate
            elif instruction.opcode is IROpcode.MOVE and instruction.result is not None:
                moves[instruction.result] = instruction.operands[0]

    def index_key(register: int) -> tuple[str, int]:
        seen: set[int] = set()
        while register in moves and register not in seen:
            seen.add(register)
            register = moves[register]
        if register in constants:
            return ("constant", constants[register])
        return ("register", register)

    memory_lengths = {memory.index: memory.length for memory in function.memory_objects}
    top: dict[int, frozenset[tuple[str, int]] | None] = {
        index: None for index in memory_lengths
    }
    empty = {index: frozenset() for index in memory_lengths}
    blocks = {block.name: block for block in function.blocks}
    predecessors: dict[str, set[str]] = {name: set() for name in blocks}
    for block in function.blocks:
        terminator = block.instructions[-1]
        for target in terminator.targets:
            predecessors[target].add(block.name)

    entry = function.blocks[0].name
    reachable: set[str] = set()
    pending = [entry]
    while pending:
        name = pending.pop()
        if name in reachable:
            continue
        reachable.add(name)
        pending.extend(blocks[name].instructions[-1].targets)

    def intersect(
        states: list[dict[int, frozenset[tuple[str, int]] | None]],
    ) -> dict[int, frozenset[tuple[str, int]] | None]:
        result: dict[int, frozenset[tuple[str, int]] | None] = {}
        for memory_index in memory_lengths:
            finite = [state[memory_index] for state in states if state[memory_index] is not None]
            if not finite:
                result[memory_index] = None
            else:
                common = set(finite[0])
                for facts in finite[1:]:
                    common.intersection_update(facts)
                result[memory_index] = frozenset(common)
        return result

    def transfer_stores(
        block_name: str,
        state: dict[int, frozenset[tuple[str, int]] | None],
    ) -> dict[int, frozenset[tuple[str, int]] | None]:
        result = dict(state)
        for instruction in blocks[block_name].instructions:
            if instruction.opcode is not IROpcode.STORE or instruction.memory is None:
                continue
            key = index_key(instruction.operands[0])
            length = memory_lengths[instruction.memory]
            if key[0] == "constant" and not 0 <= key[1] < length:
                continue
            facts = result[instruction.memory]
            if facts is not None:
                result[instruction.memory] = facts | {key}
        return result

    incoming = {name: dict(top) for name in reachable}
    outgoing = {name: dict(top) for name in reachable}
    while True:
        changed = False
        for name in (block.name for block in function.blocks if block.name in reachable):
            if name == entry:
                new_in = dict(empty)
            else:
                incoming_states = [
                    outgoing[pred]
                    for pred in predecessors[name]
                    if pred in reachable
                ]
                new_in = intersect(incoming_states) if incoming_states else dict(empty)
            new_out = transfer_stores(name, new_in)
            if new_in != incoming[name] or new_out != outgoing[name]:
                incoming[name] = new_in
                outgoing[name] = new_out
                changed = True
        if not changed:
            break

    for name in (block.name for block in function.blocks if block.name in reachable):
        state = dict(incoming[name])
        for instruction in blocks[name].instructions:
            if instruction.opcode is IROpcode.LOAD:
                assert instruction.memory is not None
                key = index_key(instruction.operands[0])
                facts = state[instruction.memory]
                length = memory_lengths[instruction.memory]
                fully_initialized = facts is not None and sum(
                    1
                    for kind, value in facts
                    if kind == "constant" and 0 <= value < length
                ) == length
                if facts is not None and key not in facts and not fully_initialized:
                    raise QBETranslationError(
                        f"function '{function.name}' may load uninitialized memory "
                        f"m{instruction.memory} in block '{name}'"
                    )
            elif instruction.opcode is IROpcode.STORE and instruction.memory is not None:
                key = index_key(instruction.operands[0])
                length = memory_lengths[instruction.memory]
                if key[0] == "constant" and not 0 <= key[1] < length:
                    continue
                facts = state[instruction.memory]
                if facts is not None:
                    state[instruction.memory] = facts | {key}


def _validate_instruction(
    function: IRFunction,
    block_name: str,
    instruction: IRInstruction,
    functions: dict[str, IRFunction],
) -> None:
    op = instruction.opcode
    operands = instruction.operands
    registers = {register.index: register.type for register in function.registers}

    if op is IROpcode.CONST:
        result_type = _result_type(function, instruction)
        if result_type not in _QBE_SCALAR_TYPES:
            _unsupported(function, block_name, instruction, "constant type")
        return
    if op is IROpcode.MOVE:
        result_type = _result_type(function, instruction)
        if result_type not in _QBE_ABI_TYPES:
            _unsupported(function, block_name, instruction, "move type")
        return
    if op is IROpcode.CONST_STR:
        if (
            operands
            or _result_type(function, instruction) is not IRType.STRING
            or instruction.static_string is None
        ):
            _unsupported(function, block_name, instruction, "static string constant shape")
        return
    if op is IROpcode.ADDRESS_OF:
        if (
            len(operands) != 1
            or len(instruction.results) != 1
            or registers[operands[0]] not in _QBE_REFERENCE_OWNER_NAMES
            or _result_type(function, instruction) is not IRType.REFERENCE
        ):
            _unsupported(function, block_name, instruction, "owned container reference shape")
        return
    if op is IROpcode.INVERT:
        if len(operands) != 1 or _result_type(function, instruction) not in _QBE_SCALAR_TYPES:
            _unsupported(function, block_name, instruction, "invert shape")
        return
    if op in {
        IROpcode.ADD,
        IROpcode.NUMERIC_DIFFERENCE,
        IROpcode.MULTIPLY,
        IROpcode.DIVIDE,
    }:
        result_type = _result_type(function, instruction)
        if len(operands) != 2 or result_type not in _QBE_SCALAR_TYPES:
            _unsupported(function, block_name, instruction, "numeric operation shape")
        if op in {
            IROpcode.NUMERIC_DIFFERENCE,
            IROpcode.MULTIPLY,
            IROpcode.DIVIDE,
        } and result_type not in {IRType.I64, IRType.F64}:
            _unsupported(function, block_name, instruction, "numeric operation type")
        return
    if op in {IROpcode.COMPARE, IROpcode.RELATE}:
        if len(operands) != 2 or any(
            registers[operand] not in _QBE_SCALAR_TYPES for operand in operands
        ):
            _unsupported(function, block_name, instruction, "comparison operands")
        if _result_type(function, instruction) is not IRType.TRIT:
            _unsupported(function, block_name, instruction, "comparison result")
        return
    if op is IROpcode.CALL:
        callee_name = instruction.callee or ""
        callee = functions.get(callee_name)
        if callee is None:
            signature = DYNAMIC_BUILTIN_SIGNATURES.get(callee_name)
            if callee_name not in _QBE_DYNAMIC_CONTAINER_BUILTINS or signature is None:
                _unsupported(function, block_name, instruction, "external or builtin call")
            parameter_types, result_types = signature
            if tuple(registers[operand] for operand in operands) != parameter_types:
                _unsupported(function, block_name, instruction, "dynamic builtin arguments")
            if instruction.results and tuple(
                registers[result] for result in instruction.results
            ) != result_types:
                _unsupported(function, block_name, instruction, "dynamic builtin results")
            return
        if tuple(registers[operand] for operand in operands) != tuple(
            parameter.type for parameter in callee.parameters
        ):
            _unsupported(function, block_name, instruction, "callee ABI arguments")
        if any(parameter.type not in _QBE_ABI_TYPES for parameter in callee.parameters):
            _unsupported(function, block_name, instruction, "non-scalar callee ABI")
        if instruction.results and (
            len(instruction.results) != callee.result_width
            or tuple(registers[result] for result in instruction.results)
            != callee.result_types
        ):
            _unsupported(function, block_name, instruction, "callee result cells")
        return
    if op in {IROpcode.LOAD, IROpcode.STORE}:
        memory = _memory_object(function, instruction.memory)
        if memory.element_type not in _QBE_SCALAR_TYPES:
            _unsupported(function, block_name, instruction, "non-scalar memory element")
        expected_operands = 1 if op is IROpcode.LOAD else 2
        if len(operands) != expected_operands:
            _unsupported(function, block_name, instruction, "memory operation shape")
        if registers[operands[0]] not in {IRType.I64, IRType.TRYTE}:
            _unsupported(function, block_name, instruction, "memory index type")
        if op is IROpcode.LOAD:
            if _result_type(function, instruction) is not memory.element_type:
                _unsupported(function, block_name, instruction, "memory load type")
        else:
            if instruction.results or registers[operands[1]] is not memory.element_type:
                _unsupported(function, block_name, instruction, "memory store type")
        return
    if op is IROpcode.CONVERT:
        source_type = registers[operands[0]] if len(operands) == 1 else None
        result_type = _result_type(function, instruction)
        if (source_type, result_type) not in {
            (IRType.TRIT, IRType.I64),
            (IRType.TRYTE, IRType.I64),
            (IRType.TRIT, IRType.F64),
            (IRType.TRYTE, IRType.F64),
            (IRType.I64, IRType.F64),
            (IRType.I64, IRType.TRYTE),
        }:
            _unsupported(function, block_name, instruction, "conversion shape")
        return
    if op in {IROpcode.MINIMUM, IROpcode.MAXIMUM}:
        if len(operands) != 2 or _result_type(function, instruction) not in {
            IRType.TRIT,
            IRType.TRYTE,
        }:
            _unsupported(function, block_name, instruction, "balanced extreme shape")
        return
    if op is IROpcode.JUMP:
        return
    if op is IROpcode.BRANCH3:
        if len(operands) != 1 or registers[operands[0]] is not IRType.TRIT:
            _unsupported(function, block_name, instruction, "branch3 condition")
        return
    if op is IROpcode.RETURN:
        if len(operands) != function.result_width or tuple(
            registers[operand] for operand in operands
        ) != function.result_types:
            _unsupported(function, block_name, instruction, "return value")
        return
    _unsupported(function, block_name, instruction, "opcode")


def _translate_function(
    function: IRFunction,
    function_index: int,
    functions: dict[str, IRFunction],
    static_string_symbols: dict[str, str],
) -> list[str]:
    linkage = "export " if function.exported or function.name == "main" else ""
    result_type = (
        f"{_qbe_type(function.return_type)} "
        if function.result_width == 1
        else ""
    )
    parameters = [
        f"{_qbe_type(parameter.type)} %r{parameter.register}"
        for parameter in function.parameters
    ]
    if function.result_width > 1:
        parameters.insert(0, "l %s3_sret")
    lines = [
        f"{linkage}function {result_type}${function.name}({', '.join(parameters)}) {{"
    ]
    block_names = {block.name: f"b{index}" for index, block in enumerate(function.blocks)}
    sret_call_slots = {
        (block.name, instruction_index): (
            f"%s3_f{function_index}_call_result_b{block_index}_i{instruction_index}",
            functions[instruction.callee].result_width,
        )
        for block_index, block in enumerate(function.blocks)
        for instruction_index, instruction in enumerate(block.instructions)
        if instruction.opcode is IROpcode.CALL
        and instruction.callee in functions
        and functions[instruction.callee].result_width > 1
    }
    memory_pointers = {
        memory.index: f"%s3_f{function_index}_memory_{memory.index}"
        for memory in function.memory_objects
    }
    addressed_owners = {
        instruction.operands[0]
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode is IROpcode.ADDRESS_OF
    }
    reference_slots = {
        register: (
            f"%s3_f{function_index}_"
            f"{_QBE_REFERENCE_OWNER_NAMES[_register_type(function, register)]}_slot_{register}"
        )
        for register in addressed_owners
    }
    failure_return_type = (
        function.return_type if function.result_width == 1 else None
    )
    temporary_index = 0
    for block_index, block in enumerate(function.blocks):
        lines.append(f"@{block_names[block.name]}")
        if block_index == 0:
            for memory in function.memory_objects:
                lines.append(
                    f"\t{memory_pointers[memory.index]} =l alloc8 {memory.length * 8}"
                )
            for slot in reference_slots.values():
                lines.append(f"\t{slot} =l alloc8 8")
            for slot, result_width in sret_call_slots.values():
                lines.append(
                    f"\t{slot} =l alloc8 {result_width * 8}"
                )
            for parameter in function.parameters:
                if parameter.register in reference_slots:
                    lines.append(
                        f"\tstorel %r{parameter.register}, "
                        f"{reference_slots[parameter.register]}"
                    )
        for instruction_index, instruction in enumerate(block.instructions):
            op = instruction.opcode
            result = instruction.result
            args = instruction.operands
            if op is IROpcode.CONST:
                assert result is not None and instruction.immediate is not None
                result_type = _register_type(function, result)
                value = _format_constant(instruction.immediate, result_type)
                lines.append(f"\t%r{result} ={_qbe_type(result_type)} copy {value}")
            elif op is IROpcode.CONST_STR:
                assert result is not None and instruction.static_string is not None
                lines.append(
                    f"\t%r{result} =l copy ${static_string_symbols[instruction.static_string]}"
                )
            elif op is IROpcode.MOVE:
                assert result is not None
                result_type = _register_type(function, result)
                lines.append(
                    f"\t%r{result} ={_qbe_type(result_type)} copy %r{args[0]}"
                )
            elif op is IROpcode.INVERT:
                assert result is not None
                result_type = _register_type(function, result)
                if result_type is IRType.I64:
                    _emit_i64_negation(
                        lines, function_index, failure_return_type, result, args[0]
                    )
                else:
                    lines.append(
                        f"\t%r{result} ={_qbe_type(result_type)} neg %r{args[0]}"
                    )
            elif op in {
                IROpcode.ADD,
                IROpcode.NUMERIC_DIFFERENCE,
                IROpcode.MULTIPLY,
                IROpcode.DIVIDE,
            }:
                assert result is not None
                result_type = _register_type(function, result)
                if result_type is IRType.I64:
                    emit_i64 = {
                        IROpcode.ADD: _emit_i64_add,
                        IROpcode.NUMERIC_DIFFERENCE: _emit_i64_sub,
                        IROpcode.MULTIPLY: _emit_i64_mul,
                        IROpcode.DIVIDE: _emit_i64_div,
                    }[op]
                    emit_i64(
                        lines,
                        function_index,
                        failure_return_type,
                        result,
                        args[0],
                        args[1],
                    )
                elif result_type is IRType.F64:
                    qbe_op = {
                        IROpcode.ADD: "add",
                        IROpcode.NUMERIC_DIFFERENCE: "sub",
                        IROpcode.MULTIPLY: "mul",
                        IROpcode.DIVIDE: "div",
                    }[op]
                    lines.append(
                        f"\t%r{result} =d {qbe_op} %r{args[0]}, %r{args[1]}"
                    )
                else:
                    _emit_balanced_add(
                        lines,
                        function_index,
                        failure_return_type,
                        result,
                        args[0],
                        args[1],
                        result_type,
                    )
            elif op is IROpcode.RELATE:
                assert result is not None and instruction.immediate is not None
                operand_type = _register_type(function, args[0])
                predicate = _qbe_predicate(int(instruction.immediate), operand_type)
                compare_name = _temporary(function_index, temporary_index, "rel")
                temporary_index += 1
                lines.append(
                    f"\t{compare_name} =l {predicate} %r{args[0]}, %r{args[1]}"
                )
                # QBE comparisons return 1/0; S3 RELATE returns -1/0.
                lines.append(f"\t%r{result} =l sub 0, {compare_name}")
            elif op is IROpcode.COMPARE:
                assert result is not None
                operand_type = _register_type(function, args[0])
                suffix = _comparison_suffix(operand_type)
                less = _temporary(function_index, temporary_index, "cmp_less")
                nonless_label = _label(function_index, temporary_index, "cmp_nonless")
                less_label = _label(function_index, temporary_index, "cmp_lt")
                greater_label = _label(function_index, temporary_index, "cmp_gt")
                equal_label = _label(function_index, temporary_index, "cmp_eq")
                join_label = _label(function_index, temporary_index, "cmp_join")
                greater = _temporary(function_index, temporary_index, "cmp_greater")
                temporary_index += 1
                lines.extend(
                    [
                        f"\t{less} =l {suffix[0]} %r{args[0]}, %r{args[1]}",
                        f"\tjnz {less}, @{less_label}, @{nonless_label}",
                        f"@{less_label}",
                        f"\tjmp @{join_label}",
                        f"@{nonless_label}",
                        f"\t{greater} =l {suffix[1]} %r{args[0]}, %r{args[1]}",
                        f"\tjnz {greater}, @{greater_label}, @{equal_label}",
                        f"@{greater_label}",
                        f"\tjmp @{join_label}",
                        f"@{equal_label}",
                        f"\tjmp @{join_label}",
                        f"@{join_label}",
                        f"\t%r{result} =l phi @{less_label} -1, @{equal_label} 0, @{greater_label} 1",
                    ]
                )
            elif op is IROpcode.CONVERT:
                assert result is not None
                source_type = _register_type(function, args[0])
                result_type = _register_type(function, result)
                if source_type is IRType.I64 and result_type is IRType.TRYTE:
                    _emit_range_guard(
                        lines,
                        function_index,
                        result,
                        failure_return_type,
                        args[0],
                        _TRYTE_MIN,
                        _TRYTE_MAX,
                        "overflow",
                    )
                if result_type is IRType.F64:
                    lines.append(f"\t%r{result} =d sltof %r{args[0]}")
                else:
                    lines.append(
                        f"\t%r{result} ={_qbe_type(result_type)} copy %r{args[0]}"
                    )
            elif op in {IROpcode.MINIMUM, IROpcode.MAXIMUM}:
                assert result is not None
                result_type = _register_type(function, result)
                if result_type is IRType.TRIT:
                    _emit_trit_extreme(
                        lines,
                        function_index,
                        result,
                        args[0],
                        args[1],
                        op is IROpcode.MINIMUM,
                    )
                else:
                    _emit_tryte_extreme(
                        lines,
                        function_index,
                        result,
                        args[0],
                        args[1],
                        op is IROpcode.MINIMUM,
                    )
            elif op is IROpcode.CALL:
                assert instruction.callee is not None
                callee = functions.get(instruction.callee)
                if callee is None:
                    parameter_types = DYNAMIC_BUILTIN_SIGNATURES[
                        instruction.callee
                    ][0]
                    callee_name = _QBE_DYNAMIC_CONTAINER_RUNTIME_SYMBOLS.get(
                        instruction.callee, instruction.callee
                    )
                else:
                    parameter_types = tuple(
                        parameter.type for parameter in callee.parameters
                    )
                    callee_name = callee.name
                if callee is not None and callee.result_width > 1:
                    slot, result_width = sret_call_slots[(block.name, instruction_index)]
                    assert result_width == callee.result_width
                    call_arguments = [f"l {slot}"]
                    call_arguments.extend(
                        f"{_qbe_type(parameter_type)} %r{register}"
                        for parameter_type, register in zip(
                            parameter_types, args, strict=True
                        )
                    )
                    lines.append(
                        f"\tcall ${callee_name}({', '.join(call_arguments)})"
                    )
                    for cell_index, result_register in enumerate(instruction.results):
                        cell_type = callee.result_types[cell_index]
                        pointer = slot
                        if cell_index:
                            pointer = _temporary(
                                function_index, temporary_index, "sret_result_ptr"
                            )
                            temporary_index += 1
                            lines.append(
                                f"\t{pointer} =l add {slot}, {cell_index * 8}"
                            )
                        qbe_type = _qbe_type(cell_type)
                        lines.append(
                            f"\t%r{result_register} ={qbe_type} "
                            f"load{qbe_type} {pointer}"
                        )
                else:
                    call_arguments = ", ".join(
                        f"{_qbe_type(parameter_type)} %r{register}"
                        for parameter_type, register in zip(
                            parameter_types, args, strict=True
                        )
                    )
                    call = f"call ${callee_name}({call_arguments})"
                    if result is None:
                        lines.append(f"\t{call}")
                    else:
                        result_type = _register_type(function, result)
                        if callee is None and result_type is IRType.TRIT:
                            raw_result = _temporary(
                                function_index, temporary_index, "dynamic_trit_result"
                            )
                            temporary_index += 1
                            lines.extend(
                                [
                                    f"\t{raw_result} =w {call}",
                                    f"\t%r{result} =l extsw {raw_result}",
                                ]
                            )
                        elif callee is None and instruction.callee in {
                            "tryte_vector_get",
                            "tryte_vector_pop",
                        }:
                            raw_result = _temporary(
                                function_index, temporary_index, "tryte_vector_result"
                            )
                            temporary_index += 1
                            lines.extend(
                                [
                                    f"\t{raw_result} =l {call}",
                                    f"\t%r{result} =l extsh {raw_result}",
                                ]
                            )
                        else:
                            lines.append(
                                f"\t%r{result} ={_qbe_type(result_type)} {call}"
                            )
            elif op in {IROpcode.LOAD, IROpcode.STORE}:
                memory = _memory_object(function, instruction.memory)
                index = args[0]
                pointer = _temporary(function_index, temporary_index, "memory_ptr")
                temporary_index += 1
                _emit_memory_address(
                    lines,
                    function_index,
                    temporary_index,
                    failure_return_type,
                    index,
                    memory.length,
                    memory_pointers[memory.index],
                    pointer,
                )
                if op is IROpcode.LOAD:
                    assert result is not None
                    value_type = _register_type(function, result)
                    lines.append(
                        f"\t%r{result} ={_qbe_type(value_type)} "
                        f"load{_qbe_type(value_type)} {pointer}"
                    )
                else:
                    value_type = _register_type(function, args[1])
                    lines.append(
                        f"\tstore{_qbe_type(value_type)} %r{args[1]}, {pointer}"
                    )
            elif op is IROpcode.ADDRESS_OF:
                assert result is not None
                lines.append(
                    f"\t%r{result} =l copy {reference_slots[args[0]]}"
                )
            elif op is IROpcode.JUMP:
                lines.append(f"\tjmp @{block_names[instruction.targets[0]]}")
            elif op is IROpcode.BRANCH3:
                assert len(args) == 1
                negative = _temporary(function_index, temporary_index, "branch_neg")
                zero = _temporary(function_index, temporary_index, "branch_zero")
                zero_label = _label(function_index, temporary_index, "branch_check_zero")
                temporary_index += 1
                lines.extend(
                    [
                        f"\t{negative} =l ceql %r{args[0]}, -1",
                        f"\tjnz {negative}, @{block_names[instruction.targets[0]]}, @{zero_label}",
                        f"@{zero_label}",
                        f"\t{zero} =l ceql %r{args[0]}, 0",
                        f"\tjnz {zero}, @{block_names[instruction.targets[1]]}, @{block_names[instruction.targets[2]]}",
                    ]
                )
            elif op is IROpcode.RETURN:
                if function.result_width == 1:
                    lines.append(f"\tret %r{args[0]}")
                else:
                    for cell_index, register in enumerate(args):
                        cell_type = function.result_types[cell_index]
                        pointer = "%s3_sret"
                        if cell_index:
                            pointer = _temporary(
                                function_index, temporary_index, "sret_return_ptr"
                            )
                            temporary_index += 1
                            lines.append(
                                f"\t{pointer} =l add %s3_sret, {cell_index * 8}"
                            )
                        qbe_type = _qbe_type(cell_type)
                        lines.append(
                            f"\tstore{qbe_type} %r{register}, {pointer}"
                        )
                    lines.append("\tret")
            else:
                raise AssertionError(f"validated opcode was not translated: {op}")
            for result_register in instruction.results:
                if result_register not in reference_slots:
                    continue
                lines.append(
                    f"\tstorel %r{result_register}, "
                    f"{reference_slots[result_register]}"
                )
        if block_index == 0 and block.instructions[-1].opcode not in {
            IROpcode.RETURN,
            IROpcode.JUMP,
            IROpcode.BRANCH3,
        }:
            raise AssertionError("verified S3 block has no terminator")
    lines.append("}")
    return lines


def _qbe_type(type_: IRType) -> str:
    try:
        return _QBE_TYPES[type_]
    except KeyError as error:
        raise QBETranslationError(f"unsupported S3 type {type_.value}") from error


def _static_string_symbols(module: IRModule) -> dict[str, str]:
    occupied = {function.name for function in module.functions}
    occupied.update(_QBE_DYNAMIC_CONTAINER_RUNTIME_SYMBOLS.values())
    symbols: dict[str, str] = {}
    for entry in module.static_strings:
        symbol = f"s3_qbe_static_{entry.id}"
        while symbol in occupied:
            symbol = f"_{symbol}"
        symbols[entry.id] = symbol
        occupied.add(symbol)
    return symbols


def _emit_static_string_data(
    module: IRModule, symbols: dict[str, str]
) -> list[str]:
    lines: list[str] = []
    for entry in module.static_strings:
        encoded = (*entry.utf8_bytes, 0)
        fields = ", ".join(f"b {byte}" for byte in encoded)
        lines.append(f"data ${symbols[entry.id]} = {{ {fields} }}")
    return lines


def _failure_return_value(type_: IRType) -> str:
    return "d_0.0" if type_ is IRType.F64 else "0"


def _memory_object(function: IRFunction, index: int | None):
    if index is None:
        raise QBETranslationError(
            f"function '{function.name}' memory operation has no memory identity"
        )
    for memory in function.memory_objects:
        if memory.index == index:
            return memory
    raise QBETranslationError(
        f"function '{function.name}' references missing memory m{index}"
    )


def _emit_memory_address(
    lines: list[str],
    function_index: int,
    sequence: int,
    return_type: IRType | None,
    index: int,
    length: int,
    base: str,
    pointer: str,
) -> None:
    stem = f"s3_f{function_index}_mem_{sequence}"
    negative = f"%{stem}_negative"
    high = f"%{stem}_high"
    fail_label = _label(function_index, sequence, "fail_bounds")
    check_high_label = _label(function_index, sequence, "check_bounds_high")
    ok_label = _label(function_index, sequence, "bounds_ok")
    lines.extend(
        [
            f"\t{negative} =l csltl %r{index}, 0",
            f"\tjnz {negative}, @{fail_label}, @{check_high_label}",
            f"@{check_high_label}",
            f"\t{high} =l csgel %r{index}, {length}",
            f"\tjnz {high}, @{fail_label}, @{ok_label}",
        ]
    )
    _emit_failure_body(lines, function_index, sequence, return_type, "bounds")
    offset = f"%{stem}_offset"
    lines.extend(
        [
            f"@{ok_label}",
            f"\t{offset} =l mul %r{index}, 8",
            f"\t{pointer} =l add {base}, {offset}",
        ]
    )


def _failure_label(function_index: int, result: int, category: str) -> str:
    return _label(function_index, result, f"fail_{category}")


def _emit_failure_body(
    lines: list[str],
    function_index: int,
    result: int,
    return_type: IRType | None,
    category: str,
) -> None:
    label = _failure_label(function_index, result, category)
    lines.extend([f"@{label}", f"\tcall $s3_qbe_fail_{category}()"])
    if return_type is None:
        lines.append("\tret")
    else:
        lines.append(f"\tret {_failure_return_value(return_type)}")


def _emit_i64_add(
    lines: list[str], function_index: int, return_type: IRType | None, result: int, left: int, right: int
) -> None:
    stem = f"s3_f{function_index}_r{result}"
    label = _failure_label(function_index, result, "overflow")
    xor_inputs, xor_result = f"%{stem}_xor_inputs", f"%{stem}_xor_result"
    same_sign, overflow_bits, overflow = (
        f"%{stem}_same_sign",
        f"%{stem}_overflow_bits",
        f"%{stem}_overflow",
    )
    lines.extend(
        [
            f"\t%{stem}_sum =l add %r{left}, %r{right}",
            f"\t{xor_inputs} =l xor %r{left}, %r{right}",
            f"\t{xor_result} =l xor %r{left}, %{stem}_sum",
            f"\t{same_sign} =l xor {xor_inputs}, -1",
            f"\t{overflow_bits} =l and {same_sign}, {xor_result}",
            f"\t{overflow} =l csltl {overflow_bits}, 0",
            f"\tjnz {overflow}, @{label}, @{label}_ok",
        ]
    )
    _emit_failure_body(lines, function_index, result, return_type, "overflow")
    lines.extend([f"@{label}_ok", f"\t%r{result} =l copy %{stem}_sum"])


def _emit_i64_sub(
    lines: list[str], function_index: int, return_type: IRType | None, result: int, left: int, right: int
) -> None:
    stem = f"s3_f{function_index}_r{result}"
    label = _failure_label(function_index, result, "overflow")
    xor_inputs, xor_result = f"%{stem}_xor_inputs", f"%{stem}_xor_result"
    overflow_bits, overflow = f"%{stem}_overflow_bits", f"%{stem}_overflow"
    lines.extend(
        [
            f"\t%{stem}_difference =l sub %r{left}, %r{right}",
            f"\t{xor_inputs} =l xor %r{left}, %r{right}",
            f"\t{xor_result} =l xor %r{left}, %{stem}_difference",
            f"\t{overflow_bits} =l and {xor_inputs}, {xor_result}",
            f"\t{overflow} =l csltl {overflow_bits}, 0",
            f"\tjnz {overflow}, @{label}, @{label}_ok",
        ]
    )
    _emit_failure_body(lines, function_index, result, return_type, "overflow")
    lines.extend([f"@{label}_ok", f"\t%r{result} =l copy %{stem}_difference"])


def _emit_i64_mul(
    lines: list[str], function_index: int, return_type: IRType | None, result: int, left: int, right: int
) -> None:
    stem = f"s3_f{function_index}_r{result}"
    failure, zero, quotient = (
        _failure_label(function_index, result, "overflow"),
        _label(function_index, result, "mul_zero"),
        _label(function_index, result, "mul_check_quotient"),
    )
    lines.extend(
        [
            f"\t%{stem}_product =l mul %r{left}, %r{right}",
            f"\t%{stem}_left_negone =l ceql %r{left}, -1",
            f"\t%{stem}_right_min =l ceql %r{right}, {_I64_MIN}",
            f"\t%{stem}_dangerous_division =l and %{stem}_left_negone, %{stem}_right_min",
            f"\tjnz %{stem}_dangerous_division, @{failure}, @{zero}_check",
        ]
    )
    _emit_failure_body(lines, function_index, result, return_type, "overflow")
    lines.extend(
        [
            f"@{zero}_check",
            f"\t%{stem}_left_zero =l ceql %r{left}, 0",
            f"\tjnz %{stem}_left_zero, @{zero}, @{quotient}",
            f"@{quotient}",
            f"\t%{stem}_product_quotient =l div %{stem}_product, %r{left}",
            f"\t%{stem}_quotient_mismatch =l cnel %{stem}_product_quotient, %r{right}",
            f"\tjnz %{stem}_quotient_mismatch, @{failure}, @{zero}",
        ]
    )
    lines.extend([f"@{zero}", f"\t%r{result} =l copy %{stem}_product"])


def _emit_i64_div(
    lines: list[str], function_index: int, return_type: IRType | None, result: int, left: int, right: int
) -> None:
    stem = f"s3_f{function_index}_r{result}"
    zero_label = _failure_label(function_index, result, "division_by_zero")
    overflow_label = _failure_label(function_index, result, "overflow")
    check_label = _label(function_index, result, "div_check_overflow")
    safe_label = _label(function_index, result, "div_safe")
    lines.extend(
        [
            f"\t%{stem}_divisor_zero =l ceql %r{right}, 0",
            f"\tjnz %{stem}_divisor_zero, @{zero_label}, @{check_label}",
        ]
    )
    _emit_failure_body(lines, function_index, result, return_type, "division_by_zero")
    lines.extend(
        [
            f"@{check_label}",
            f"\t%{stem}_dividend_min =l ceql %r{left}, {_I64_MIN}",
            f"\t%{stem}_divisor_negone =l ceql %r{right}, -1",
            f"\t%{stem}_div_overflow =l and %{stem}_dividend_min, %{stem}_divisor_negone",
            f"\tjnz %{stem}_div_overflow, @{overflow_label}, @{safe_label}",
        ]
    )
    _emit_failure_body(lines, function_index, result, return_type, "overflow")
    lines.extend(
        [
            f"@{safe_label}",
            f"\t%r{result} =l div %r{left}, %r{right}",
        ]
    )


def _emit_i64_negation(
    lines: list[str], function_index: int, return_type: IRType | None, result: int, operand: int
) -> None:
    stem = f"s3_f{function_index}_r{result}"
    label = _failure_label(function_index, result, "overflow")
    lines.extend(
        [
            f"\t%{stem}_is_min =l ceql %r{operand}, {_I64_MIN}",
            f"\tjnz %{stem}_is_min, @{label}, @{label}_ok",
        ]
    )
    _emit_failure_body(lines, function_index, result, return_type, "overflow")
    lines.extend([f"@{label}_ok", f"\t%r{result} =l neg %r{operand}"])


def _emit_range_guard(
    lines: list[str],
    function_index: int,
    result: int,
    return_type: IRType | None,
    operand: int,
    minimum: int,
    maximum: int,
    category: str,
) -> None:
    stem = f"s3_f{function_index}_r{result}"
    label = _failure_label(function_index, result, category)
    lines.extend(
        [
            f"\t%{stem}_below_min =l csltl %r{operand}, {minimum}",
            f"\t%{stem}_above_max =l csgtl %r{operand}, {maximum}",
            f"\t%{stem}_outside_range =l or %{stem}_below_min, %{stem}_above_max",
            f"\tjnz %{stem}_outside_range, @{label}, @{label}_ok",
        ]
    )
    _emit_failure_body(lines, function_index, result, return_type, category)
    lines.append(f"@{label}_ok")


def _emit_balanced_add(
    lines: list[str],
    function_index: int,
    return_type: IRType | None,
    result: int,
    left: int,
    right: int,
    type_: IRType,
) -> None:
    minimum, maximum = (
        (_TRIT_MIN, _TRIT_MAX) if type_ is IRType.TRIT else (_TRYTE_MIN, _TRYTE_MAX)
    )
    stem = f"s3_f{function_index}_r{result}"
    label = _failure_label(function_index, result, "overflow")
    lines.extend(
        [
            f"\t%{stem}_sum =l add %r{left}, %r{right}",
            f"\t%{stem}_below_min =l csltl %{stem}_sum, {minimum}",
            f"\t%{stem}_above_max =l csgtl %{stem}_sum, {maximum}",
            f"\t%{stem}_outside_range =l or %{stem}_below_min, %{stem}_above_max",
            f"\tjnz %{stem}_outside_range, @{label}, @{label}_ok",
        ]
    )
    _emit_failure_body(lines, function_index, result, return_type, "overflow")
    lines.extend([f"@{label}_ok", f"\t%r{result} =l copy %{stem}_sum"])


def _emit_trit_extreme(
    lines: list[str],
    function_index: int,
    result: int,
    left: int,
    right: int,
    minimum: bool,
) -> None:
    stem = f"s3_f{function_index}_r{result}"
    take_left = _label(function_index, result, "trit_extreme_left")
    take_right = _label(function_index, result, "trit_extreme_right")
    join = _label(function_index, result, "trit_extreme_join")
    predicate = "csltl" if minimum else "csgtl"
    lines.extend(
        [
            f"\t%{stem}_select_left =l {predicate} %r{left}, %r{right}",
            f"\tjnz %{stem}_select_left, @{take_left}, @{take_right}",
            f"@{take_left}",
            f"\tjmp @{join}",
            f"@{take_right}",
            f"\tjmp @{join}",
            f"@{join}",
            f"\t%r{result} =l phi @{take_left} %r{left}, @{take_right} %r{right}",
        ]
    )


def _emit_tryte_extreme(
    lines: list[str],
    function_index: int,
    result: int,
    left: int,
    right: int,
    minimum: bool,
) -> None:
    stem = f"s3_f{function_index}_r{result}"
    left_value, right_value = f"%{stem}_left_value_0", f"%{stem}_right_value_0"
    lines.extend(
        [
            f"\t{left_value} =l copy %r{left}",
            f"\t{right_value} =l copy %r{right}",
        ]
    )
    digits: list[str] = []
    for position in range(6):
        next_left, next_right = (
            f"%{stem}_left_value_{position + 1}",
            f"%{stem}_right_value_{position + 1}",
        )
        left_digit = _emit_balanced_digit(lines, stem, "left", position, left_value, next_left)
        right_digit = _emit_balanced_digit(lines, stem, "right", position, right_value, next_right)
        take_left = _label(function_index, result * 6 + position, "tryte_min_left")
        take_right = _label(function_index, result * 6 + position, "tryte_min_right")
        join = _label(function_index, result * 6 + position, "tryte_min_join")
        predicate = "csltl" if minimum else "csgtl"
        selected = f"%{stem}_digit_{position}"
        lines.extend(
            [
                f"\t%{stem}_select_{position} =l {predicate} {left_digit}, {right_digit}",
                f"\tjnz %{stem}_select_{position}, @{take_left}, @{take_right}",
                f"@{take_left}",
                f"\tjmp @{join}",
                f"@{take_right}",
                f"\tjmp @{join}",
                f"@{join}",
                f"\t{selected} =l phi @{take_left} {left_digit}, @{take_right} {right_digit}",
            ]
        )
        digits.append(selected)
        left_value, right_value = next_left, next_right
    accumulated = "0"
    for position, digit in enumerate(digits):
        term = f"%{stem}_term_{position}"
        total = f"%{stem}_total_{position}"
        lines.append(f"\t{term} =l mul {digit}, {3 ** position}")
        lines.append(f"\t{total} =l add {accumulated}, {term}")
        accumulated = total
    lines.append(f"\t%r{result} =l copy {accumulated}")


def _emit_balanced_digit(
    lines: list[str], stem: str, side: str, position: int, current: str, next_value: str
) -> str:
    quotient = f"%{stem}_{side}_quotient_{position}"
    remainder = f"%{stem}_{side}_remainder_{position}"
    plus_two = f"%{stem}_{side}_plus_two_{position}"
    minus_two = f"%{stem}_{side}_minus_two_{position}"
    carry = f"%{stem}_{side}_carry_{position}"
    correction = f"%{stem}_{side}_correction_{position}"
    digit = f"%{stem}_{side}_digit_{position}"
    lines.extend(
        [
            f"\t{quotient} =l div {current}, 3",
            f"\t{remainder} =l rem {current}, 3",
            f"\t{plus_two} =l ceql {remainder}, 2",
            f"\t{minus_two} =l ceql {remainder}, -2",
            f"\t{carry} =l sub {plus_two}, {minus_two}",
            f"\t{correction} =l mul {carry}, 3",
            f"\t{digit} =l sub {remainder}, {correction}",
            f"\t{next_value} =l add {quotient}, {carry}",
        ]
    )
    return digit


def _register_type(function: IRFunction, register: int) -> IRType:
    for item in function.registers:
        if item.index == register:
            return item.type
    raise QBETranslationError(
        f"function '{function.name}' references missing register r{register}"
    )


def _result_type(function: IRFunction, instruction: IRInstruction) -> IRType:
    if instruction.result is None:
        _unsupported(function, "?", instruction, "missing result")
    return _register_type(function, instruction.result)


def _format_constant(value: int | float, type_: IRType) -> str:
    if type_ is IRType.F64:
        return "d_" + repr(float(value))
    return str(int(value))


def _comparison_suffix(type_: IRType) -> tuple[str, str]:
    if type_ in {IRType.I64, IRType.TRIT, IRType.TRYTE}:
        return "csltl", "csgtl"
    if type_ is IRType.F64:
        return "cltd", "cgtd"
    raise QBETranslationError(f"comparison for {type_.value} is outside QBE oracle V5")


def _qbe_predicate(relation: int, type_: IRType) -> str:
    names = {0: "ceq", 1: "cne", 2: "clt", 3: "cle", 4: "cgt", 5: "cge"}
    if relation not in names:
        raise QBETranslationError(f"unknown S3 relation code {relation}")
    suffix = "l" if type_ in {IRType.I64, IRType.TRIT, IRType.TRYTE} else "d" if type_ is IRType.F64 else None
    if suffix is None:
        raise QBETranslationError(f"relation for {type_.value} is outside QBE oracle V5")
    if type_ in {IRType.I64, IRType.TRIT, IRType.TRYTE} and relation in {2, 3, 4, 5}:
        names.update({2: "cslt", 3: "csle", 4: "csgt", 5: "csge"})
    return names[relation] + suffix


def _temporary(function_index: int, index: int, stem: str) -> str:
    return f"%s3_f{function_index}_{stem}_{index}"


def _label(function_index: int, index: int, stem: str) -> str:
    return f"s3_f{function_index}_{stem}_{index}"


def _unsupported(
    function: IRFunction,
    block: str,
    instruction: IRInstruction,
    reason: str,
) -> None:
    op = instruction.opcode.value if isinstance(instruction.opcode, IROpcode) else instruction.opcode
    raise QBETranslationError(
        f"function '{function.name}' block '{block}': {reason} is outside "
        f"QBE oracle V5 (opcode {op})"
    )
