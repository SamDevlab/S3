from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.assembly import AssemblyOpcode
from bootstrap.s3.emulator import EmulatorError, execute_assembly
from bootstrap.s3.ir import IROpcode, IRType
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.verifier import verify_ir


def example(name: str) -> str:
    return Path("examples", name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("filename", "expected"),
    (
        ("first.s3", 6),
        ("simple_call.s3", 15),
        ("nested_calls.s3", 12),
        ("sign.s3", -1),
        ("recursive_sum.s3", 10),
    ),
)
def test_examples_execute_end_to_end(filename: str, expected: int) -> None:
    assert run_source(example(filename), mode=SyntaxMode.V0_6) == expected


def test_recursive_lowering_has_blocks_calls_and_subtraction_reduction() -> None:
    compilation = compile_source(example("recursive_sum.s3"), mode=SyntaxMode.V0_6)
    verify_ir(compilation.ir)
    sum_to = compilation.ir.functions[0]
    assert sum_to.parameters[0].type is IRType.TRYTE
    assert {block.name for block in sum_to.blocks} >= {
        "entry",
        "switch_negative_0",
        "switch_neutral_1",
        "switch_positive_2",
    }
    opcodes = [instruction.opcode for instruction in sum_to.instructions]
    assert IROpcode.BRANCH3 in opcodes
    assert IROpcode.CALL in opcodes
    invert_index = opcodes.index(IROpcode.INVERT)
    assert opcodes[invert_index + 1] is IROpcode.ADD
    assert all("sub" not in opcode.value for opcode in IROpcode)
    assert "TSUB" not in AssemblyOpcode.__members__


def test_switch_selector_is_evaluated_once_in_ir() -> None:
    source = """\
fn identity(value: trit) -> trit { return value; }
fn main() -> trit {
    switch (identity(0)) {
        -1: { return -1; }
        0: { return 0; }
        1: { return 1; }
    }
}
"""
    compilation = compile_source(source)
    main = compilation.ir.functions[1]
    calls = [
        instruction
        for instruction in main.instructions
        if instruction.opcode is IROpcode.CALL
    ]
    assert len(calls) == 1
    assert run_source(source) == 0


def test_forward_declared_function_executes() -> None:
    source = """\
fn main() -> tryte { return calculate(3); }
fn calculate(value: tryte) -> tryte { return value + 1; }
"""
    assert run_source(source) == 4


def test_control_flow_ir_preserves_source_locations() -> None:
    compilation = compile_source(example("recursive_sum.s3"), mode=SyntaxMode.V0_6)
    instructions = [
        instruction
        for function in compilation.ir.functions
        for instruction in function.instructions
    ]
    relevant = [
        instruction
        for instruction in instructions
        if instruction.opcode
        in {
            IROpcode.COMPARE,
            IROpcode.BRANCH3,
            IROpcode.CALL,
            IROpcode.RETURN,
        }
    ]
    assert relevant
    assert all(instruction.location is not None for instruction in relevant)


@pytest.mark.parametrize(
    ("argument", "expected"),
    (("-7", -1), ("0", 0), ("7", 1)),
)
def test_all_three_switch_branches(argument: str, expected: int) -> None:
    source = f"""\
fn sign(value: tryte) -> trit {{
    switch (value <=> 0) {{
        -1: {{ return -1; }}
        0: {{ return 0; }}
        1: {{ return 1; }}
    }}
}}
fn main() -> trit {{ return sign({argument}); }}
"""
    assert run_source(source) == expected


def test_frame_registers_are_isolated_across_nested_calls() -> None:
    source = """\
fn retain(value: tryte) -> tryte { return value; }
fn outer(value: tryte) -> tryte {
    tryte inner = retain(3);
    return value + inner;
}
fn main() -> tryte { return outer(9); }
"""
    assert run_source(source) == 12


def test_frame_limit_stops_unbounded_recursion() -> None:
    assembly = compile_source(
        """\
fn forever(value: tryte) -> tryte { return forever(value); }
fn main() -> tryte { return forever(0); }
"""
    ).assembly
    with pytest.raises(EmulatorError, match="frame limit 4 exceeded"):
        execute_assembly(assembly, max_frames=4)


def test_instruction_limit_is_enforced() -> None:
    assembly = compile_source(example("simple_call.s3"), mode=SyntaxMode.V0_6).assembly
    with pytest.raises(EmulatorError, match="instruction limit 2 exceeded"):
        execute_assembly(assembly, max_instructions=2)


def test_overflow_in_called_function_has_function_context() -> None:
    source = """\
fn overflow() -> tryte { return 364 + 1; }
fn main() -> tryte { return overflow(); }
"""
    with pytest.raises(
        EmulatorError,
        match=r"function 'overflow'.*TADD.*source 1:.*overflow",
    ):
        run_source(source)
