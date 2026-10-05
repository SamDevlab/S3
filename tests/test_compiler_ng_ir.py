from __future__ import annotations

import json
from pathlib import Path

from bootstrap.s3.ir import IRType
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.pipeline import compile_source


_ROOT = Path(__file__).parents[1]


def _module_body(relative_path: str) -> str:
    return "\n".join(
        line
        for line in (_ROOT / relative_path).read_text(encoding="utf-8").splitlines()
        if not line.startswith("module ") and not line.startswith("from ")
    )


_NG_SOURCE = "\n".join(
    (
        (_ROOT / "selfhost/compiler_ng/lexer.s3").read_text(encoding="utf-8"),
        _module_body("selfhost/compiler_ng/parser.s3"),
        _module_body("selfhost/compiler_ng/semantic.s3"),
        _module_body("selfhost/compiler_ng/ir.s3"),
    )
)

_TYPE_CODES = {
    IRType.I64: 1,
    IRType.TRIT: 2,
    IRType.TRYTE: 3,
    IRType.F64: 4,
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
}


def _register_number(name: str) -> int:
    return int(name.removeprefix("r"))


def _reference_events(program: object) -> list[int]:
    events: list[int] = []
    function_indices = {function.name: index for index, function in enumerate(program.functions)}

    def event(kind: int, *fields: int) -> None:
        assert len(fields) == 7
        events.extend((kind, *fields))

    for function_index, function in enumerate(program.functions):
        call_argument_cursor = 0
        block_indices = {block.name: index for index, block in enumerate(function.blocks)}
        event(
            1,
            function_index,
            _TYPE_CODES[function.return_type],
            len(function.parameters),
            0,
            0,
            0,
            0,
        )
        for parameter_index, parameter in enumerate(function.parameters):
            event(
                2,
                function_index,
                parameter_index,
                _TYPE_CODES[parameter.type],
                parameter.register,
                0,
                0,
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
                if opcode == "call":
                    assert instruction.callee in function_indices
                    event(
                        4,
                        function_index,
                        _OPCODE_CODES[opcode],
                        -1 if instruction.result is None else instruction.result,
                        len(operands),
                        function_indices[instruction.callee],
                        call_argument_cursor,
                        0,
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
                if opcode == "branch3":
                    event(
                        11,
                        function_index,
                        instruction_index,
                        *(block_indices[target] for target in instruction.targets),
                        0,
                        0,
                    )
                instruction_index += 1
        event(5, function_index, 0, 0, 0, 0, 0, 0)
    return events


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
    expected = _reference_events(reference)
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
    mut functions: vector<NgFunction> = vector_new<NgFunction>(32)
    mut parameters: vector<NgParameter> = vector_new<NgParameter>(64)
    mut nodes: vector<NgAstNode> = vector_new<NgAstNode>(256)
    mut actual: vector<i64> = vector_new<i64>({len(expected)})
    mut expected: vector<i64> = vector_new<i64>({len(expected)})
    mut index: i64 = 0
    mut status: i64 = ng_lex(&source_bytes, &mut tokens)
    match status <=> 0:
        -1:
            return -100
        0:
            status = ng_parse_program(&source_bytes, &tokens, &mut functions, &mut parameters, &mut nodes)
            match status <=> 0:
                -1:
                    return -101
                0:
                    status = ng_emit_program(&source_bytes, &functions, &parameters, &nodes, &mut actual)
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
                                                return vector_get<i64>(&actual, index) * 10000 + vector_get<i64>(&expected, index)
                                            0:
                                                index = index + 1
                                            1:
                                                return vector_get<i64>(&actual, index) * 10000 + vector_get<i64>(&expected, index)
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
