from __future__ import annotations

import platform

import pytest

from bootstrap.s3.backends.x86_64 import NativeBackendError, NativeToolchain, generate_native_assembly
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source


pytestmark = [pytest.mark.s3_native, pytest.mark.s3_differential]


@pytest.fixture(scope="session")
def native_toolchain() -> NativeToolchain:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("composite vector native matrix requires Linux x86-64")
    try:
        return NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))


def _run_native(
    source: str,
    expected: int,
    native_toolchain: NativeToolchain,
    output,
) -> None:
    for optimization in ("O0", "O1"):
        program = compile_source(
            source,
            optimization,
            mode=SyntaxMode.V0_6,
        ).assembly
        assert run_source(source, optimization=optimization, mode=SyntaxMode.V0_6) == expected
        assembly = generate_native_assembly(program)
        executable = native_toolchain.build(
            assembly,
            output / optimization.lower(),
        )
        completed = native_toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stderr == ""
        assert completed.stdout == f"program returned: {expected}\n"


def _run_native_failure(
    source: str,
    message: str,
    native_toolchain: NativeToolchain,
    output,
) -> None:
    for optimization in ("O0", "O1"):
        program = compile_source(
            source,
            optimization,
            mode=SyntaxMode.V0_6,
        ).assembly
        executable = native_toolchain.build(
            generate_native_assembly(program),
            output / optimization.lower(),
        )
        completed = native_toolchain.run(executable)
        assert completed.returncode != 0
        assert completed.stdout == ""
        assert completed.stderr == message


def test_native_composite_vector_record_and_nested_record_matrix(
    native_toolchain: NativeToolchain,
    tmp_path,
) -> None:
    source = """\
record Inner:
    left: i64
    right: i64
record Outer:
    inner: Inner
    tag: tryte
fn main() -> i64:
    mut values: vector<Outer> = vector_new<Outer>(1)
    discard vector_push<Outer>(&mut values, Outer(inner=Inner(left=7, right=11), tag=3))
    return vector_get<Outer>(&values, 0).inner.right
"""
    _run_native(source, 11, native_toolchain, tmp_path / "nested-record")


def test_native_composite_vector_enum_matrix(
    native_toolchain: NativeToolchain,
    tmp_path,
) -> None:
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
    return read(vector_get<State>(&states, 0))
"""
    _run_native(source, 9, native_toolchain, tmp_path / "enum")


def test_native_composite_vector_parametric_record_and_enum_matrix(
    native_toolchain: NativeToolchain,
    tmp_path,
) -> None:
    record_source = """\
record Box<T: value>:
    value: T
fn main() -> i64:
    mut values: vector<Box<i64>> = vector_new<Box<i64>>(1)
    discard vector_push<Box<i64>>(&mut values, Box<i64>(value=17))
    return vector_get<Box<i64>>(&values, 0).value
"""
    enum_source = """\
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
    return read(vector_get<Maybe<i64>>(&values, 0))
"""
    _run_native(record_source, 17, native_toolchain, tmp_path / "parametric-record")
    _run_native(enum_source, 13, native_toolchain, tmp_path / "parametric-enum")


def test_native_composite_vector_fixed_array_and_f64_matrix(
    native_toolchain: NativeToolchain,
    tmp_path,
) -> None:
    array_source = """\
fn main() -> i64:
    mut values: vector<i64[2]> = vector_new<i64[2]>(1)
    pair: i64[2] = [1, 2]
    discard vector_push<i64[2]>(&mut values, pair)
    item: i64[2] = vector_get<i64[2]>(&values, 0)
    return item[1]
"""
    f64_source = """\
record Sample:
    first: f64
    second: f64
fn main() -> i64:
    mut values: vector<Sample> = vector_new<Sample>(1)
    discard vector_push<Sample>(&mut values, Sample(first=1.5, second=2.5))
    item: Sample = vector_get<Sample>(&values, 0)
    match item.second <=> 2.5:
        -1:
            return -1
        0:
            return 1
        else:
            return 0
"""
    _run_native(array_source, 2, native_toolchain, tmp_path / "fixed-array")
    _run_native(f64_source, 1, native_toolchain, tmp_path / "f64")


def test_native_composite_vector_owned_text_operations(
    native_toolchain: NativeToolchain,
    tmp_path,
) -> None:
    source = """\
record Token:
    lexeme: text
    kind: tryte
fn main() -> i64:
    mut values: vector<Token> = vector_new<Token>(2)
    discard vector_push<Token>(&mut values, Token(lexeme=text_from_static("old"), kind=1))
    discard vector_push<Token>(&mut values, Token(lexeme=text_from_static("new"), kind=2))
    copy: vector<Token> = vector_clone<Token>(&values)
    mut window: vector<Token> = vector_slice<Token>(&copy, 1, 2)
    discard vector_set<Token>(&mut values, 0, Token(lexeme=text_from_static("reset"), kind=3))
    item: Token = vector_pop<Token>(&mut window)
    return text_len(&item.lexeme)
"""
    _run_native(source, 3, native_toolchain, tmp_path / "owned-text")


def test_native_composite_vector_capacity_and_bounds_are_fail_closed(
    native_toolchain: NativeToolchain,
    tmp_path,
) -> None:
    record = """\
record Pair:
    left: i64
    right: i64
"""
    bounds_source = record + """\
fn main() -> i64:
    mut values: vector<Pair> = vector_new<Pair>(1)
    discard vector_push<Pair>(&mut values, Pair(left=1, right=2))
    return vector_get<Pair>(&values, 1).left
"""
    capacity_source = record + """\
fn main() -> i64:
    mut values: vector<Pair> = vector_new<Pair>(1)
    discard vector_push<Pair>(&mut values, Pair(left=1, right=2))
    discard vector_push<Pair>(&mut values, Pair(left=3, right=4))
    return 0
"""
    _run_native_failure(
        bounds_source,
        "runtime error: bounds\n",
        native_toolchain,
        tmp_path / "bounds",
    )
    _run_native_failure(
        capacity_source,
        "runtime error: dynamic buffer capacity\n",
        native_toolchain,
        tmp_path / "capacity",
    )


def test_native_composite_vector_len_capacity_and_reserve(
    native_toolchain: NativeToolchain,
    tmp_path,
) -> None:
    source = """\
record Pair:
    left: i64
    right: i64
fn main() -> i64:
    mut values: vector<Pair> = vector_new<Pair>(1)
    discard vector_push<Pair>(&mut values, Pair(left=4, right=7))
    before: i64 = vector_capacity<Pair>(&values)
    discard vector_reserve<Pair>(&mut values, 3)
    after: i64 = vector_capacity<Pair>(&values)
    return vector_len<Pair>(&values) * 100 + before * 10 + after
"""
    _run_native(source, 113, native_toolchain, tmp_path / "length-capacity")


def test_composite_vector_native_assembly_is_deterministic() -> None:
    source = """\
record Pair:
    left: i64
    right: i64
fn main() -> i64:
    mut values: vector<Pair> = vector_new<Pair>(1)
    discard vector_push<Pair>(&mut values, Pair(left=4, right=7))
    return vector_get<Pair>(&values, 0).right
"""
    first = compile_source(source, "O0", mode=SyntaxMode.V0_6).assembly
    second = compile_source(source, "O0", mode=SyntaxMode.V0_6).assembly
    assert generate_native_assembly(first) == generate_native_assembly(second)


def test_composite_vector_use_after_move_is_rejected_before_native_lowering() -> None:
    source = """\
record Token:
    lexeme: text
fn main() -> i64:
    mut values: vector<Token> = vector_new<Token>(1)
    token: Token = Token(lexeme=text_from_static("x"))
    discard vector_push<Token>(&mut values, token)
    return text_len(&token.lexeme)
"""
    for optimization in ("O0", "O1"):
        with pytest.raises(SemanticError) as error:
            compile_source(source, optimization, mode=SyntaxMode.V0_6)
        assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_USE_AFTER_MOVE
