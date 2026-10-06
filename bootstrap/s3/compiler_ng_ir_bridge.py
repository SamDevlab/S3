"""Structural decoder for the versioned S3C-NG integer-event interchange.

Versions 1 and 2 are flat sequences of signed-i64 records ``(kind, a, b, c, d, e, f, g)``.
Kind 0 declares ``(version, record_width, flags=0, 0, 0, 0, 0)``. Kind 1 is a
function ``(index, return_type, parameter_count, name_start, name_end,
result_width, flags)``; kind 2 is a parameter ``(function, ordinal, type,
register, name_start, name_end, 0)``. Kinds 3, 7, and 9 declare registers,
memory objects, and ordered block IDs. Kind 4 is an instruction; kinds 6, 8,
10, and 11 attach call arguments, store-initialization flags, block ownership,
and control-flow targets. Kind 5 closes a function. Names use absolute UTF-8
byte spans into the original source. Function flag bits 0/1 mean external and
exported. Block ID 0 is the canonical entry block. V1 accepts scalar type codes
1-4; V2 adds bytes and text as codes 5 and 6 without changing V1 semantics.
Unsupported types, opcodes, fields, or record order fail closed. The stream
carries no source locations or static strings, so those are intentionally
absent from reconstructed IR.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

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


NG_IR_FORMAT_VERSION = 2
NG_IR_RECORD_WIDTH = 8

_TYPE_CODES_V1 = {
    1: IRType.I64,
    2: IRType.TRIT,
    3: IRType.TRYTE,
    4: IRType.F64,
}
_TYPE_CODES_BY_VERSION = {
    1: _TYPE_CODES_V1,
    2: {
        **_TYPE_CODES_V1,
        5: IRType.BYTES,
        6: IRType.TEXT,
    },
}
_OPCODE_CODES = {
    1: IROpcode.CONST,
    2: IROpcode.ADD,
    3: IROpcode.NUMERIC_DIFFERENCE,
    4: IROpcode.MULTIPLY,
    5: IROpcode.DIVIDE,
    6: IROpcode.RETURN,
    7: IROpcode.CALL,
    8: IROpcode.MOVE,
    9: IROpcode.LOAD,
    10: IROpcode.STORE,
    11: IROpcode.BRANCH3,
    12: IROpcode.JUMP,
    13: IROpcode.COMPARE,
}


class NGIRDecodeError(ValueError):
    """The serialized NG IR is malformed or uses an unsupported record."""


@dataclass(frozen=True, slots=True)
class _InstructionRecord:
    opcode: IROpcode
    result: int | None
    operands: tuple[int, ...]
    immediate: int | None
    memory: int | None
    initialization: bool
    block: int
    targets: tuple[int, ...]
    callee_index: int | None = None


def decode_ng_ir_events(source: bytes, cells: Sequence[int]) -> IRModule:
    """Deserialize NG records without inferring or repairing program semantics."""

    if not isinstance(source, bytes):
        raise TypeError("source must be bytes")
    if len(cells) % NG_IR_RECORD_WIDTH:
        raise NGIRDecodeError("event stream ends in a partial record")
    records: list[tuple[int, ...]] = []
    for offset in range(0, len(cells), NG_IR_RECORD_WIDTH):
        record = tuple(cells[offset : offset + NG_IR_RECORD_WIDTH])
        if any(isinstance(value, bool) or not isinstance(value, int) for value in record):
            raise NGIRDecodeError(f"record {offset // NG_IR_RECORD_WIDTH} contains a non-integer cell")
        records.append(record)
    if not records:
        raise NGIRDecodeError("event stream is empty")

    header = records[0]
    version = header[1]
    if (
        header[0] != 0
        or version not in _TYPE_CODES_BY_VERSION
        or header[2] != NG_IR_RECORD_WIDTH
        or any(header[3:])
    ):
        raise NGIRDecodeError("unsupported or malformed NG IR format header")
    type_codes = _TYPE_CODES_BY_VERSION[version]

    cursor = 1
    raw_functions: list[dict[str, object]] = []

    def take(kind: int, context: str) -> tuple[int, ...]:
        nonlocal cursor
        if cursor >= len(records) or records[cursor][0] != kind:
            actual = "end of stream" if cursor >= len(records) else f"record kind {records[cursor][0]}"
            raise NGIRDecodeError(f"expected record kind {kind} for {context}, got {actual}")
        record = records[cursor]
        cursor += 1
        return record

    def type_for(code: int, context: str) -> IRType:
        try:
            return type_codes[code]
        except KeyError as exc:
            raise NGIRDecodeError(f"unknown type code {code} in {context}") from exc

    def source_name(start: int, end: int, context: str) -> str:
        if start < 0 or end <= start or end > len(source):
            raise NGIRDecodeError(f"invalid source-name span in {context}")
        try:
            value = source[start:end].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise NGIRDecodeError(f"source-name span is not UTF-8 in {context}") from exc
        if not value:
            raise NGIRDecodeError(f"empty source name in {context}")
        return value

    while cursor < len(records):
        header_record = take(1, "function header")
        _, function_index, return_type_code, parameter_count, name_start, name_end, result_width, flags = header_record
        if function_index != len(raw_functions):
            raise NGIRDecodeError("function indexes must be contiguous and ordered")
        if parameter_count < 0:
            raise NGIRDecodeError("negative function parameter count")
        if result_width != 1:
            raise NGIRDecodeError("this interchange version supports exactly one function result")
        if flags & ~0b11:
            raise NGIRDecodeError("unknown function flag bits")
        function_name = source_name(name_start, name_end, f"function {function_index}")
        return_type = type_for(return_type_code, f"function {function_name} return")

        parameters: list[IRParameter] = []
        for parameter_index in range(parameter_count):
            item = take(2, f"parameter {parameter_index} of {function_name}")
            _, owner, ordinal, type_code, register, parameter_start, parameter_end, reserved = item
            if owner != function_index or ordinal != parameter_index or reserved != 0:
                raise NGIRDecodeError("malformed parameter identity or reserved fields")
            parameters.append(
                IRParameter(
                    source_name(parameter_start, parameter_end, f"parameter {parameter_index} of {function_name}"),
                    register,
                    type_for(type_code, f"parameter {parameter_index} of {function_name}"),
                )
            )

        registers: list[IRRegister] = []
        while cursor < len(records) and records[cursor][0] == 3:
            item = take(3, f"register of {function_name}")
            _, owner, register_index, type_code, reserved0, reserved1, reserved2, reserved3 = item
            if owner != function_index or register_index != len(registers) or any((reserved0, reserved1, reserved2, reserved3)):
                raise NGIRDecodeError("register identities must be contiguous with zero reserved fields")
            registers.append(IRRegister(register_index, type_for(type_code, f"register {register_index} of {function_name}")))

        memories: list[IRMemoryObject] = []
        while cursor < len(records) and records[cursor][0] == 7:
            item = take(7, f"memory object of {function_name}")
            _, owner, memory_index, type_code, length, mutable, reserved0, reserved1 = item
            if owner != function_index or memory_index != len(memories) or any((reserved0, reserved1)):
                raise NGIRDecodeError("memory identities must be contiguous with zero reserved fields")
            if mutable not in (0, 1):
                raise NGIRDecodeError("memory mutability must be encoded as 0 or 1")
            memories.append(IRMemoryObject(memory_index, type_for(type_code, f"memory {memory_index} of {function_name}"), length, bool(mutable)))

        block_ids: list[int] = []
        while cursor < len(records) and records[cursor][0] == 9:
            item = take(9, f"basic block of {function_name}")
            _, owner, block_id, *reserved = item
            if owner != function_index or block_id in block_ids or block_id != len(block_ids) or any(reserved):
                raise NGIRDecodeError("block identities must be unique, contiguous, ordered, and have zero reserved fields")
            block_ids.append(block_id)

        instruction_records: list[_InstructionRecord] = []
        call_pool_length = 0
        while cursor < len(records) and records[cursor][0] == 4:
            item = take(4, f"instruction {len(instruction_records)} of {function_name}")
            _, owner, opcode_code, result_id, operand_count, operand0, operand1, immediate = item
            instruction_index = len(instruction_records)
            if owner != function_index or operand_count < 0:
                raise NGIRDecodeError("malformed instruction owner or operand count")
            try:
                opcode = _OPCODE_CODES[opcode_code]
            except KeyError as exc:
                raise NGIRDecodeError(f"unknown opcode code {opcode_code}") from exc

            result = None if result_id == -1 else result_id
            callee_index: int | None = None
            memory_id: int | None = None
            init = False
            targets: tuple[int, ...] = ()
            if opcode is IROpcode.CONST:
                if result is None or operand_count != 0 or operand0 != -1 or operand1 != -1:
                    raise NGIRDecodeError("malformed CONST record")
                operands: tuple[int, ...] = ()
                decoded_immediate: int | None = immediate
            elif opcode in {IROpcode.ADD, IROpcode.NUMERIC_DIFFERENCE, IROpcode.MULTIPLY, IROpcode.DIVIDE, IROpcode.COMPARE}:
                if result is None or operand_count != 2 or immediate != 0:
                    raise NGIRDecodeError(f"malformed {opcode.value.upper()} record")
                operands = (operand0, operand1)
                decoded_immediate = None
            elif opcode is IROpcode.RETURN:
                if result is not None or operand_count != 1 or operand1 != -1 or immediate != 0:
                    raise NGIRDecodeError("malformed RETURN record")
                operands = (operand0,)
                decoded_immediate = None
            elif opcode is IROpcode.CALL:
                if operand_count < 0 or operand1 < 0 or immediate != 0:
                    raise NGIRDecodeError("malformed CALL record")
                callee_index = operand0
                if operand1 != call_pool_length:
                    raise NGIRDecodeError("CALL argument-pool offset is not contiguous")
                call_arguments: list[int] = []
                for argument_index in range(operand_count):
                    argument = take(6, f"CALL argument {argument_index}")
                    _, argument_owner, argument_instruction, argument_ordinal, argument_register, reserved0, reserved1, reserved2 = argument
                    if (argument_owner, argument_instruction, argument_ordinal) != (function_index, instruction_index, argument_index) or any((reserved0, reserved1, reserved2)):
                        raise NGIRDecodeError("malformed CALL argument identity or reserved fields")
                    call_arguments.append(argument_register)
                call_pool_length += len(call_arguments)
                if operand1 + operand_count > call_pool_length:
                    raise NGIRDecodeError("CALL argument range is outside the serialized pool")
                operands = tuple(call_arguments)
                decoded_immediate = None
            elif opcode is IROpcode.MOVE:
                if result is None or operand_count != 1 or operand1 != -1 or immediate != 0:
                    raise NGIRDecodeError("malformed MOVE record")
                operands = (operand0,)
                decoded_immediate = None
            elif opcode is IROpcode.LOAD:
                if result is None or operand_count != 1 or immediate != 0:
                    raise NGIRDecodeError("malformed LOAD record")
                operands = (operand0,)
                memory_id = operand1
                decoded_immediate = None
            elif opcode is IROpcode.STORE:
                if result is not None or operand_count != 2:
                    raise NGIRDecodeError("malformed STORE record")
                operands = (operand0, operand1)
                memory_id = immediate
                decoded_immediate = None
            elif opcode is IROpcode.BRANCH3:
                if result is not None or operand_count != 1 or operand1 != -1 or immediate != 0:
                    raise NGIRDecodeError("malformed BRANCH3 record")
                operands = (operand0,)
                decoded_immediate = None
            elif opcode is IROpcode.JUMP:
                if result is not None or operand_count != 0 or operand0 != -1 or operand1 != -1 or immediate != 0:
                    raise NGIRDecodeError("malformed JUMP record")
                operands = ()
                decoded_immediate = None
            else:  # The explicit table above is deliberately exhaustive.
                raise NGIRDecodeError(f"unsupported opcode {opcode.value}")

            if opcode is IROpcode.STORE:
                init_record = take(8, "STORE initialization flag")
                _, init_owner, init_instruction, init_value, *reserved = init_record
                if init_owner != function_index or init_instruction != instruction_index or init_value not in (0, 1) or any(reserved):
                    raise NGIRDecodeError("malformed STORE initialization record")
                init = bool(init_value)

            block_record = take(10, "instruction block association")
            _, block_owner, block_instruction, block_id, *reserved = block_record
            if block_owner != function_index or block_instruction != instruction_index or any(reserved):
                raise NGIRDecodeError("malformed instruction block association")

            if opcode in {IROpcode.BRANCH3, IROpcode.JUMP}:
                target_record = take(11, "control-flow targets")
                _, target_owner, target_instruction, target0, target1, target2, reserved0, reserved1 = target_record
                if target_owner != function_index or target_instruction != instruction_index or reserved0 or reserved1:
                    raise NGIRDecodeError("malformed control-flow target record")
                if opcode is IROpcode.BRANCH3:
                    targets = (target0, target1, target2)
                else:
                    if any((target1, target2)):
                        raise NGIRDecodeError("JUMP contains more than one target")
                    targets = (target0,)

            instruction_records.append(
                _InstructionRecord(opcode, result, operands, decoded_immediate, memory_id, init, block_id, targets, callee_index)
            )

        end_record = take(5, f"end of function {function_name}")
        if end_record != (5, function_index, 0, 0, 0, 0, 0, 0):
            raise NGIRDecodeError("malformed function-end record")

        if len({parameter.name for parameter in parameters}) != len(parameters):
            raise NGIRDecodeError(f"duplicate parameter identity in function {function_name}")
        for parameter in parameters:
            if parameter.register < 0 or parameter.register >= len(registers):
                raise NGIRDecodeError(f"parameter register is missing in function {function_name}")
        block_set = set(block_ids)
        for instruction in instruction_records:
            if instruction.block not in block_set:
                raise NGIRDecodeError(f"instruction references missing block {instruction.block} in {function_name}")
            for register in (*instruction.operands, *((instruction.result,) if instruction.result is not None else ())):
                if register < 0 or register >= len(registers):
                    raise NGIRDecodeError(f"instruction references missing register {register} in {function_name}")
            if instruction.memory is not None and not 0 <= instruction.memory < len(memories):
                raise NGIRDecodeError(f"instruction references missing memory {instruction.memory} in {function_name}")
            if any(target not in block_set for target in instruction.targets):
                raise NGIRDecodeError(f"instruction references a missing branch target in {function_name}")

        raw_functions.append(
            {
                "name": function_name,
                "return_type": return_type,
                "parameters": tuple(parameters),
                "registers": tuple(registers),
                "memories": tuple(memories),
                "block_ids": tuple(block_ids),
                "instructions": tuple(instruction_records),
                "external": bool(flags & 0b01),
                "exported": bool(flags & 0b10),
            }
        )

    if not raw_functions:
        raise NGIRDecodeError("event stream contains no functions")
    if cursor != len(records):
        raise NGIRDecodeError("trailing records after final function")
    function_names = [str(function["name"]) for function in raw_functions]
    if len(set(function_names)) != len(function_names):
        raise NGIRDecodeError("duplicate function identity")

    functions: list[IRFunction] = []
    for function_index, raw in enumerate(raw_functions):
        name = str(raw["name"])
        block_ids = raw["block_ids"]
        block_names = {
            block_id: "entry" if block_id == 0 else f"b{block_id}"
            for block_id in block_ids
        }
        by_block: dict[int, list[IRInstruction]] = {block_id: [] for block_id in block_ids}
        for record in raw["instructions"]:
            callee = None
            if record.callee_index is not None:
                if not 0 <= record.callee_index < len(function_names):
                    raise NGIRDecodeError(f"CALL references invalid function index {record.callee_index} in {name}")
                callee = function_names[record.callee_index]
            by_block[record.block].append(
                IRInstruction(
                    opcode=record.opcode,
                    result=record.result,
                    operands=record.operands,
                    immediate=record.immediate,
                    callee=callee,
                    targets=tuple(block_names[target] for target in record.targets),
                    memory=record.memory,
                    initialization=record.initialization,
                )
            )
        return_type = raw["return_type"]
        functions.append(
            IRFunction(
                name=name,
                parameters=raw["parameters"],
                return_type=return_type,
                registers=raw["registers"],
                blocks=tuple(
                    IRBasicBlock(block_names[block_id], tuple(by_block[block_id]))
                    for block_id in block_ids
                ),
                memory_objects=raw["memories"],
                result_types=(return_type,),
                external=raw["external"],
                exported=raw["exported"],
            )
        )
    return IRModule(tuple(functions))
