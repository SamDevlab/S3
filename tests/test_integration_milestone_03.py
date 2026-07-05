from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.emulator import EmulatorError
from bootstrap.s3.ir import IROpcode
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source


ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    ("filename", "expected"),
    (
        ("first.s3", 6),
        ("simple_call.s3", 15),
        ("nested_calls.s3", 12),
        ("sign.s3", -1),
        ("recursive_sum.s3", 10),
        ("mutable_value.s3", 15),
        ("mutable_switch.s3", 10),
        ("static_array.s3", 13),
        ("trit_array.s3", 1),
        ("recursive_memory.s3", 6),
        ("native_abi.s3", 7),
    ),
)
def test_all_language_examples(filename: str, expected: int) -> None:
    source = (ROOT / "examples" / filename).read_text(encoding="utf-8")
    assert run_source(source, mode=SyntaxMode.V0_6) == expected


def test_static_array_pipeline_exposes_memory_at_ir_and_assembly() -> None:
    source = (ROOT / "examples" / "static_array.s3").read_text(encoding="utf-8")
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    function = compilation.ir.functions[0]
    assert function.memory_objects[0].length == 4
    opcodes = {instruction.opcode for instruction in function.instructions}
    assert {IROpcode.LOAD, IROpcode.STORE} <= opcodes
    assert ".memory m0, tryte, 4, mutable" in compilation.assembly_text
    assert "TLOAD" in compilation.assembly_text
    assert "TSTORE" in compilation.assembly_text


def test_dynamic_out_of_bounds_index_fails_at_runtime() -> None:
    source = """\
fn read(index: tryte) -> tryte {
    tryte[2] values = [10, 20];
    return values[index];
}
fn main() -> tryte { return read(2); }
"""
    with pytest.raises(
        EmulatorError,
        match=r"function 'read'.*memory m0 index 2.*\[0, 2\)",
    ):
        run_source(source, mode=SyntaxMode.V0_5)


def test_array_initializers_are_lowered_left_to_right() -> None:
    source = """\
fn identity(value: tryte) -> tryte { return value; }
fn main() -> tryte {
    tryte[3] values = [identity(1), identity(2), identity(3)];
    return values[2];
}
"""
    function = compile_source(source, mode=SyntaxMode.V0_5).ir.functions[1]
    calls = [
        instruction
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CALL
    ]
    stores = [
        instruction
        for instruction in function.instructions
        if instruction.opcode is IROpcode.STORE
    ]
    assert len(calls) == 3
    assert len(stores) == 3
    assert run_source(source, mode=SyntaxMode.V0_5) == 3


def test_no_phi_subtract_or_pointer_opcodes_exist() -> None:
    names = {opcode.value for opcode in IROpcode}
    assert "phi" not in names
    assert all("sub" not in name for name in names)
    assert all("ptr" not in name for name in names)
