"""Structural decoder for the versioned S3C-NG integer-event interchange.

Versions 1-11 are flat sequences of signed-i64 records ``(kind, a, b, c, d, e, f, g)``.
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
``vector_new<T>`` runtime builtin and its element type descriptor ID. V6 retains
that record and adds kind 17 for scalar ``vector_len<T>`` calls whose argument
register is explicitly typed as a reference to ``vector<T>``.
V7 adds opcode 15 for scalar relational operators, with relation ID 0-5 in the instruction immediate.
V8 adds kind 18 after a CALL's arguments for explicitly selected scalar
``vector_push<T>``; the record carries the builtin ID and element descriptor ID.
V9 adds kind 19/20 metadata for record-element vector builtins. V10 adds opcode
16 for address-of a register or a memory cell; the result's reference descriptor
is the authoritative target and mutability contract.
V11 adds opcode 17 for typed numeric conversion and kind 21 after CALL arguments
for a dynamic builtin target identified by an explicit source-name span. V12 adds
opcode 18 for typed reference loads. V13 adds type kind 10 for static strings and
opcode 19, whose quoted-source span is decoded into the canonical static-string
table in source order. V14 adds explicit result-cell layouts. V15 represents
record parameters as NG-emitted scalar value cells and carries each field path
explicitly in leaf-to-root record order with root-based segment ordinals; the
decoder formats those paths into canonical parameter names but does not resolve
fields or types.
V16 adds kind 23 after CALL arguments for typed scalar ``vector_get<T>`` and
``vector_set<T>`` targets.
V17 stores each RETURN's explicit result-register IDs in kind 24 records
immediately following that instruction. This preserves non-contiguous
aggregate result layouts without inserting semantic MOVE instructions.
The decoder only
validates descriptor structure and maps runtime-representable categories; it
does not resolve source-level names or perform semantic analysis.
Unsupported types, opcodes, fields, or record order fail closed. Earlier streams
carry no static-string data; V13 reconstructs only strings explicitly referenced
by CONST_STR instructions.
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
    IRStaticString,
    IRType,
)
from .static_text import StaticTextDecodeError, decode_static_text
from .vector_types import composite_vector_runtime_name_from_key


NG_IR_FORMAT_VERSION = 17
NG_IR_RECORD_WIDTH = 8

_V5_VECTOR_NEW_BUILTINS = {
    1: ("i64_vector_new", 1),
    2: ("tryte_vector_new", 3),
    3: ("f64_vector_new", 4),
}
_V6_VECTOR_LEN_BUILTINS = {
    1: ("i64_vector_len", 1),
    3: ("tryte_vector_len", 3),
    4: ("f64_vector_len", 4),
}
_V8_VECTOR_PUSH_BUILTINS = {
    1: "i64_vector_push",
    3: "tryte_vector_push",
    4: "f64_vector_push",
}
_V16_VECTOR_ACCESS_BUILTINS = {
    1: {1: "i64_vector_get", 2: "i64_vector_set"},
    3: {1: "tryte_vector_get", 2: "tryte_vector_set"},
    4: {1: "f64_vector_get", 2: "f64_vector_set"},
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
    10: IRType.STRING,
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
    15: IROpcode.RELATE,
    16: IROpcode.ADDRESS_OF,
    17: IROpcode.CONVERT,
    18: IROpcode.REFERENCE_LOAD,
    19: IROpcode.CONST_STR,
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
    reference_target: IRType | None = None
    reference_mutable: bool = False
    reference_is_slice: bool = False
    static_string_value: str | None = None
    static_string_offset: int | None = None
    results: tuple[int, ...] = ()


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
        or version not in {*_TYPE_CODES_BY_VERSION, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17}
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

    def decode_string_literal(start: int, end: int) -> str:
        if start < 0 or end <= start or end > len(source):
            raise NGIRDecodeError("CONST_STR has an invalid source span")
        raw = source[start:end]
        if len(raw) < 2 or raw[0] != 34 or raw[-1] != 34:
            raise NGIRDecodeError("CONST_STR source span is not a quoted string literal")
        escaped = False
        for unit in raw[1:-1]:
            if unit == 34 and not escaped:
                raise NGIRDecodeError("CONST_STR source span contains an unescaped quote")
            if unit == 92 and not escaped:
                escaped = True
            else:
                escaped = False
        try:
            return decode_static_text(raw[1:-1].decode("utf-8"))
        except (UnicodeDecodeError, StaticTextDecodeError) as exc:
            raise NGIRDecodeError("CONST_STR literal is not valid static text") from exc

    def module_at_source_offset(offset: int) -> str | None:
        marker = source.rfind(b"\nmodule ", 0, offset)
        line_start = marker + 1 if marker >= 0 else (0 if source.startswith(b"module ") else -1)
        if line_start < 0:
            return None
        line_end = source.find(b"\n", line_start)
        if line_end < 0:
            line_end = len(source)
        parts = source[line_start:line_end].split()
        if len(parts) != 2 or parts[0] != b"module":
            return None
        try:
            return parts[1].decode("utf-8")
        except UnicodeDecodeError as exc:
            raise NGIRDecodeError("entry module declaration is not UTF-8") from exc

    main_headers = [
        item
        for item in records
        if item[0] == 1
        and 0 <= item[4] < item[5] <= len(source)
        and source[item[4] : item[5]] == b"main"
    ]
    entry_module = (
        module_at_source_offset(main_headers[0][4]) if len(main_headers) == 1 else None
    )

    def nominal_runtime_key(type_id: int, context: str) -> str:
        descriptor = type_descriptors.get(type_id)
        if descriptor is None or descriptor.kind != 7:
            raise NGIRDecodeError(f"{context} requires a nominal type descriptor")
        module_name = source_name(
            descriptor.module_start, descriptor.module_end, f"module of {context}"
        )
        type_name = source_name(
            descriptor.name_start, descriptor.name_end, f"name of {context}"
        )
        if entry_module is None:
            raise NGIRDecodeError("cannot resolve nominal runtime identity without the entry module")
        if module_name == entry_module:
            return type_name
        return f"__s3mod_{module_name.replace('.', '_')}__type_{type_name}"

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
            if kind not in range(1, 11) or any((reserved0, reserved1)):
                raise NGIRDecodeError(f"malformed type descriptor {type_id}")
            if kind == 10 and version < 13:
                raise NGIRDecodeError("STRING type descriptor requires NG IR V13")
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
            elif descriptor.kind == 9:
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
            else:
                if (
                    version < 13
                    or (
                        descriptor.module_start, descriptor.module_end,
                        descriptor.name_start, descriptor.name_end,
                        descriptor.element_type, descriptor.target_type,
                        descriptor.mutable, descriptor.first_field, descriptor.field_count,
                    ) != (-1, -1, -1, -1, -1, -1, 0, 0, 0)
                ):
                    raise NGIRDecodeError(f"malformed string type descriptor {type_id}")
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

    def declared_value_cell_type_ids(type_id: int, active: frozenset[int] = frozenset()) -> tuple[int, ...]:
        descriptor = type_descriptors.get(type_id)
        if descriptor is None:
            raise NGIRDecodeError(f"function result references unknown type descriptor {type_id}")
        if descriptor.kind != 7:
            return (type_id,)
        if type_id in active:
            raise NGIRDecodeError(f"recursive record result layout at type descriptor {type_id}")
        active = active | {type_id}
        result: list[int] = []
        for owner_type, _order, _name_start, _name_end, field_type in descriptor_fields:
            if owner_type == type_id:
                result.extend(declared_value_cell_type_ids(field_type, active))
        if not result:
            raise NGIRDecodeError(f"record result type descriptor {type_id} has no value cells")
        return tuple(result)

    while cursor < len(records):
        header_record = take(1, "function header")
        _, function_index, return_type_code, parameter_count, name_start, name_end, result_width, flags = header_record
        if function_index != len(raw_functions):
            raise NGIRDecodeError("function indexes must be contiguous and ordered")
        if parameter_count < 0:
            raise NGIRDecodeError("negative function parameter count")
        if flags & ~0b11:
            raise NGIRDecodeError("unknown function flag bits")
        function_name = source_name(name_start, name_end, f"function {function_index}")
        if version >= 14:
            if result_width <= 0:
                raise NGIRDecodeError("V14 function result width must be positive")
            if return_type_code not in type_descriptors:
                raise NGIRDecodeError(f"function {function_name} declares an unknown result type")
            result_type_ids: list[int] = []
            for result_ordinal in range(result_width):
                result_type_record = take(22, f"result cell {result_ordinal} of {function_name}")
                _, owner, ordinal, type_id, reserved0, reserved1, reserved2, reserved3 = result_type_record
                if owner != function_index or ordinal != result_ordinal or any((reserved0, reserved1, reserved2, reserved3)):
                    raise NGIRDecodeError("malformed V14 function result-cell identity")
                if type_id not in type_descriptors:
                    raise NGIRDecodeError(f"function {function_name} result cell has an unknown type")
                result_type_ids.append(type_id)
            if tuple(result_type_ids) != declared_value_cell_type_ids(return_type_code):
                raise NGIRDecodeError(f"function {function_name} result cells disagree with its declared value layout")
            result_types = tuple(
                type_for(type_id, f"function {function_name} result cell {ordinal}")
                for ordinal, type_id in enumerate(result_type_ids)
            )
            return_type = result_types[0]
        else:
            if result_width != 1:
                raise NGIRDecodeError("this interchange version supports exactly one function result")
            result_type_ids = [return_type_code]
            return_type = type_for(return_type_code, f"function {function_name} return")
            result_types = (return_type,)

        parameters: list[IRParameter] = []
        for parameter_index in range(parameter_count):
            item = take(2, f"parameter {parameter_index} of {function_name}")
            _, owner, ordinal, type_code, register, parameter_start, parameter_end, metadata = item
            if owner != function_index or ordinal != parameter_index:
                raise NGIRDecodeError("malformed parameter identity")
            parameter_name = source_name(parameter_start, parameter_end, f"parameter {parameter_index} of {function_name}")
            if version >= 15:
                path_depth = metadata
                if path_depth < 0:
                    raise NGIRDecodeError("negative V15 parameter field-path depth")
                path_segments: list[str | None] = [None] * path_depth
                for path_ordinal in range(path_depth):
                    path_record = take(23, f"field-path segment {path_ordinal} of parameter {parameter_index}")
                    _, path_owner, path_cell, segment_ordinal, segment_start, segment_end, reserved0, reserved1 = path_record
                    if (
                        path_owner != function_index
                        or path_cell != parameter_index
                        or segment_ordinal != path_depth - path_ordinal - 1
                        or reserved0 != 0
                        or reserved1 != 0
                    ):
                        raise NGIRDecodeError("malformed V15 parameter field-path identity")
                    path_segments[segment_ordinal] = source_name(segment_start, segment_end, f"parameter {parameter_index} field path")
                if any(segment is None for segment in path_segments):
                    raise NGIRDecodeError("incomplete V15 parameter field path")
                parameter_name += "".join("__" + str(segment) for segment in path_segments)
                if register != parameter_index:
                    raise NGIRDecodeError("V15 parameter registers must occupy the leading contiguous register range")
            elif metadata != 0:
                raise NGIRDecodeError("malformed parameter reserved field")
            reference_target, reference_mutable, reference_aggregate = reference_metadata(
                type_code, f"parameter {parameter_index} of {function_name}"
            )
            parameters.append(
                IRParameter(
                    parameter_name,
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
        return_pool_length = 0
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
            if opcode is IROpcode.RELATE and version < 7:
                raise NGIRDecodeError("RELATE opcode requires NG IR format V7")

            result = None if result_id == -1 else result_id
            callee_index: int | None = None
            callee_builtin: str | None = None
            memory_id: int | None = None
            init = False
            targets: tuple[int, ...] = ()
            reference_aggregate: str | None = None
            aggregate_field_path: tuple[str, ...] = ()
            reference_target: IRType | None = None
            reference_mutable = False
            reference_is_slice = False
            static_string_value: str | None = None
            static_string_offset: int | None = None
            instruction_results: tuple[int, ...] = ()
            if opcode is IROpcode.CONST_STR:
                if version < 13:
                    raise NGIRDecodeError("CONST_STR opcode requires NG IR V13")
                if (
                    result is None
                    or not 0 <= result < len(register_type_ids)
                    or operand_count != 0
                    or immediate != 0
                ):
                    raise NGIRDecodeError("malformed CONST_STR record")
                descriptor = type_descriptors.get(register_type_ids[result])
                if descriptor is None or descriptor.kind != 10:
                    raise NGIRDecodeError("CONST_STR result must use the STRING type descriptor")
                static_string_value = decode_string_literal(operand0, operand1)
                static_string_offset = operand0
                operands: tuple[int, ...] = ()
                decoded_immediate: int | None = None
            elif opcode is IROpcode.CONST:
                if result is None or operand_count != 0 or operand0 != -1 or operand1 != -1:
                    raise NGIRDecodeError("malformed CONST record")
                operands: tuple[int, ...] = ()
                decoded_immediate: int | None = immediate
            elif opcode in {IROpcode.ADD, IROpcode.NUMERIC_DIFFERENCE, IROpcode.MULTIPLY, IROpcode.DIVIDE, IROpcode.COMPARE}:
                if result is None or operand_count != 2 or immediate != 0:
                    raise NGIRDecodeError(f"malformed {opcode.value.upper()} record")
                operands = (operand0, operand1)
                decoded_immediate = None
            elif opcode is IROpcode.RELATE:
                if result is None or operand_count != 2 or immediate not in range(6):
                    raise NGIRDecodeError("malformed RELATE record")
                operands = (operand0, operand1)
                decoded_immediate = immediate
            elif opcode is IROpcode.RETURN:
                if result is not None or immediate != 0:
                    raise NGIRDecodeError("malformed RETURN record")
                if version >= 17:
                    if (
                        operand_count != len(result_type_ids)
                        or operand_count <= 0
                        or operand0 < 0
                        or operand1 != return_pool_length
                    ):
                        raise NGIRDecodeError("V17 RETURN width or result-pool offset is malformed")
                    explicit_operands: list[int] = []
                    for result_ordinal in range(operand_count):
                        result_record = take(24, f"V17 RETURN result cell {result_ordinal}")
                        (
                            _,
                            result_owner,
                            result_instruction,
                            encoded_ordinal,
                            register_id,
                            reserved0,
                            reserved1,
                            reserved2,
                        ) = result_record
                        if (
                            result_owner != function_index
                            or result_instruction != instruction_index
                            or encoded_ordinal != result_ordinal
                            or any((reserved0, reserved1, reserved2))
                        ):
                            raise NGIRDecodeError("malformed V17 RETURN result-cell identity or reserved fields")
                        if not 0 <= register_id < len(register_type_ids):
                            raise NGIRDecodeError("V17 RETURN references a missing result register")
                        explicit_operands.append(register_id)
                    if explicit_operands[0] != operand0:
                        raise NGIRDecodeError("V17 RETURN first-register field disagrees with its explicit result cells")
                    operands = tuple(explicit_operands)
                    if tuple(register_type_ids[index] for index in operands) != tuple(result_type_ids):
                        raise NGIRDecodeError("V17 RETURN registers disagree with function result-cell types")
                    return_pool_length += len(operands)
                elif version >= 14:
                    if operand1 != -1:
                        raise NGIRDecodeError("malformed pre-V17 RETURN record")
                    if operand_count != len(result_type_ids) or operand_count <= 0 or operand0 < 0:
                        raise NGIRDecodeError("V14 RETURN width disagrees with its function signature")
                    if operand0 + operand_count > len(register_type_ids):
                        raise NGIRDecodeError("V14 RETURN result range is outside the register table")
                    operands = tuple(range(operand0, operand0 + operand_count))
                    if tuple(register_type_ids[index] for index in operands) != tuple(result_type_ids):
                        raise NGIRDecodeError("V14 RETURN registers disagree with function result-cell types")
                else:
                    if operand1 != -1:
                        raise NGIRDecodeError("malformed RETURN record")
                    if operand_count != 1:
                        raise NGIRDecodeError("malformed RETURN record")
                    operands = (operand0,)
                decoded_immediate = None
            elif opcode is IROpcode.CALL:
                if (
                    operand_count < 0
                    or operand1 < 0
                    or (
                        immediate != 0
                        and not (
                            version >= 11 and operand0 == -7
                            or version >= 14 and operand0 >= 0
                            or version >= 16 and operand0 in {-8, -9}
                        )
                    )
                ):
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
                elif version >= 6 and operand0 == -2:
                    builtin_record = take(17, "V6 generic vector_len CALL target")
                    _, builtin_owner, builtin_instruction, builtin_id, element_type_id, *reserved = builtin_record
                    if (builtin_owner, builtin_instruction) != (function_index, instruction_index) or any(reserved):
                        raise NGIRDecodeError("malformed V6 generic vector_len CALL target identity")
                    if builtin_id != 1:
                        raise NGIRDecodeError(f"unknown V6 generic CALL builtin ID {builtin_id}")
                    if result is None or not 0 <= result < len(register_type_ids):
                        raise NGIRDecodeError("V6 vector_len result register is missing")
                    if operand_count != 1 or len(call_arguments) != 1:
                        raise NGIRDecodeError("V6 vector_len requires exactly one reference argument")
                    result_type = type_descriptors.get(register_type_ids[result])
                    reference_register = call_arguments[0]
                    if not 0 <= reference_register < len(register_type_ids):
                        raise NGIRDecodeError("V6 vector_len reference register is missing")
                    reference_type = type_descriptors.get(register_type_ids[reference_register])
                    vector_type = (
                        type_descriptors.get(reference_type.target_type)
                        if reference_type is not None and reference_type.kind == 9
                        else None
                    )
                    element_type = type_descriptors.get(element_type_id)
                    builtin = _V6_VECTOR_LEN_BUILTINS.get(
                        element_type.kind if element_type is not None else -1
                    )
                    if (
                        result_type is None
                        or result_type.kind != 1
                        or reference_type is None
                        or reference_type.kind != 9
                        or vector_type is None
                        or vector_type.kind != 8
                        or vector_type.element_type != element_type_id
                        or builtin is None
                    ):
                        raise NGIRDecodeError("V6 vector_len type metadata disagrees with its registers")
                    callee_index = None
                    callee_builtin = builtin[0]
                elif version >= 8 and operand0 == -3:
                    builtin_record = take(18, "V8 generic vector_push CALL target")
                    _, builtin_owner, builtin_instruction, builtin_id, element_type_id, *reserved = builtin_record
                    if (builtin_owner, builtin_instruction) != (function_index, instruction_index) or any(reserved):
                        raise NGIRDecodeError("malformed V8 generic CALL target identity")
                    if builtin_id != 1:
                        raise NGIRDecodeError(f"unknown V8 generic CALL builtin ID {builtin_id}")
                    if immediate != 0:
                        raise NGIRDecodeError("V8 vector_push CALL instruction contains nonzero reserved immediate")
                    if operand_count != 2 or len(call_arguments) != 2:
                        raise NGIRDecodeError("V8 vector_push requires exactly two arguments")
                    result_type = (
                        type_descriptors.get(register_type_ids[result])
                        if result is not None and 0 <= result < len(register_type_ids)
                        else None
                    )
                    reference_register, value_register = call_arguments
                    if not 0 <= reference_register < len(register_type_ids) or not 0 <= value_register < len(register_type_ids):
                        raise NGIRDecodeError("V8 vector_push argument register is missing")
                    reference_type = type_descriptors.get(register_type_ids[reference_register])
                    vector_type = (
                        type_descriptors.get(reference_type.target_type)
                        if reference_type is not None and reference_type.kind == 9
                        else None
                    )
                    element_type = type_descriptors.get(element_type_id)
                    builtin_name = _V8_VECTOR_PUSH_BUILTINS.get(
                        element_type.kind if element_type is not None else -1
                    )
                    if (
                        (result is not None and (result_type is None or result_type.kind != 3))
                        or reference_type is None
                        or reference_type.kind != 9
                        or reference_type.mutable != 1
                        or vector_type is None
                        or vector_type.kind != 8
                        or vector_type.element_type != element_type_id
                        or element_type is None
                        or register_type_ids[value_register] != element_type_id
                        or builtin_name is None
                    ):
                        raise NGIRDecodeError("V8 vector_push type metadata disagrees with its registers")
                    callee_index = None
                    callee_builtin = builtin_name
                elif version >= 9 and (
                    operand0 in {-4, -5, -6}
                    or version >= 16
                    and operand0 in {-8, -9}
                    and cursor < len(records)
                    and records[cursor][0] == 19
                ):
                    target = take(19, "V9 composite vector CALL target")
                    _, target_owner, target_instruction, builtin_id, element_type_id, key_start, key_end, field_count = target
                    if (target_owner, target_instruction) != (function_index, instruction_index):
                        raise NGIRDecodeError("malformed V9 composite vector target identity")
                    expected_builtin_id = {-4: 1, -5: 2, -6: 3, -8: 4, -9: 5}[operand0]
                    if builtin_id != expected_builtin_id:
                        raise NGIRDecodeError("malformed V9 composite vector operation metadata")
                    if operand0 in {-4, -5, -6} and immediate != 0:
                        raise NGIRDecodeError("malformed V9 composite vector operation metadata")
                    element_type = type_descriptors.get(element_type_id)
                    if (
                        element_type is None
                        or element_type.kind != 7
                        or field_count <= 0
                        or key_start != element_type.name_start
                        or key_end != element_type.name_end
                    ):
                        raise NGIRDecodeError("V9 composite vector target disagrees with its nominal descriptor")
                    nominal_fields = [
                        item for item in descriptor_fields if item[0] == element_type_id
                    ]
                    if len(nominal_fields) != field_count:
                        raise NGIRDecodeError("V9 composite vector field count disagrees with its descriptor")
                    field_type_ids: list[int] = []
                    for ordinal in range(field_count):
                        field_record = take(20, f"V9 composite vector field {ordinal}")
                        _, field_owner, field_instruction, field_ordinal, field_type_id, *reserved = field_record
                        if (
                            (field_owner, field_instruction) != (function_index, instruction_index)
                            or field_ordinal != ordinal
                            or any(reserved)
                            or nominal_fields[ordinal][1] != ordinal
                            or nominal_fields[ordinal][4] != field_type_id
                        ):
                            raise NGIRDecodeError("malformed V9 composite vector field metadata")
                        field_type = type_descriptors.get(field_type_id)
                        if field_type is None or field_type.kind not in {1, 2, 3, 4}:
                            raise NGIRDecodeError("V9 composite vector uses an unsupported field type")
                        field_type_ids.append(field_type_id)

                    operation = {-4: "new", -5: "len", -6: "push", -8: "get", -9: "set"}[operand0]
                    field_codes = tuple(
                        type_for(field_type_id, "V9 composite vector field").value
                        for field_type_id in field_type_ids
                    )
                    callee_index = None
                    callee_builtin = composite_vector_runtime_name_from_key(
                        nominal_runtime_key(element_type_id, "V9 composite vector type key"),
                        field_codes,
                        operation,
                    )
                    if operand0 == -4:
                        if result is None or result >= len(register_type_ids) or operand_count != 1 or len(call_arguments) != 1:
                            raise NGIRDecodeError("V9 vector_new requires one capacity argument and a result")
                        result_descriptor = type_descriptors.get(register_type_ids[result])
                        capacity_register = call_arguments[0]
                        capacity_descriptor = (
                            type_descriptors.get(register_type_ids[capacity_register])
                            if 0 <= capacity_register < len(register_type_ids)
                            else None
                        )
                        if (
                            result_descriptor is None
                            or result_descriptor.kind != 8
                            or result_descriptor.element_type != element_type_id
                            or capacity_descriptor is None
                            or capacity_descriptor.kind != 1
                        ):
                            raise NGIRDecodeError("V9 vector_new metadata disagrees with its registers")
                    elif operand0 == -5:
                        reference_register = call_arguments[0] if len(call_arguments) == 1 else -1
                        result_descriptor = (
                            type_descriptors.get(register_type_ids[result])
                            if result is not None and 0 <= result < len(register_type_ids)
                            else None
                        )
                        reference_descriptor = (
                            type_descriptors.get(register_type_ids[reference_register])
                            if 0 <= reference_register < len(register_type_ids)
                            else None
                        )
                        vector_descriptor = (
                            type_descriptors.get(reference_descriptor.target_type)
                            if reference_descriptor is not None and reference_descriptor.kind == 9
                            else None
                        )
                        if (
                            result_descriptor is None
                            or result_descriptor.kind != 1
                            or reference_descriptor is None
                            or reference_descriptor.kind != 9
                            or vector_descriptor is None
                            or vector_descriptor.kind != 8
                            or vector_descriptor.element_type != element_type_id
                        ):
                            raise NGIRDecodeError("V9 vector_len metadata disagrees with its registers")
                    elif operand0 == -8:
                        if immediate != field_count or operand_count != 2 or result is None:
                            raise NGIRDecodeError("V16 composite vector_get result width disagrees with its record")
                        if result + field_count > len(register_type_ids):
                            raise NGIRDecodeError("V16 composite vector_get result range is outside the register table")
                        reference_register, index_register = call_arguments
                        if (
                            not 0 <= reference_register < len(register_type_ids)
                            or not 0 <= index_register < len(register_type_ids)
                        ):
                            raise NGIRDecodeError("V16 composite vector_get references a missing argument register")
                        reference_descriptor = type_descriptors.get(register_type_ids[reference_register])
                        vector_descriptor = (
                            type_descriptors.get(reference_descriptor.target_type)
                            if reference_descriptor is not None and reference_descriptor.kind == 9
                            else None
                        )
                        index_descriptor = type_descriptors.get(register_type_ids[index_register])
                        if (
                            reference_descriptor is None
                            or reference_descriptor.kind != 9
                            or vector_descriptor is None
                            or vector_descriptor.kind != 8
                            or vector_descriptor.element_type != element_type_id
                            or index_descriptor is None
                            or index_descriptor.kind != 1
                        ):
                            raise NGIRDecodeError("V16 composite vector_get metadata disagrees with its arguments")
                        if tuple(register_type_ids[result : result + field_count]) != tuple(field_type_ids):
                            raise NGIRDecodeError("V16 composite vector_get result cells disagree with its record layout")
                        instruction_results = tuple(range(result, result + field_count))
                    elif operand0 == -9:
                        if immediate != 1 or operand_count != field_count + 2 or result is None:
                            raise NGIRDecodeError("V16 composite vector_set arguments disagree with its record layout")
                        reference_register, index_register = call_arguments[:2]
                        if (
                            not 0 <= reference_register < len(register_type_ids)
                            or not 0 <= index_register < len(register_type_ids)
                        ):
                            raise NGIRDecodeError("V16 composite vector_set references a missing argument register")
                        reference_descriptor = type_descriptors.get(register_type_ids[reference_register])
                        vector_descriptor = (
                            type_descriptors.get(reference_descriptor.target_type)
                            if reference_descriptor is not None and reference_descriptor.kind == 9
                            else None
                        )
                        index_descriptor = type_descriptors.get(register_type_ids[index_register])
                        result_descriptor = (
                            type_descriptors.get(register_type_ids[result])
                            if 0 <= result < len(register_type_ids)
                            else None
                        )
                        if (
                            reference_descriptor is None
                            or reference_descriptor.kind != 9
                            or reference_descriptor.mutable != 1
                            or vector_descriptor is None
                            or vector_descriptor.kind != 8
                            or vector_descriptor.element_type != element_type_id
                            or index_descriptor is None
                            or index_descriptor.kind != 1
                            or result_descriptor is None
                            or result_descriptor.kind != 3
                        ):
                            raise NGIRDecodeError("V16 composite vector_set metadata disagrees with its arguments")
                        for register, field_type_id in zip(call_arguments[2:], field_type_ids, strict=True):
                            if not 0 <= register < len(register_type_ids) or register_type_ids[register] != field_type_id:
                                raise NGIRDecodeError("V16 composite vector_set value cells disagree with its record layout")
                    else:
                        if operand_count != field_count + 1 or len(call_arguments) != operand_count:
                            raise NGIRDecodeError("V9 vector_push argument count disagrees with its record layout")
                        reference_register = call_arguments[0]
                        reference_descriptor = (
                            type_descriptors.get(register_type_ids[reference_register])
                            if 0 <= reference_register < len(register_type_ids)
                            else None
                        )
                        vector_descriptor = (
                            type_descriptors.get(reference_descriptor.target_type)
                            if reference_descriptor is not None and reference_descriptor.kind == 9
                            else None
                        )
                        result_descriptor = (
                            type_descriptors.get(register_type_ids[result])
                            if result is not None and 0 <= result < len(register_type_ids)
                            else None
                        )
                        if (
                            reference_descriptor is None
                            or reference_descriptor.kind != 9
                            or reference_descriptor.mutable != 1
                            or vector_descriptor is None
                            or vector_descriptor.kind != 8
                            or vector_descriptor.element_type != element_type_id
                            or (result is not None and (result_descriptor is None or result_descriptor.kind != 3))
                        ):
                            raise NGIRDecodeError("V9 vector_push metadata disagrees with its registers")
                        for register, field_type_id in zip(call_arguments[1:], field_type_ids, strict=True):
                            if not 0 <= register < len(register_type_ids) or register_type_ids[register] != field_type_id:
                                raise NGIRDecodeError("V9 vector_push value cells disagree with the record layout")
                elif version >= 16 and operand0 in {-8, -9}:
                    target = take(23, "V16 generic vector access CALL target")
                    _, target_owner, target_instruction, operation_id, element_type_id, *reserved = target
                    expected_operation_id = {-8: 1, -9: 2}[operand0]
                    if (
                        (target_owner, target_instruction) != (function_index, instruction_index)
                        or operation_id != expected_operation_id
                        or any(reserved)
                        or immediate != 1
                    ):
                        raise NGIRDecodeError("malformed V16 generic vector access target identity")
                    element_type = type_descriptors.get(element_type_id)
                    builtin_names = _V16_VECTOR_ACCESS_BUILTINS.get(
                        element_type.kind if element_type is not None else -1
                    )
                    builtin_name = builtin_names.get(operation_id) if builtin_names is not None else None
                    expected_argument_count = 2 if operand0 == -8 else 3
                    if (
                        result is None
                        or not 0 <= result < len(register_type_ids)
                        or operand_count != expected_argument_count
                        or len(call_arguments) != expected_argument_count
                        or element_type is None
                        or builtin_name is None
                    ):
                        raise NGIRDecodeError("V16 vector access has unsupported types or argument count")
                    reference_register, index_register = call_arguments[:2]
                    if (
                        not 0 <= reference_register < len(register_type_ids)
                        or not 0 <= index_register < len(register_type_ids)
                    ):
                        raise NGIRDecodeError("V16 vector access references a missing argument register")
                    reference_type = type_descriptors.get(register_type_ids[reference_register])
                    vector_type = (
                        type_descriptors.get(reference_type.target_type)
                        if reference_type is not None and reference_type.kind == 9
                        else None
                    )
                    index_type = type_descriptors.get(register_type_ids[index_register])
                    result_type = type_descriptors.get(register_type_ids[result])
                    if (
                        reference_type is None
                        or reference_type.kind != 9
                        or (operand0 == -9 and reference_type.mutable != 1)
                        or vector_type is None
                        or vector_type.kind != 8
                        or vector_type.element_type != element_type_id
                        or index_type is None
                        or index_type.kind != 1
                    ):
                        raise NGIRDecodeError("V16 vector access reference or index metadata disagrees with its registers")
                    if operand0 == -8:
                        if result_type is None or register_type_ids[result] != element_type_id:
                            raise NGIRDecodeError("V16 vector_get result type disagrees with its element type")
                    else:
                        value_register = call_arguments[2]
                        if (
                            not 0 <= value_register < len(register_type_ids)
                            or register_type_ids[value_register] != element_type_id
                            or result_type is None
                            or result_type.kind != 3
                        ):
                            raise NGIRDecodeError("V16 vector_set value or result type disagrees with its signature")
                    callee_index = None
                    callee_builtin = builtin_name
                elif version >= 11 and operand0 == -7:
                    target = take(21, "V11 dynamic CALL target")
                    _, target_owner, target_instruction, name_start, name_end, *reserved = target
                    if (target_owner, target_instruction) != (function_index, instruction_index) or any(reserved) or immediate != 0:
                        raise NGIRDecodeError("malformed V11 dynamic CALL target identity")
                    callee_builtin = source_name(name_start, name_end, "V11 dynamic CALL target")
                    callee_index = None
                elif operand0 < 0:
                    raise NGIRDecodeError(f"unsupported generic CALL sentinel {operand0} in NG IR V{version}")
                if version >= 14 and callee_index is not None:
                    result_count = immediate
                    if result is None or result_count <= 0 or result + result_count > len(register_type_ids):
                        raise NGIRDecodeError("V14 CALL result range is missing or outside the register table")
                    instruction_results = tuple(range(result, result + result_count))
                elif result is not None and not instruction_results:
                    instruction_results = (result,)
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
            elif opcode is IROpcode.ADDRESS_OF:
                if version < 10:
                    raise NGIRDecodeError("ADDRESS_OF opcode requires NG IR V10")
                if result is None or not 0 <= result < len(register_type_ids) or immediate != 0:
                    raise NGIRDecodeError("malformed ADDRESS_OF result or immediate")
                reference_target, reference_mutable, reference_aggregate = reference_metadata(
                    register_type_ids[result], f"ADDRESS_OF result in {function_name}"
                )
                if reference_target is None or reference_aggregate is not None:
                    raise NGIRDecodeError("ADDRESS_OF requires a scalar or vector reference result")
                if operand_count == 0:
                    if operand0 != -1 or operand1 < 0:
                        raise NGIRDecodeError("memory ADDRESS_OF must identify one memory object")
                    memory_id = operand1
                    operands = ()
                    if memory_id >= len(memories) or memories[memory_id].element_type is not reference_target:
                        raise NGIRDecodeError("ADDRESS_OF memory type disagrees with its reference target")
                elif operand_count == 1:
                    if operand1 != -1 or not 0 <= operand0 < len(register_type_ids):
                        raise NGIRDecodeError("register ADDRESS_OF must identify one existing register")
                    operands = (operand0,)
                    if registers[operand0].type is not reference_target:
                        raise NGIRDecodeError("ADDRESS_OF register type disagrees with its reference target")
                else:
                    raise NGIRDecodeError("ADDRESS_OF accepts one register or one memory object")
                decoded_immediate = None
            elif opcode is IROpcode.CONVERT:
                if version < 11:
                    raise NGIRDecodeError("CONVERT opcode requires NG IR V11")
                if (
                    result is None
                    or not 0 <= result < len(register_type_ids)
                    or operand_count != 1
                    or operand1 != -1
                    or immediate != 0
                    or not 0 <= operand0 < len(register_type_ids)
                ):
                    raise NGIRDecodeError("malformed CONVERT record")
                source_type = type_for(register_type_ids[operand0], "CONVERT source")
                result_type = type_for(register_type_ids[result], "CONVERT result")
                if (source_type, result_type) not in {
                    (IRType.TRIT, IRType.I64),
                    (IRType.TRYTE, IRType.I64),
                    (IRType.TRIT, IRType.F64),
                    (IRType.TRYTE, IRType.F64),
                    (IRType.I64, IRType.F64),
                    (IRType.I64, IRType.TRYTE),
                }:
                    raise NGIRDecodeError("CONVERT source/result type metadata is invalid")
                operands = (operand0,)
                decoded_immediate = None
            elif opcode is IROpcode.REFERENCE_LOAD:
                if version < 12:
                    raise NGIRDecodeError("REFERENCE_LOAD opcode requires NG IR V12")
                if (
                    result is None
                    or not 0 <= result < len(register_type_ids)
                    or operand_count != 1
                    or operand1 != -1
                    or immediate != 0
                    or not 0 <= operand0 < len(register_type_ids)
                ):
                    raise NGIRDecodeError("malformed REFERENCE_LOAD record")
                reference_descriptor = type_descriptors.get(register_type_ids[operand0])
                if reference_descriptor is None or reference_descriptor.kind != 9:
                    raise NGIRDecodeError("REFERENCE_LOAD operand must use a reference type descriptor")
                result_type_id = register_type_ids[result]
                if reference_descriptor.target_type != result_type_id:
                    raise NGIRDecodeError("REFERENCE_LOAD result type disagrees with its reference target")
                reference_target = type_for(result_type_id, "REFERENCE_LOAD target")
                operands = (operand0,)
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
                    reference_target=reference_target,
                    reference_mutable=reference_mutable,
                    reference_is_slice=reference_is_slice,
                    static_string_value=static_string_value,
                    static_string_offset=static_string_offset,
                    results=instruction_results,
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
            for register in instruction.results:
                if register < 0 or register >= len(registers):
                    raise NGIRDecodeError(f"instruction references missing result register {register} in {function_name}")
            if instruction.memory is not None and not 0 <= instruction.memory < len(memories):
                raise NGIRDecodeError(f"instruction references missing memory {instruction.memory} in {function_name}")
            if any(target not in block_set for target in instruction.targets):
                raise NGIRDecodeError(f"instruction references a missing branch target in {function_name}")

        raw_functions.append(
            {
                "name": function_name,
                "return_type": return_type,
                "result_types": result_types,
                "result_type_ids": tuple(result_type_ids),
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

    for function in raw_functions:
        registers = function["registers"]
        for instruction in function["instructions"]:
            if instruction.opcode is not IROpcode.CALL or instruction.callee_index is None:
                continue
            if not 0 <= instruction.callee_index < len(raw_functions):
                raise NGIRDecodeError(
                    f"CALL references invalid function index {instruction.callee_index} in {function['name']}"
                )
            callee = raw_functions[instruction.callee_index]
            actual_types = tuple(registers[index].type for index in instruction.results)
            if actual_types != tuple(callee["result_types"]):
                raise NGIRDecodeError(f"CALL result cells disagree with callee signature in {function['name']}")

    ordered_static_values = sorted(
        (
            (record.static_string_offset, record.static_string_value)
            for raw in raw_functions
            for record in raw["instructions"]
            if record.static_string_value is not None
        ),
        key=lambda item: item[0],
    )
    static_ids: dict[str, str] = {}
    static_strings: list[IRStaticString] = []
    for offset, value in ordered_static_values:
        if offset is None or value is None:
            raise NGIRDecodeError("incomplete CONST_STR source metadata")
        if value not in static_ids:
            identifier = f"s{len(static_strings)}"
            static_ids[value] = identifier
            static_strings.append(IRStaticString(identifier, value))

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
            composite_vector_call = (
                record.opcode is IROpcode.CALL
                and record.callee_builtin is not None
                and record.callee_builtin.startswith("__s3_composite_vector__")
            )
            by_block[record.block].append(
                IRInstruction(
                    opcode=record.opcode,
                    result=(None if record.opcode is IROpcode.CALL and record.results else record.result),
                    operands=record.operands,
                    immediate=record.immediate,
                    callee=callee,
                    targets=tuple(block_names[target] for target in record.targets),
                    memory=record.memory,
                    initialization=record.initialization,
                    results=record.results,
                    reference_target=record.reference_target,
                    reference_mutable=record.reference_mutable,
                    reference_is_slice=record.reference_is_slice,
                    reference_aggregate=record.reference_aggregate,
                    aggregate_field_path=record.aggregate_field_path,
                    static_string=(
                        static_ids[record.static_string_value]
                        if record.static_string_value is not None
                        else None
                    ),
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
                result_types=raw["result_types"],
                external=raw["external"],
                exported=raw["exported"],
            )
        )
    return IRModule(tuple(functions), tuple(static_strings))
