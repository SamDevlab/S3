from __future__ import annotations

import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.dynamic import (
    Allocator,
    BorrowConflictError,
    BufferBoundsError,
    BufferFullError,
    DynamicCompositeVector,
    DynamicText,
    MovedValueError,
)
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.semantic import ValueLayoutKind


def test_record_vector_supports_push_indexed_read_set_clone_and_slice_o0_o1() -> None:
    source = """\
record Pair:
    left: i64
    right: i64
fn main() -> i64:
    mut values: vector<Pair> = vector_new<Pair>(3)
    discard vector_push<Pair>(&mut values, Pair(left=1, right=2))
    discard vector_push<Pair>(&mut values, Pair(left=3, right=4))
    discard vector_set<Pair>(&mut values, 0, Pair(left=8, right=9))
    copy: vector<Pair> = vector_clone<Pair>(&values)
    window: vector<Pair> = vector_slice<Pair>(&copy, 0, 1)
    return vector_get<Pair>(&window, 0).left
"""

    assert run_source(source, optimization="O0") == 8
    assert run_source(source, optimization="O1") == 8
    compilation = compile_source(source)
    calls = [
        instruction.callee
        for function in compilation.ir.functions
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode.value == "call"
    ]
    assert any(name and "__s3_composite_vector__" in name for name in calls)
    assert compilation.semantic_model.contains_dynamic


def test_composite_vector_preserves_owned_text_clone_and_field_projection() -> None:
    source = """\
record Token:
    lexeme: text
    kind: tryte
fn main() -> i64:
    mut tokens: vector<Token> = vector_new<Token>(2)
    discard vector_push<Token>(&mut tokens, Token(lexeme=text_from_static("hello"), kind=3))
    copy: vector<Token> = vector_clone<Token>(&tokens)
    return text_len(&copy[0].lexeme)
"""

    assert run_source(source, optimization="O0") == 5
    assert run_source(source, optimization="O1") == 5


def test_composite_vector_round_trips_enum_payload_through_generic_storage() -> None:
    source = """\
enum State:
    Ready(code: i64)
    Empty
fn read(state: State) -> i64:
    match state:
        State.Ready(code):
            return code
        State.Empty:
            return 0
fn main() -> i64:
    mut states: vector<State> = vector_new<State>(1)
    discard vector_push<State>(&mut states, State.Ready(code=9))
    state: State = vector_get<State>(&states, 0)
    return read(state)
"""

    assert run_source(source, optimization="O0") == 9
    assert run_source(source, optimization="O1") == 9


def test_parametric_enum_vector_uses_the_same_specialized_layout_path() -> None:
    source = """\
enum Maybe<T: value>:
    Some(value: T)
    None
fn read(value: Maybe<i64>) -> i64:
    match value:
        Maybe<i64>.Some(value):
            return value
        Maybe<i64>.None:
            return 0
fn main() -> i64:
    mut values: vector<Maybe<i64>> = vector_new<Maybe<i64>>(1)
    discard vector_push<Maybe<i64>>(&mut values, Maybe<i64>.Some(value=13))
    item: Maybe<i64> = vector_get<Maybe<i64>>(&values, 0)
    return read(item)
"""

    assert run_source(source, optimization="O0") == 13
    assert run_source(source, optimization="O1") == 13


def test_composite_vector_runtime_enforces_capacity_borrow_move_and_drop() -> None:
    allocator = Allocator(max_bytes=64)
    owner = DynamicCompositeVector(
        "Token",
        ("i64", "text"),
        capacity=1,
        allocator=allocator,
    )
    text = DynamicText.from_static("x", allocator=allocator)
    owner.push((7, text))

    with pytest.raises(BufferFullError):
        owner.push((8, DynamicText.from_static("y", allocator=allocator)))
    with pytest.raises(BufferBoundsError):
        owner.get(1)

    owner._acquire_borrow(False)
    with pytest.raises(BorrowConflictError):
        owner.set(0, (9, text))
    owner._release_borrow(False)
    owner.set(0, (9, text))

    moved = owner.move()
    with pytest.raises(MovedValueError):
        owner.length
    moved.drop()
    with pytest.raises(MovedValueError):
        moved.length


def test_parametric_record_and_fixed_array_elements_use_one_generic_path() -> None:
    source = """\
record Box<T: value>:
    value: T
fn main() -> i64:
    mut values: vector<Box<i64>> = vector_new<Box<i64>>(1)
    discard vector_push<Box<i64>>(&mut values, Box<i64>(value=17))
    return vector_get<Box<i64>>(&values, 0).value
"""

    compilation = compile_source(source)
    assert run_source(source, optimization="O0") == 17
    assert run_source(source, optimization="O1") == 17
    assert compilation.semantic_model.fixed_value_layout(
        ast.NominalType("__s3_generic_type__Box__i64", compilation.ast.location)
    ).kind is ValueLayoutKind.RECORD


def test_fixed_array_vector_elements_are_flattened_deterministically() -> None:
    source = """\
fn main() -> i64:
    mut values: vector<i64[2]> = vector_new<i64[2]>(1)
    pair: i64[2] = [1, 2]
    discard vector_push<i64[2]>(&mut values, pair)
    return vector_get<i64[2]>(&values, 0)[1]
"""

    first = compile_source(source)
    second = compile_source(source)
    assert run_source(source) == 2
    assert first.ir.to_dict() == second.ir.to_dict()


def test_composite_vector_rejects_recursive_and_nested_dynamic_elements() -> None:
    recursive = """\
record Node:
    next: Node
fn main() -> i64:
    mut values: vector<Node> = vector_new<Node>(1)
    return vector_len<Node>(&values)
"""
    with pytest.raises(SemanticError) as recursive_error:
        compile_source(recursive)
    assert recursive_error.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_PROGRAM

    nested = """\
fn main() -> i64:
    mut values: vector<vector<i64>> = vector_new<vector<i64>>(1)
    return vector_len<vector<i64>>(&values)
"""
    with pytest.raises(SemanticError) as nested_error:
        compile_source(nested)
    assert nested_error.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE


def test_composite_vector_push_reuses_existing_owned_move_rule() -> None:
    source = """\
record Token:
    lexeme: text
fn main() -> i64:
    mut tokens: vector<Token> = vector_new<Token>(1)
    token: Token = Token(lexeme=text_from_static("x"))
    discard vector_push<Token>(&mut tokens, token)
    return text_len(&token.lexeme)
"""

    with pytest.raises(SemanticError) as error:
        compile_source(source)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_USE_AFTER_MOVE
