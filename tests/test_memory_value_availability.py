from __future__ import annotations

from bootstrap.s3.ir import IRMemoryObject, IROpcode, IRType
from bootstrap.s3 import run_source
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.ssa import (
    SSAFunction,
    SSAInstruction,
    SSABlock,
    SSAParameter,
    SSABuilder,
    SSAValue,
)
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.memory_value_availability import (
    AvailabilityKind,
    _NON_WRITING_OPCODES,
    analyze_memory_value_availability,
    analyze_repeated_load_availability,
)
from tools.s3_memory_availability_experiment import forward_available_stores
from tools.s3_memory_repeated_load_experiment import (
    forward_available_loads,
    forward_available_loads_by_ssa_substitution,
)


def _value(name: str, block: str, type_: IRType = IRType.TRYTE) -> SSAValue:
    return SSAValue(name, type=type_, def_block=block)


def _constant(
    name: str,
    value: int,
    block: str = "entry",
    type_: IRType = IRType.I64,
) -> SSAInstruction:
    return SSAInstruction(
        IROpcode.CONST,
        result=_value(name, block, type_),
        immediate=value,
    )


def _load(
    name: str,
    index: SSAValue,
    block: str,
    memory: int = 0,
) -> SSAInstruction:
    return SSAInstruction(
        IROpcode.LOAD,
        result=_value(name, block),
        operands=(index,),
        memory=memory,
    )


def _store(
    index: SSAValue,
    value: SSAValue,
    block: str,
    memory: int = 0,
) -> SSAInstruction:
    return SSAInstruction(
        IROpcode.STORE,
        operands=(index, value),
        memory=memory,
    )


def _function(
    blocks: tuple[SSABlock, ...],
    values: tuple[SSAValue, ...],
    *,
    length: int = 2,
    parameters: tuple[SSAParameter, ...] = (),
) -> SSAFunction:
    return SSAFunction(
        name="probe",
        parameters=parameters,
        blocks=blocks,
        values=values,
        memory_objects=(IRMemoryObject(0, IRType.TRYTE, length, True),),
        return_type=IRType.TRYTE,
    )


def _only_load_state(function: SSAFunction):
    report = analyze_memory_value_availability(function)
    assert len(report.loads) == 1
    return report.loads[0]


def test_memory_effect_transfer_classifies_every_ir_opcode() -> None:
    writing_or_unknown = {
        IROpcode.CALL,
        IROpcode.STORE,
        IROpcode.REFERENCE_STORE,
        IROpcode.SLICE_STORE,
    }
    assert _NON_WRITING_OPCODES.isdisjoint(writing_or_unknown)
    assert _NON_WRITING_OPCODES | writing_or_unknown == set(IROpcode)


def test_stored_value_is_available_across_a_basic_block_edge() -> None:
    index = _value("index", "entry", IRType.I64)
    value = _value("value", "entry")
    loaded = _value("loaded", "read")
    function = _function(
        (
            SSABlock(
                "entry",
                instructions=[
                    _constant("index", 0),
                    _constant("value", 17, type_=IRType.TRYTE),
                    _store(index, value, "entry"),
                    SSAInstruction(IROpcode.JUMP, targets=("read",)),
                ],
            ),
            SSABlock(
                "read",
                instructions=[
                    _load("loaded", index, "read"),
                    SSAInstruction(IROpcode.RETURN, operands=(loaded,)),
                ],
            ),
        ),
        (index, value, loaded),
        length=1,
    )

    candidate = _only_load_state(function)
    assert candidate.state.kind is AvailabilityKind.AVAILABLE
    assert candidate.state.value == value
    assert candidate.forwardable
    assert candidate.reason == "SAME_EXACT_VALUE_ON_ALL_PATHS"
    assert candidate.state.store_blocks == ("entry",)
    assert candidate.state.store_sites == (("entry", 2),)
    assert candidate.cross_block_available


def test_join_keeps_only_the_same_value_stored_on_every_incoming_path() -> None:
    index = _value("index", "entry", IRType.I64)
    condition = _value("condition", "entry")
    value = _value("value", "entry")
    loaded = _value("loaded", "join")
    function = _function(
        (
            SSABlock(
                "entry",
                instructions=[
                    _constant("index", 0),
                    _constant("value", 17, type_=IRType.TRYTE),
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(condition,),
                        targets=("left", "right", "third"),
                    ),
                ],
            ),
            SSABlock(
                "left",
                instructions=[
                    _store(index, value, "left"),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "right",
                instructions=[
                    _store(index, value, "right"),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "third",
                instructions=[
                    _store(index, value, "third"),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "join",
                instructions=[
                    _load("loaded", index, "join"),
                    SSAInstruction(IROpcode.RETURN, operands=(loaded,)),
                ],
            ),
        ),
        (index, condition, value, loaded),
        length=1,
        parameters=(SSAParameter(condition),),
    )

    candidate = _only_load_state(function)
    assert candidate.state.kind is AvailabilityKind.AVAILABLE
    assert candidate.state.value == value
    assert candidate.state.store_blocks == ("left", "right", "third")
    assert candidate.state.store_sites == (("left", 0), ("right", 0), ("third", 0))
    assert candidate.cross_block_available


def test_join_rejects_different_values_and_a_path_without_a_store() -> None:
    index = _value("index", "entry", IRType.I64)
    condition = _value("condition", "entry")
    left_value = _value("left_value", "entry")
    right_value = _value("right_value", "entry")
    loaded = _value("loaded", "join")
    function = _function(
        (
            SSABlock(
                "entry",
                instructions=[
                    _constant("index", 0),
                    _constant("left_value", 17, type_=IRType.TRYTE),
                    _constant("right_value", 23, type_=IRType.TRYTE),
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(condition,),
                        targets=("left", "right", "empty"),
                    ),
                ],
            ),
            SSABlock(
                "left",
                instructions=[
                    _store(index, left_value, "left"),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "right",
                instructions=[
                    _store(index, right_value, "right"),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock("empty", instructions=[SSAInstruction(IROpcode.JUMP, targets=("join",))]),
            SSABlock(
                "join",
                instructions=[
                    _load("loaded", index, "join"),
                    SSAInstruction(IROpcode.RETURN, operands=(loaded,)),
                ],
            ),
        ),
        (index, condition, left_value, right_value, loaded),
        length=1,
        parameters=(SSAParameter(condition),),
    )

    candidate = _only_load_state(function)
    assert candidate.state.kind is AvailabilityKind.MAYBE_AVAILABLE
    assert not candidate.forwardable


def test_may_alias_store_and_call_have_distinct_conservative_states() -> None:
    index = _value("index", "entry", IRType.I64)
    dynamic_index = _value("dynamic_index", "entry", IRType.I64)
    value = _value("value", "entry")
    other_value = _value("other_value", "entry")
    loaded_after_may_store = _value("loaded_after_may_store", "entry")
    loaded_after_call = _value("loaded_after_call", "read")
    function = _function(
        (
            SSABlock(
                "entry",
                instructions=[
                    _constant("index", 0),
                    _constant("value", 17, type_=IRType.TRYTE),
                    _constant("other_value", 23, type_=IRType.TRYTE),
                    _store(index, value, "entry"),
                    _store(dynamic_index, other_value, "entry"),
                    _load("loaded_after_may_store", index, "entry"),
                    SSAInstruction(IROpcode.CALL, immediate="unknown", operands=(dynamic_index,)),
                    SSAInstruction(IROpcode.JUMP, targets=("read",)),
                ],
            ),
            SSABlock(
                "read",
                instructions=[
                    _load("loaded_after_call", index, "read"),
                    SSAInstruction(IROpcode.RETURN, operands=(loaded_after_call,)),
                ],
            ),
        ),
        (
            index,
            dynamic_index,
            value,
            other_value,
            loaded_after_may_store,
            loaded_after_call,
        ),
        length=2,
        parameters=(SSAParameter(dynamic_index),),
    )

    report = analyze_memory_value_availability(function)
    assert [item.state.kind for item in report.loads] == [
        AvailabilityKind.MAYBE_AVAILABLE,
        AvailabilityKind.UNKNOWN,
    ]
    assert not any(item.forwardable for item in report.loads)


def test_store_to_distinct_constant_index_preserves_cell_availability() -> None:
    index0 = _value("index0", "entry", IRType.I64)
    index1 = _value("index1", "entry", IRType.I64)
    first = _value("first", "entry")
    second = _value("second", "entry")
    loaded = _value("loaded", "entry")
    function = _function(
        (
            SSABlock(
                "entry",
                instructions=[
                    _constant("index0", 0),
                    _constant("index1", 1),
                    _constant("first", 17, type_=IRType.TRYTE),
                    _constant("second", 23, type_=IRType.TRYTE),
                    _store(index0, first, "entry"),
                    _store(index1, second, "entry"),
                    _load("loaded", index0, "entry"),
                    SSAInstruction(IROpcode.RETURN, operands=(loaded,)),
                ],
            ),
        ),
        (index0, index1, first, second, loaded),
        length=2,
    )

    candidate = _only_load_state(function)
    assert candidate.state.kind is AvailabilityKind.AVAILABLE
    assert candidate.state.value == first
    assert candidate.state.store_blocks == ("entry",)
    assert not candidate.cross_block_available


def test_availability_does_not_leak_between_distinct_memory_objects() -> None:
    index = _value("index", "entry", IRType.I64)
    first = _value("first", "entry")
    loaded_first = _value("loaded_first", "entry")
    loaded_second = _value("loaded_second", "entry")
    function = SSAFunction(
        name="probe",
        parameters=(),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    _constant("index", 0),
                    _constant("first", 17, type_=IRType.TRYTE),
                    _store(index, first, "entry", memory=0),
                    _load("loaded_first", index, "entry", memory=0),
                    _load("loaded_second", index, "entry", memory=1),
                    SSAInstruction(IROpcode.RETURN, operands=(loaded_first,)),
                ],
            ),
        ),
        values=(index, first, loaded_first, loaded_second),
        memory_objects=(
            IRMemoryObject(0, IRType.TRYTE, 1, True),
            IRMemoryObject(1, IRType.TRYTE, 1, True),
        ),
        return_type=IRType.TRYTE,
    )

    report = analyze_memory_value_availability(function)
    assert [item.state.kind for item in report.loads] == [
        AvailabilityKind.AVAILABLE,
        AvailabilityKind.UNINITIALIZED,
    ]


def test_loop_backedge_with_a_may_alias_write_blocks_forwarding_after_loop() -> None:
    index = _value("index", "entry", IRType.I64)
    condition = _value("condition", "entry")
    first = _value("first", "entry")
    later = _value("later", "body")
    loaded = _value("loaded", "exit")
    function = _function(
        (
            SSABlock(
                "entry",
                instructions=[
                    _constant("index", 0),
                    _constant("first", 17, type_=IRType.TRYTE),
                    _store(index, first, "entry"),
                    SSAInstruction(IROpcode.JUMP, targets=("header",)),
                ],
            ),
            SSABlock(
                "header",
                instructions=[
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(condition,),
                        targets=("body", "exit", "exit"),
                    ),
                ],
            ),
            SSABlock(
                "body",
                instructions=[
                    _constant("later", 23, "body", IRType.TRYTE),
                    _store(index, later, "body"),
                    SSAInstruction(IROpcode.JUMP, targets=("header",)),
                ],
            ),
            SSABlock(
                "exit",
                instructions=[
                    _load("loaded", index, "exit"),
                    SSAInstruction(IROpcode.RETURN, operands=(loaded,)),
                ],
            ),
        ),
        (index, condition, first, later, loaded),
        length=1,
        parameters=(SSAParameter(condition),),
    )

    candidate = _only_load_state(function)
    assert candidate.state.kind is AvailabilityKind.MAYBE_AVAILABLE
    assert not candidate.forwardable


def test_repeated_load_is_available_across_a_cfg_edge_but_not_within_one_block() -> None:
    index = _value("index", "entry", IRType.I64)
    first = _value("first", "entry")
    second = _value("second", "read")
    across_blocks = _function(
        (
            SSABlock(
                "entry",
                instructions=[
                    _constant("index", 0),
                    _load("first", index, "entry"),
                    SSAInstruction(IROpcode.JUMP, targets=("read",)),
                ],
            ),
            SSABlock(
                "read",
                instructions=[
                    _load("second", index, "read"),
                    SSAInstruction(IROpcode.RETURN, operands=(second,)),
                ],
            ),
        ),
        (index, first, second),
        length=1,
    )

    report = analyze_repeated_load_availability(across_blocks)
    candidate = next(item for item in report.candidates if item.block == "read")
    assert candidate.forwardable
    assert candidate.cross_block_available
    assert candidate.state.value == first
    assert candidate.state.load_sites == (("entry", 1),)
    assert report.cross_block_candidate_count == 1

    same_block_first = _value("same_first", "entry")
    same_block_second = _value("same_second", "entry")
    same_block = _function(
        (
            SSABlock(
                "entry",
                instructions=[
                    _constant("index", 0),
                    _load("same_first", index, "entry"),
                    _load("same_second", index, "entry"),
                    SSAInstruction(IROpcode.RETURN, operands=(same_block_second,)),
                ],
            ),
        ),
        (index, same_block_first, same_block_second),
        length=1,
    )
    same_report = analyze_repeated_load_availability(same_block)
    assert same_report.cross_block_candidate_count == 0
    assert not next(
        item for item in same_report.candidates if item.result == same_block_second
    ).cross_block_available


def test_repeated_load_join_requires_same_value_on_every_incoming_path() -> None:
    index = _value("index", "entry", IRType.I64)
    condition = _value("condition", "entry")
    first = _value("first", "entry")
    joined = _value("joined", "join")
    same_value = _function(
        (
            SSABlock(
                "entry",
                instructions=[
                    _constant("index", 0),
                    _load("first", index, "entry"),
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(condition,),
                        targets=("left", "right", "third"),
                    ),
                ],
            ),
            SSABlock("left", instructions=[SSAInstruction(IROpcode.JUMP, targets=("join",))]),
            SSABlock("right", instructions=[SSAInstruction(IROpcode.JUMP, targets=("join",))]),
            SSABlock("third", instructions=[SSAInstruction(IROpcode.JUMP, targets=("join",))]),
            SSABlock(
                "join",
                instructions=[
                    _load("joined", index, "join"),
                    SSAInstruction(IROpcode.RETURN, operands=(joined,)),
                ],
            ),
        ),
        (index, condition, first, joined),
        length=1,
        parameters=(SSAParameter(condition),),
    )
    report = analyze_repeated_load_availability(same_value)
    join_candidate = next(item for item in report.candidates if item.result == joined)
    assert join_candidate.forwardable
    assert join_candidate.state.load_sites == (("entry", 1),)

    left_value = _value("left_value", "left")
    right_value = _value("right_value", "right")
    third_value = _value("third_value", "third")
    merged = _value("merged", "join")
    different_values = _function(
        (
            SSABlock(
                "entry",
                instructions=[
                    _constant("index", 0),
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(condition,),
                        targets=("left", "right", "third"),
                    ),
                ],
            ),
            SSABlock(
                "left",
                instructions=[
                    _load("left_value", index, "left"),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "right",
                instructions=[
                    _load("right_value", index, "right"),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "third",
                instructions=[
                    _load("third_value", index, "third"),
                    SSAInstruction(IROpcode.JUMP, targets=("join",)),
                ],
            ),
            SSABlock(
                "join",
                instructions=[
                    _load("merged", index, "join"),
                    SSAInstruction(IROpcode.RETURN, operands=(merged,)),
                ],
            ),
        ),
        (index, condition, left_value, right_value, third_value, merged),
        length=1,
        parameters=(SSAParameter(condition),),
    )
    merged_report = analyze_repeated_load_availability(different_values)
    merge_candidate = next(item for item in merged_report.candidates if item.result == merged)
    assert merge_candidate.state.kind is AvailabilityKind.MAYBE_AVAILABLE
    assert not merge_candidate.forwardable


def test_repeated_load_is_killed_by_aliasing_store_and_unknown_call() -> None:
    index = _value("index", "entry", IRType.I64)
    dynamic_index = _value("dynamic_index", "entry", IRType.I64)
    before = _value("before", "entry")
    value = _value("value", "entry")
    after_store = _value("after_store", "entry")
    after_call = _value("after_call", "after_call")
    function = _function(
        (
            SSABlock(
                "entry",
                instructions=[
                    _constant("index", 0),
                    _constant("value", 17, type_=IRType.TRYTE),
                    _load("before", index, "entry"),
                    _store(dynamic_index, value, "entry"),
                    _load("after_store", index, "entry"),
                    SSAInstruction(
                        IROpcode.CALL, immediate="unknown", operands=(dynamic_index,)
                    ),
                    SSAInstruction(IROpcode.JUMP, targets=("after_call",)),
                ],
            ),
            SSABlock(
                "after_call",
                instructions=[
                    _load("after_call", index, "after_call"),
                    SSAInstruction(IROpcode.RETURN, operands=(after_call,)),
                ],
            ),
        ),
        (index, dynamic_index, before, value, after_store, after_call),
        length=2,
        parameters=(SSAParameter(dynamic_index),),
    )
    report = analyze_repeated_load_availability(function)
    store_successor = next(item for item in report.candidates if item.result == after_store)
    assert store_successor.state.kind in {
        AvailabilityKind.MAYBE_AVAILABLE,
        AvailabilityKind.UNKNOWN,
    }
    assert not store_successor.forwardable
    call_successor = next(item for item in report.candidates if item.result == after_call)
    assert call_successor.state.kind is AvailabilityKind.UNKNOWN
    assert not call_successor.forwardable


def test_loop_backedge_does_not_make_a_loop_carried_load_reusable() -> None:
    index = _value("index", "entry", IRType.I64)
    condition = _value("condition", "header")
    first = _value("first", "entry")
    body_load = _value("body_load", "body")
    exit_load = _value("exit_load", "exit")
    function = _function(
        (
            SSABlock(
                "entry",
                instructions=[
                    _constant("index", 0),
                    _load("first", index, "entry"),
                    SSAInstruction(IROpcode.JUMP, targets=("header",)),
                ],
            ),
            SSABlock(
                "header",
                instructions=[
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(condition,),
                        targets=("body", "exit", "exit"),
                    ),
                ],
            ),
            SSABlock(
                "body",
                instructions=[
                    _load("body_load", index, "body"),
                    SSAInstruction(IROpcode.JUMP, targets=("header",)),
                ],
            ),
            SSABlock(
                "exit",
                instructions=[
                    _load("exit_load", index, "exit"),
                    SSAInstruction(IROpcode.RETURN, operands=(exit_load,)),
                ],
            ),
        ),
        (index, condition, first, body_load, exit_load),
        length=1,
        parameters=(SSAParameter(condition),),
    )
    report = analyze_repeated_load_availability(function)
    assert report.cross_block_candidate_count == 0
    assert all(not item.forwardable for item in report.candidates)


def test_real_source_pipeline_reports_a_directly_stored_array_value() -> None:
    source = """\
fn main() -> tryte:
    mut values: tryte[2] = [0, 0]
    values[1] = 42
    mut counter: tryte = 0
    while counter < 1:
        counter += 1
    return values[1]
"""
    compilation = compile_source(source)
    function = compilation.ir.functions[0]
    ssa_function = SSABuilder.build_function(function)

    report = analyze_memory_value_availability(ssa_function)
    assert run_source(source) == 42
    assert report.forwardable_load_count == 1
    candidate = next(item for item in report.loads if item.forwardable)
    assert candidate.state.kind is AvailabilityKind.AVAILABLE
    assert candidate.state.value is not None
    assert candidate.reason == "SAME_EXACT_VALUE_ON_ALL_PATHS"
    assert candidate.cross_block_available

    transformed, forwarded = forward_available_stores(compilation.ir)
    assert forwarded == report.forwardable_load_count
    assert execute_ir(transformed) == execute_ir(compilation.ir) == 42


def test_repeated_load_experiment_preserves_loop_carried_value_semantics() -> None:
    source = """\
fn main() -> tryte:
    mut values: tryte[2] = [0, 0]
    values[1] = 42
    first: tryte = values[1]
    mut counter: tryte = 0
    while counter < 1:
        counter += 1
    return first + values[1]
"""
    compilation = compile_source(source)
    function = compilation.ir.functions[0]
    availability = analyze_repeated_load_availability(
        SSABuilder.build_function(function)
    )
    assert availability.cross_block_candidate_count >= 1

    transformed, forwarded = forward_available_loads(compilation.ir)
    assert forwarded == availability.cross_block_candidate_count
    assert execute_ir(transformed) == execute_ir(compilation.ir) == 84

    selected = next(
        item for item in availability.candidates if item.cross_block_available
    )
    selected_sites = {
        (function.name, selected.block, selected.instruction_index)
    }
    filtered, filtered_count = forward_available_loads(
        compilation.ir, selected_sites=selected_sites
    )
    assert filtered_count == 1
    assert execute_ir(filtered) == execute_ir(compilation.ir) == 84


def test_ssa_value_substitution_removes_proven_cross_block_load() -> None:
    source = """\
fn main() -> tryte:
    mut values: tryte[2] = [0, 0]
    values[1] = 42
    first: tryte = values[1]
    mut counter: tryte = 0
    while counter < 1:
        counter += 1
    return first + values[1]
"""
    compilation = compile_source(source)
    ssa_function = SSABuilder.build_function(compilation.ir.functions[0])
    availability = analyze_repeated_load_availability(ssa_function)
    cross_block = [candidate for candidate in availability.candidates if candidate.cross_block_available]
    phi_used_results = {
        value.name
        for block in ssa_function.blocks
        for phi in block.phis
        for value in phi.operands.values()
    }
    phi_used_candidates = [
        candidate
        for candidate in cross_block
        if candidate.result is not None and candidate.result.name in phi_used_results
    ]
    assert len(cross_block) == 2
    assert len(phi_used_candidates) == 1
    baseline_loads = sum(
        instruction.opcode is IROpcode.LOAD
        for function in compilation.ir.functions
        for block in function.blocks
        for instruction in block.instructions
    )

    transformed, forwarded = forward_available_loads_by_ssa_substitution(
        compilation.ir
    )
    transformed_loads = sum(
        instruction.opcode is IROpcode.LOAD
        for function in transformed.functions
        for block in function.blocks
        for instruction in block.instructions
    )

    assert forwarded == len(cross_block) - len(phi_used_candidates) == 1
    assert transformed_loads == baseline_loads - forwarded
    assert execute_ir(transformed) == execute_ir(compilation.ir) == 84


def test_ssa_value_substitution_keeps_reload_after_mutation() -> None:
    source = """\
fn main() -> tryte:
    mut values: tryte[1] = [0]
    values[0] = 42
    first: tryte = values[0]
    values[0] = 43
    mut counter: tryte = 0
    while counter < 1:
        counter += 1
    return first + values[0]
"""
    compilation = compile_source(source)
    transformed, forwarded = forward_available_loads_by_ssa_substitution(
        compilation.ir
    )

    assert forwarded == 0
    assert execute_ir(transformed) == execute_ir(compilation.ir) == 85
