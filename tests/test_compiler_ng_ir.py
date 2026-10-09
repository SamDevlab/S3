from __future__ import annotations

import json
from pathlib import Path

from bootstrap.s3.compiler_ng_ir_bridge import decode_ng_ir_events
from bootstrap.s3.dynamic import DynamicVector
from bootstrap.s3.ir import IRType
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.verifier import verify_ir


_ROOT = Path(__file__).parents[1]


def _module_body(relative_path: str) -> str:
    return "\n".join(
        line
        for line in (_ROOT / relative_path).read_text(encoding="utf-8").splitlines()
        if not line.startswith("module ") and not line.startswith("from ")
    )


_NG_SOURCE = "\n".join(
    (
        _module_body("selfhost/compiler_ng/character_classes.s3"),
        _module_body("selfhost/compiler_ng/lexer.s3"),
        _module_body("selfhost/compiler_ng/types.s3"),
        _module_body("selfhost/compiler_ng/parser.s3"),
        _module_body("selfhost/compiler_ng/semantic.s3"),
        _module_body("selfhost/compiler_ng/ir.s3"),
        _module_body("selfhost/compiler_ng/modules.s3"),
    )
)

_TYPE_CODES = {
    IRType.I64: 1,
    IRType.TRIT: 2,
    IRType.TRYTE: 3,
    IRType.F64: 4,
    IRType.BYTES: 5,
    IRType.TEXT: 6,
}
_OPCODE_CODES = {
    "const": 1,
    "add": 2,
    "numeric_difference": 3,
    "multiply": 4,
    "divide": 5,
    "return": 6,
    "call": 7,
    "move": 8,
    "load": 9,
    "store": 10,
    "branch3": 11,
    "jump": 12,
    "compare": 13,
    "relate": 15,
}


def _register_number(name: str) -> int:
    return int(name.removeprefix("r"))


def _source_name_span(source: str, name: str, character_offset: int, *, search_line: bool) -> tuple[int, int]:
    encoded = source.encode("utf-8")
    if search_line:
        line_end = source.find("\n", character_offset)
        if line_end < 0:
            line_end = len(source)
        character_start = source.find(name, character_offset, line_end)
        assert character_start >= 0
    else:
        character_start = character_offset
        assert source[character_start : character_start + len(name)] == name
    byte_start = len(source[:character_start].encode("utf-8"))
    byte_end = byte_start + len(name.encode("utf-8"))
    assert byte_end <= len(encoded)
    return byte_start, byte_end


def _reference_events(program: object, source: str) -> list[int]:
    events: list[int] = []
    function_indices = {function.name: index for index, function in enumerate(program.functions)}

    def event(kind: int, *fields: int) -> None:
        assert len(fields) == 7
        events.extend((kind, *fields))

    event(0, 17, 8, 0, 0, 0, 0, 0)
    for type_id in range(1, 7):
        event(12, type_id, type_id, -1, -1, -1, -1, -1)
        event(13, type_id, -1, 0, 0, 0, 0, 0)
    for function_index, function in enumerate(program.functions):
        call_argument_cursor = 0
        return_cell_cursor = 0
        block_indices = {block.name: index for index, block in enumerate(function.blocks)}
        assert function.location is not None
        function_name_start, function_name_end = _source_name_span(
            source, function.name, function.location.offset, search_line=True
        )
        event(
            1,
            function_index,
            _TYPE_CODES[function.return_type],
            len(function.parameters),
            function_name_start,
            function_name_end,
            function.result_width,
            int(function.external) | (int(function.exported) << 1),
        )
        for result_ordinal, result_type in enumerate(function.result_types):
            event(22, function_index, result_ordinal, _TYPE_CODES[result_type], 0, 0, 0, 0)
        for parameter_index, parameter in enumerate(function.parameters):
            assert parameter.location is not None
            parameter_name_start, parameter_name_end = _source_name_span(
                source, parameter.name, parameter.location.offset, search_line=False
            )
            event(
                2,
                function_index,
                parameter_index,
                _TYPE_CODES[parameter.type],
                parameter.register,
                parameter_name_start,
                parameter_name_end,
                0,
            )
        for register in function.registers:
            event(
                3,
                function_index,
                register.index,
                _TYPE_CODES[register.type],
                0,
                0,
                0,
                0,
            )
        for memory in function.memory_objects:
            event(
                7,
                function_index,
                memory.index,
                _TYPE_CODES[memory.element_type],
                memory.length,
                int(memory.mutable),
                0,
                0,
            )
        for block_index, block in enumerate(function.blocks):
            event(9, function_index, block_index, 0, 0, 0, 0, 0)
        instruction_index = 0
        for block_index, block in enumerate(function.blocks):
            for instruction in block.instructions:
                operands = instruction.operands
                immediate = instruction.immediate
                assert immediate is None or isinstance(immediate, int)
                opcode = instruction.opcode.value
                result_register = instruction.result
                if opcode == "call" and result_register is None and instruction.results:
                    assert len(instruction.results) == 1, "NG event format currently supports one call result"
                    result_register = instruction.results[0]
                if opcode == "return":
                    assert operands
                    event(
                        4,
                        function_index,
                        _OPCODE_CODES[opcode],
                        -1,
                        len(operands),
                        operands[0],
                        return_cell_cursor,
                        0,
                    )
                    for result_ordinal, return_register in enumerate(operands):
                        event(
                            24,
                            function_index,
                            instruction_index,
                            result_ordinal,
                            return_register,
                            0,
                            0,
                            0,
                        )
                    return_cell_cursor += len(operands)
                elif opcode == "call":
                    assert instruction.callee in function_indices
                    event(
                        4,
                        function_index,
                        _OPCODE_CODES[opcode],
                        -1 if result_register is None else result_register,
                        len(operands),
                        function_indices[instruction.callee],
                        call_argument_cursor,
                        len(instruction.results),
                    )
                    for argument_index, argument_register in enumerate(operands):
                        event(6, function_index, instruction_index, argument_index, argument_register, 0, 0, 0)
                    call_argument_cursor += len(operands)
                elif opcode == "load":
                    event(4, function_index, _OPCODE_CODES[opcode], -1 if instruction.result is None else instruction.result, len(operands), operands[0], instruction.memory, 0)
                elif opcode == "store":
                    event(4, function_index, _OPCODE_CODES[opcode], -1, len(operands), operands[0], operands[1], instruction.memory)
                    event(8, function_index, instruction_index, int(instruction.initialization), 0, 0, 0, 0)
                else:
                    event(
                        4,
                        function_index,
                        _OPCODE_CODES[opcode],
                        -1 if instruction.result is None else instruction.result,
                        len(operands),
                        -1 if len(operands) < 1 else operands[0],
                        -1 if len(operands) < 2 else operands[1],
                        0 if immediate is None else immediate,
                    )
                event(10, function_index, instruction_index, block_index, 0, 0, 0, 0)
                if opcode in {"branch3", "jump"}:
                    targets = tuple(block_indices[target] for target in instruction.targets)
                    event(11, function_index, instruction_index, *targets, *(0 for _ in range(5 - len(targets))))
                instruction_index += 1
        event(5, function_index, 0, 0, 0, 0, 0, 0)
    return events


def _canonical_ir_structure(program: object) -> tuple[object, ...]:
    functions: list[object] = []
    for function in program.functions:
        block_names = {
            block.name: f"b{index}" for index, block in enumerate(function.blocks)
        }
        blocks = tuple(
            (
                block_names[block.name],
                tuple(
                    (
                        instruction.opcode.value,
                        (
                            None
                            if instruction.opcode.value == "call" and instruction.results
                            else instruction.result
                        ),
                        instruction.results,
                        instruction.operands,
                        instruction.immediate,
                        instruction.static_string,
                        instruction.callee,
                        tuple(block_names[target] for target in instruction.targets),
                        instruction.memory,
                        instruction.initialization,
                        instruction.reference_target,
                        instruction.reference_mutable,
                        instruction.reference_is_slice,
                        instruction.slice_length_result,
                        instruction.reference_aggregate,
                        instruction.aggregate_field_paths,
                        instruction.aggregate_field_path,
                    )
                    for instruction in block.instructions
                ),
            )
            for block in function.blocks
        )
        functions.append(
            (
                function.name,
                tuple(
                    (parameter.name, parameter.register, parameter.type)
                    for parameter in function.parameters
                ),
                function.return_type,
                function.result_types,
                tuple((register.index, register.type) for register in function.registers),
                tuple(
                    (memory.index, memory.element_type, memory.length, memory.mutable)
                    for memory in function.memory_objects
                ),
                blocks,
                function.external,
                function.exported,
            )
        )
    return tuple(functions), tuple(
        (item.id, item.value) for item in program.static_strings
    )


def _nextgen_event_parity_result(source: str) -> int:
    reference = compile_source(source).ir
    assert reference is not None
    expected = _reference_events(reference, source)
    wrapper = f'''
fn main() -> vector<i64>:
    mut source_text: text = text_from_static({json.dumps(source)})
    mut source_bytes: bytes = bytes_from_text(&source_text)
    mut tokens: vector<NgToken> = vector_new<NgToken>(8192)
    mut types: vector<NgTypeDescriptor> = vector_new<NgTypeDescriptor>(16)
    mut records: vector<NgRecord> = vector_new<NgRecord>(1)
    mut fields: vector<NgField> = vector_new<NgField>(1)
    mut functions: vector<NgFunction> = vector_new<NgFunction>(64)
    mut parameters: vector<NgParameter> = vector_new<NgParameter>(256)
    mut nodes: vector<NgAstNode> = vector_new<NgAstNode>(2048)
    mut events: vector<i64> = vector_new<i64>({max(len(expected), 1)})
    discard ng_initialize_type_table(&mut types)
    mut status: i64 = ng_lex(&source_bytes, &mut tokens)
    match status <=> 0:
        -1:
            discard vector_push<i64>(&mut events, status)
            return events
        0:
            status = ng_parse_program_typed(&source_bytes, &tokens, &mut types, -1, -1, &mut functions, &mut parameters, &mut nodes)
            match status <=> 0:
                -1:
                    discard vector_push<i64>(&mut events, status)
                    return events
                0:
                    status = ng_emit_program(&source_bytes, &types, &records, &fields, &functions, &parameters, &mut nodes, &mut events)
                    match status <=> 0:
                        -1:
                            return events
                        0:
                            return events
                        1:
                            discard vector_push<i64>(&mut events, status)
                            return events
                1:
                    discard vector_push<i64>(&mut events, status)
                    return events
        1:
            discard vector_push<i64>(&mut events, status)
            return events
'''
    compilation = compile_source(_NG_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    events = execute_ir(compilation.ir)
    if not isinstance(events, DynamicVector):
        return -100
    cells = [int(cell) for cell in events]
    if not cells or cells[0] != 0:
        return cells[0] if cells else -100
    candidate = decode_ng_ir_events(source.encode("utf-8"), cells)
    verify_ir(candidate)
    return 0 if _canonical_ir_structure(candidate) == _canonical_ir_structure(reference) else -30000


def test_nextgen_emits_reference_equivalent_typed_ir_for_multiple_functions() -> None:
    source = "\n".join(
        (
            "fn calculate(left: i64, right: i64) -> i64:",
            "    return (left + right + 1) * 3 - right / 2 / 2",
            "fn sum3(first: i64, second: i64, third: i64) -> i64:",
            "    return first + second + third",
            "fn constant() -> i64:",
            "    return 7",
            "fn relay(value: i64) -> i64:",
            "    return sum3(value, constant(), 3)",
            "fn adjust(value: i64) -> i64:",
            "    mut current: i64 = value",
            "    current = current + 1",
            "    return current",
            "fn choose(value: trit) -> i64:",
            "    match value:",
            "        -1:",
            "            return 10",
            "        0:",
            "            return 20",
            "        1:",
            "            return 30",
            "fn pass_trit(value: trit) -> trit:",
            "    return value",
            "fn pass_value(value: tryte) -> tryte:",
            "    return value",
            "fn pass_f64(value: f64) -> f64:",
            "    return value",
            "fn main() -> i64:",
            "    return adjust(relay(1))",
        )
    )
    reference = compile_source(source).ir
    assert reference is not None
    expected = _reference_events(reference, source)
    expected_pushes = "\n".join(
        [f"discard vector_push<i64>(&mut expected, {expected[0]})"]
        + [
            f"{' ' * 28}discard vector_push<i64>(&mut expected, {value})"
            for value in expected[1:]
        ]
    )
    wrapper = f'''
fn main() -> i64:
    mut source_text: text = text_from_static({json.dumps(source)})
    mut source_bytes: bytes = bytes_from_text(&source_text)
    mut tokens: vector<NgToken> = vector_new<NgToken>(256)
    mut types: vector<NgTypeDescriptor> = vector_new<NgTypeDescriptor>(16)
    mut records: vector<NgRecord> = vector_new<NgRecord>(1)
    mut fields: vector<NgField> = vector_new<NgField>(1)
    mut functions: vector<NgFunction> = vector_new<NgFunction>(32)
    mut parameters: vector<NgParameter> = vector_new<NgParameter>(64)
    mut nodes: vector<NgAstNode> = vector_new<NgAstNode>(256)
    mut actual: vector<i64> = vector_new<i64>({len(expected)})
    mut expected: vector<i64> = vector_new<i64>({len(expected)})
    mut index: i64 = 0
    discard ng_initialize_type_table(&mut types)
    mut status: i64 = ng_lex(&source_bytes, &mut tokens)
    match status <=> 0:
        -1:
            return -100
        0:
            status = ng_parse_program_typed(&source_bytes, &tokens, &mut types, -1, -1, &mut functions, &mut parameters, &mut nodes)
            match status <=> 0:
                -1:
                    return -101
                0:
                    status = ng_emit_program(&source_bytes, &types, &records, &fields, &functions, &parameters, &mut nodes, &mut actual)
                    match status <=> 0:
                        -1:
                            return status
                        0:
                            {expected_pushes}
                            match vector_len<i64>(&actual) <=> {len(expected)}:
                                -1:
                                    return -103
                                0:
                                    index = 0
                                    while index < {len(expected)}:
                                        match vector_get<i64>(&actual, index) <=> vector_get<i64>(&expected, index):
                                            -1:
                                                return index + 1
                                            0:
                                                index = index + 1
                                            1:
                                                return index + 1
                                    return 0
                                1:
                                    return -103
                        1:
                            return -102
                1:
                    return -101
        1:
            return -100
'''
    compilation = compile_source(_NG_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    result = int(execute_ir(compilation.ir))
    assert result == 0, f"serialized IR differs at flattened cell {result - 1}"


def test_nextgen_emits_reference_equivalent_ir_for_signed_i64_boundaries() -> None:
    source = (
        "fn minimum() -> i64:\n    return -9223372036854775807\n"
        "fn maximum() -> i64:\n    return 9223372036854775807\n"
        "fn main() -> i64:\n    return minimum() + maximum()\n"
    )
    assert _nextgen_event_parity_result(source) == 0


def test_nextgen_discarded_call_emits_side_effecting_call_without_result_use() -> None:
    source = "\n".join(
        (
            "fn effect(value: i64) -> i64:",
            "    return value",
            "fn main() -> i64:",
            "    discard effect(7)",
            "    return 0",
        )
    )
    assert _nextgen_event_parity_result(source) == 0


def test_nextgen_f64_relational_ir_matches_reference_relation_codes() -> None:
    source = "\n".join(
        line
        for name, operator in (
            ("equal", "=="),
            ("not_equal", "!="),
            ("less", "<"),
            ("less_equal", "<="),
            ("greater", ">"),
            ("greater_equal", ">="),
        )
        for line in (
            f"fn {name}(left: f64, right: f64) -> trit:",
            f"    return left {operator} right",
        )
    ) + "\nfn main() -> i64:\n    return 0\n"
    assert _nextgen_event_parity_result(source) == 0


def test_nextgen_emits_reference_equivalent_ir_for_branches_workload() -> None:
    source = (_ROOT / "benchmarks/workloads/branches.s3").read_text(encoding="utf-8")
    result = _nextgen_event_parity_result(source)
    assert result == 0, (
        f"NG/reference IR parity probe returned {result}; "
        f"positive results encode the first differing cell at {result - 1}"
    )


def test_nextgen_emits_unique_blocks_for_sequential_matches() -> None:
    source = "\n".join(
        (
            "fn choose(value: trit) -> i64:",
            "    mut result: i64 = 5",
            "    match value:",
            "        -1:",
            "            result = result + 1",
            "        0:",
            "            result = result + 2",
            "        1:",
            "            result = result + 3",
            "    match value:",
            "        -1:",
            "            result = result * 2",
            "        0:",
            "            result = result * 3",
            "        1:",
            "            result = result * 4",
            "    return result",
            "fn main() -> i64:",
            "    return 0",
        )
    )
    result = _nextgen_event_parity_result(source)
    assert result == 0, (
        f"NG/reference IR parity probe returned {result}; "
        f"positive results encode the first differing cell at {result - 1}"
    )
