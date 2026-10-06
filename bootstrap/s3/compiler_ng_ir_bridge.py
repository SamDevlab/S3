"""Structural decoder for the versioned S3C-NG integer-event interchange.

Versions 1-5 are flat sequences of signed-i64 records ``(kind, a, b, c, d, e, f, g)``.
Kind 0 declares ``(version, record_width, flags=0, 0, 0, 0, 0)``. Kind 1 is a
function ``(index, return_type, parameter_count, name_start, name_end,
result_width, flags)``; kind 2 is a parameter ``(function, ordinal, type,
register, name_start, name_end, 0)``. Kinds 3, 7, and 9 declare registers,
memory objects, and ordered block IDs. Kind 4 is an instruction; kinds 6, 8,
10, and 11 attach call arguments, store-initialization flags, block ownership,
and control-flow targets. Kind 5 closes a function. Names use absolute UTF-8
byte spans into the original source. Function flag bits 0/1 mean external and
exported. Block ID 0 is the canonical entry block. V1 accepts scalar type codes
1-4; V2 adds bytes and text as codes 5 and 6. V3 adds ordered type-descriptor
records (kinds 12-14) and uses descriptor IDs in type fields. V4 adds aggregate
field loads (opcode 14) followed by kind 15 carrying the field-name span end.
V5 adds kind 16 after a CALL's arguments for an explicitly selected scalar
``vector_new<T>`` runtime builtin and its element type descriptor ID.
The decoder only
validates descriptor structure and maps runtime-representable categories; it
does not resolve source-level names or perform semantic analysis.
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


NG_IR_FORMAT_VERSION = 5
NG_IR_RECORD_WIDTH = 8

_V5_VECTOR_NEW_BUILTINS = {
    1: ("i64_vector_new", 1),
    2: ("tryte_vector_new", 3),
    3: ("f64_vector_new", 4),
}

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
_TYPE_KINDS_V3 = {
    1: IRType.I64,
    2: IRType.TRIT,
    3: IRType.TRYTE,
    4: IRType.F64,
    5: IRType.BYTES,
    6: IRType.TEXT,
    8: IRType.VECTOR,
    9: IRType.REFERENCE,
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
    14: IROpcode.AGGREGATE_FIELD_LOAD,
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
    callee_builtin: str | None = None
    reference_aggregate: str | None = None
    aggregate_field_path: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class _TypeDescriptorRecord:
    id: int
    kind: int
    module_start: int
    module_end: int
    name_start: int
    name_end: int
    element_type: int
    target_type: int
    mutable: int
    first_field: int
    field_count: int


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
        or version not in {*_TYPE_CODES_BY_VERSION, 3, 4, 5}
        or header[2] != NG_IR_RECORD_WIDTH
        or any(header[3:])
    ):
        raise NGIRDecodeError("unsupported or malformed NG IR format header")
    type_codes = _TYPE_CODES_BY_VERSION.get(version, {})

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

    type_descriptors: dict[int, _TypeDescriptorRecord] = {}
    descriptor_fields: list[tuple[int, int, int, int, int]] = []

    def type_for(code: int, context: str) -> IRType:
        if version < 3:
            try:
                return type_codes[code]
            except KeyError as exc:
                raise NGIRDecodeError(f"unknown type code {code} in {context}") from exc
        descriptor = type_descriptors.get(code)
        if descriptor is None:
            raise NGIRDecodeError(f"unknown type descriptor {code} in {context}")
        try:
            return _TYPE_KINDS_V3[descriptor.kind]
        except KeyError as exc:
            raise NGIRDecodeError(
                f"nominal type descriptor {code} must be lowered to field cells before {context}"
            ) from exc

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

    def reference_metadata(type_id: int, context: str) -> tuple[IRType | None, bool, str | None]:
        if version < 3:
            return None, False, None
        type_for(type_id, context)
        descriptor = type_descriptors[type_id]
        if descriptor.kind != 9:
            return None, False, None
        target = type_descriptors[descriptor.target_type]
        if target.kind == 7:
            aggregate = source_name(target.name_start, target.name_end, f"reference target of {context}")
            return None, bool(descriptor.mutable), aggregate
        if target.kind == 9:
            raise NGIRDecodeError(f"nested reference target is not representable in {context}")
        return type_for(target.id, f"reference target of {context}"), bool(descriptor.mutable), None

    if version >= 3:
        while cursor < len(records) and records[cursor][0] == 12:
            item = take(12, "type descriptor")
            _, type_id, kind, module_start, module_end, name_start, name_end, element_type = item
            detail = take(13, f"details of type descriptor {type_id}")
            _, detail_id, target_type, mutable, first_field, field_count, reserved0, reserved1 = detail
            if type_id != len(type_descriptors) + 1 or detail_id != type_id:
                raise NGIRDecodeError("type descriptor IDs must be contiguous and ordered")
            if kind not in range(1, 10) or any((reserved0, reserved1)):
                raise NGIRDecodeError(f"malformed type descriptor {type_id}")
            type_descriptors[type_id] = _TypeDescriptorRecord(
                type_id, kind, module_start, module_end, name_start, name_end,
                element_type, target_type, mutable, first_field, field_count,
            )
        while cursor < len(records) and records[cursor][0] == 14:
            item = take(14, "record field descriptor")
            _, owner_type, order, name_start, name_end, field_type, reserved0, reserved1 = item
            if any((reserved0, reserved1)):
                raise NGIRDecodeError("record field descriptor has nonzero reserved fields")
            descriptor_fields.append((owner_type, order, name_start, name_end, field_type))
        if not type_descriptors:
            raise NGIRDecodeError("V3 stream is missing its type descriptor table")
        for builtin_id in range(1, 7):
            descriptor = type_descriptors.get(builtin_id)
            if descriptor is None or descriptor.kind != builtin_id:
                raise NGIRDecodeError("V3 builtin type descriptors must preserve IDs 1-6")
        for type_id, descriptor in type_descriptors.items():
            if descriptor.kind <= 6:
                if (
                    descriptor.module_start, descriptor.module_end,
                    descriptor.name_start, descriptor.name_end,
                    descriptor.element_type, descriptor.target_type,
                    descriptor.mutable, descriptor.first_field, descriptor.field_count,
                ) != (-1, -1, -1, -1, -1, -1, 0, 0, 0):
                    raise NGIRDecodeError(f"malformed builtin type descriptor {type_id}")
            elif descriptor.kind == 7:
                if (
                    descriptor.module_start < 0 or descriptor.module_end <= descriptor.module_start
                    or descriptor.name_start < 0 or descriptor.name_end <= descriptor.name_start
                    or descriptor.element_type != -1 or descriptor.target_type != -1
                    or descriptor.mutable != 0 or descriptor.first_field < 0 or descriptor.field_count < 0
                ):
                    raise NGIRDecodeError(f"malformed nominal type descriptor {type_id}")
                source_name(descriptor.module_start, descriptor.module_end, f"module of nominal type {type_id}")
                source_name(descriptor.name_start, descriptor.name_end, f"nominal type {type_id}")
            elif descriptor.kind == 8:
                if (
                    descriptor.element_type <= 0 or descriptor.element_type >= type_id
                    or descriptor.element_type not in type_descriptors
                    or descriptor.target_type != -1 or descriptor.mutable != 0
                    or descriptor.first_field != 0 or descriptor.field_count != 0
                    or (
                        descriptor.module_start, descriptor.module_end,
                        descriptor.name_start, descriptor.name_end,
                    ) != (-1, -1, -1, -1)
                ):
                    raise NGIRDecodeError(f"malformed vector type descriptor {type_id}")
            else:
                if (
                    descriptor.target_type <= 0 or descriptor.target_type >= type_id
                    or descriptor.target_type not in type_descriptors
                    or descriptor.element_type != -1 or descriptor.mutable not in (0, 1)
                    or descriptor.first_field != 0 or descriptor.field_count != 0
                    or (
                        descriptor.module_start, descriptor.module_end,
                        descriptor.name_start, descriptor.name_end,
                    ) != (-1, -1, -1, -1)
                ):
                    raise NGIRDecodeError(f"malformed reference type descriptor {type_id}")
        field_orders: dict[int, int] = {}
        field_positions: dict[int, list[int]] = {}
        for field_index, (owner_type, order, name_start, name_end, field_type) in enumerate(descriptor_fields):
            owner = type_descriptors.get(owner_type)
            if owner is None or owner.kind != 7 or field_type not in type_descriptors:
                raise NGIRDecodeError(f"record field {field_index} references an invalid type descriptor")
            source_name(name_start, name_end, f"record field {field_index}")
            expected_order = field_orders.get(owner_type, 0)
            if order != expected_order:
                raise NGIRDecodeError(f"record fields for type {owner_type} are not ordered")
            field_orders[owner_type] = expected_order + 1
            field_positions.setdefault(owner_type, []).append(field_index)
        for type_id, descriptor in type_descriptors.items():
            if descriptor.kind == 7:
                positions = field_positions.get(type_id, [])
                if len(positions) != descriptor.field_count:
                    raise NGIRDecodeError(f"record field count disagrees for nominal type {type_id}")
                if positions and positions != list(range(descriptor.first_field, descriptor.first_field + descriptor.field_count)):
                    raise NGIRDecodeError(f"record first-field index disagrees for nominal type {type_id}")
                if not positions and not 0 <= descriptor.first_field <= len(descriptor_fields):
                    raise NGIRDecodeError(f"empty record first-field index is invalid for nominal type {type_id}")

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
            reference_target, reference_mutable, reference_aggregate = reference_metadata(
                type_code, f"parameter {parameter_index} of {function_name}"
            )
            parameters.append(
                IRParameter(
                    source_name(parameter_start, parameter_end, f"parameter {parameter_index} of {function_name}"),
                    register,
                    type_for(type_code, f"parameter {parameter_index} of {function_name}"),
                    reference_target=reference_target,
                    reference_mutable=reference_mutable,
                    reference_aggregate=reference_aggregate,
                )
            )

        registers: list[IRRegister] = []
        register_type_ids: list[int] = []
        while cursor < len(records) and records[cursor][0] == 3:
            item = take(3, f"register of {function_name}")
            _, owner, register_index, type_code, reserved0, reserved1, reserved2, reserved3 = item
            if owner != function_index or register_index != len(registers) or any((reserved0, reserved1, reserved2, reserved3)):
                raise NGIRDecodeError("register identities must be contiguous with zero reserved fields")
            reference_target, reference_mutable, reference_aggregate = reference_metadata(
                type_code, f"register {register_index} of {function_name}"
            )
            registers.append(
                IRRegister(
                    register_index,
                    type_for(type_code, f"register {register_index} of {function_name}"),
                    reference_target=reference_target,
                    reference_mutable=reference_mutable,
                    reference_aggregate=reference_aggregate,
                )
            )
            register_type_ids.append(type_code)

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
            callee_builtin: str | None = None
            memory_id: int | None = None
            init = False
            targets: tuple[int, ...] = ()
            reference_aggregate: str | None = None
            aggregate_field_path: tuple[str, ...] = ()
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
                if version >= 5 and operand0 == -1:
                    builtin_record = take(16, "V5 generic CALL target")
                    _, builtin_owner, builtin_instruction, builtin_id, element_type_id, *reserved = builtin_record
                    if (builtin_owner, builtin_instruction) != (function_index, instruction_index) or any(reserved):
                        raise NGIRDecodeError("malformed V5 generic CALL target identity")
                    builtin = _V5_VECTOR_NEW_BUILTINS.get(builtin_id)
                    if builtin is None:
                        raise NGIRDecodeError(f"unknown V5 generic CALL builtin ID {builtin_id}")
                    builtin_name, required_element_kind = builtin
                    if result is None or not 0 <= result < len(register_type_ids):
                        raise NGIRDecodeError("V5 vector_new result register is missing")
                    if operand_count != 1 or len(call_arguments) != 1:
                        raise NGIRDecodeError("V5 vector_new requires exactly one capacity argument")
                    vector_type = type_descriptors.get(register_type_ids[result])
                    element_type = type_descriptors.get(element_type_id)
                    capacity_register = call_arguments[0]
                    if not 0 <= capacity_register < len(register_type_ids):
                        raise NGIRDecodeError("V5 vector_new capacity register is missing")
                    capacity_type = type_descriptors.get(register_type_ids[capacity_register])
                    if (
                        vector_type is None
                        or vector_type.kind != 8
                        or vector_type.element_type != element_type_id
                        or element_type is None
                        or element_type.kind != required_element_kind
                        or capacity_type is None
                        or capacity_type.kind != 1
                    ):
                        raise NGIRDecodeError("V5 vector_new type metadata disagrees with its registers")
                    callee_index = None
                    callee_builtin = builtin_name
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
            elif opcode is IROpcode.AGGREGATE_FIELD_LOAD:
                if version < 4:
                    raise NGIRDecodeError("AGGREGATE_FIELD_LOAD requires NG IR V4")
                if result is None or operand_count != 1 or operand0 < 0 or operand1 <= 0 or immediate < 0:
                    raise NGIRDecodeError("malformed AGGREGATE_FIELD_LOAD record")
                if operand0 >= len(register_type_ids):
                    raise NGIRDecodeError("AGGREGATE_FIELD_LOAD references a missing aggregate register")
                owner_descriptor = type_descriptors.get(operand1)
                if owner_descriptor is None or owner_descriptor.kind != 7:
                    raise NGIRDecodeError("AGGREGATE_FIELD_LOAD owner must be a nominal type descriptor")
                reference_descriptor = type_descriptors.get(register_type_ids[operand0])
                if (
                    reference_descriptor is None
                    or reference_descriptor.kind != 9
                    or reference_descriptor.target_type != operand1
                ):
                    raise NGIRDecodeError("AGGREGATE_FIELD_LOAD operand must reference its declared owner type")
                field_end_record = take(15, "AGGREGATE_FIELD_LOAD field-name span")
                _, field_owner, field_instruction, field_end, *reserved = field_end_record
                if (field_owner, field_instruction) != (function_index, instruction_index) or any(reserved):
                    raise NGIRDecodeError("malformed AGGREGATE_FIELD_LOAD field-name span record")
                field_name = source_name(immediate, field_end, "AGGREGATE_FIELD_LOAD field name")
                reference_aggregate = source_name(
                    owner_descriptor.name_start,
                    owner_descriptor.name_end,
                    "AGGREGATE_FIELD_LOAD owner",
                )
                aggregate_field_path = (field_name,)
                operands = (operand0,)
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
                _InstructionRecord(
                    opcode=opcode,
                    result=result,
                    operands=operands,
                    immediate=decoded_immediate,
                    memory=memory_id,
                    initialization=init,
                    block=block_id,
                    targets=targets,
                    callee_index=callee_index,
                    callee_builtin=callee_builtin,
                    reference_aggregate=reference_aggregate,
                    aggregate_field_path=aggregate_field_path,
                )
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
            callee = record.callee_builtin
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
                    reference_aggregate=record.reference_aggregate,
                    aggregate_field_path=record.aggregate_field_path,
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
