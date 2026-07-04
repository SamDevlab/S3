from __future__ import annotations

from bootstrap.s3.ir import IROpcode, IRType
from bootstrap.s3.lowering import lower
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze
from bootstrap.s3.verifier import verify_ir


def lower_source(source: str):
    program = parse(source)
    module = lower(program, analyze(program))
    verify_ir(module)
    return module


def test_immutable_scalar_remains_in_ssa_without_memory() -> None:
    function = lower_source(
        "fn main() -> tryte { tryte value = 10; return value; }"
    ).functions[0]
    assert function.memory_objects == ()
    assert IROpcode.MOVE in {
        instruction.opcode for instruction in function.instructions
    }
    assert IROpcode.LOAD not in {
        instruction.opcode for instruction in function.instructions
    }


def test_mutable_scalar_lowers_to_memory_store_and_load() -> None:
    function = lower_source(
        """\
fn main() -> tryte {
    mut tryte value = 10;
    value = value + 5;
    return value;
}
"""
    ).functions[0]
    assert len(function.memory_objects) == 1
    memory = function.memory_objects[0]
    assert memory.element_type is IRType.TRYTE
    assert memory.length == 1
    assert memory.mutable
    instructions = function.instructions
    stores = [
        instruction
        for instruction in instructions
        if instruction.opcode is IROpcode.STORE
    ]
    loads = [
        instruction
        for instruction in instructions
        if instruction.opcode is IROpcode.LOAD
    ]
    assert len(stores) == 2
    assert stores[0].initialization
    assert not stores[1].initialization
    assert len(loads) == 2


def test_array_lowers_to_memory_of_declared_length() -> None:
    function = lower_source(
        """\
fn main() -> tryte {
    mut tryte[4] values = [1, 2, 3, 4];
    values[1] = 5;
    return values[0];
}
"""
    ).functions[0]
    assert len(function.memory_objects) == 1
    memory = function.memory_objects[0]
    assert memory.length == 4
    assert memory.element_type is IRType.TRYTE
    stores = [
        instruction
        for instruction in function.instructions
        if instruction.opcode is IROpcode.STORE
    ]
    assert len(stores) == 5
    assert all(store.memory == memory.index for store in stores)
    assert all(store.initialization for store in stores[:4])


def test_mutable_value_communicates_across_switch_without_phi() -> None:
    function = lower_source(
        """\
fn classify(value: tryte) -> tryte {
    mut tryte result = 0;
    switch (value <=> 0) {
        -1: { result = -10; }
        0: { result = 0; }
        1: { result = 10; }
    }
    return result;
}
fn main() -> tryte { return classify(5); }
"""
    ).functions[0]
    assert len(function.memory_objects) == 1
    assert IROpcode.BRANCH3 in {
        instruction.opcode for instruction in function.instructions
    }
    assert IROpcode.STORE in {
        instruction.opcode for instruction in function.instructions
    }
    assert IROpcode.LOAD in {
        instruction.opcode for instruction in function.instructions
    }
    assert all("phi" not in opcode.value for opcode in IROpcode)


def test_subtraction_still_lowers_to_invert_and_add_with_memory() -> None:
    function = lower_source(
        """\
fn main() -> tryte {
    mut tryte value = 3;
    value = value - 1;
    return value;
}
"""
    ).functions[0]
    opcodes = [instruction.opcode for instruction in function.instructions]
    invert = opcodes.index(IROpcode.INVERT)
    assert opcodes[invert + 1] is IROpcode.ADD
    assert all("sub" not in opcode.value for opcode in IROpcode)

