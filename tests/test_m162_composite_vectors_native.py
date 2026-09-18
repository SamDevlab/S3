from __future__ import annotations

import platform

import pytest

from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativeToolchain,
    X8664Backend,
    generate_native_assembly,
)
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source


pytestmark = [pytest.mark.s3_native, pytest.mark.s3_differential]


def _composite_native_corpus() -> tuple[tuple[str, str, int], ...]:
    cases: list[tuple[str, str, int]] = []
    for value in range(1, 9):
        cases.extend(
            (
                (
                    f"pair-read-{value}",
                    f"""\
record Pair:
    left: i64
    right: i64
fn main() -> i64:
    mut values: vector<Pair> = vector_new<Pair>(1)
    discard vector_push<Pair>(&mut values, Pair(left={value}, right={value + 1}))
    return vector_get<Pair>(&values, 0).right
""",
                    value + 1,
                ),
                (
                    f"pair-replace-{value}",
                    f"""\
record Pair:
    left: i64
    right: i64
fn main() -> i64:
    mut values: vector<Pair> = vector_new<Pair>(1)
    discard vector_push<Pair>(&mut values, Pair(left=0, right=0))
    discard vector_set<Pair>(&mut values, 0, Pair(left={value}, right={value + 2}))
    return vector_get<Pair>(&values, 0).left
""",
                    value,
                ),
                (
                    f"pair-clone-{value}",
                    f"""\
record Pair:
    left: i64
    right: i64
fn main() -> i64:
    mut values: vector<Pair> = vector_new<Pair>(1)
    discard vector_push<Pair>(&mut values, Pair(left={value}, right={value + 3}))
    copy: vector<Pair> = vector_clone<Pair>(&values)
    return vector_get<Pair>(&copy, 0).right
""",
                    value + 3,
                ),
                (
                    f"pair-slice-{value}",
                    f"""\
record Pair:
    left: i64
    right: i64
fn main() -> i64:
    mut values: vector<Pair> = vector_new<Pair>(2)
    discard vector_push<Pair>(&mut values, Pair(left={value}, right={value + 4}))
    discard vector_push<Pair>(&mut values, Pair(left=0, right=0))
    window: vector<Pair> = vector_slice<Pair>(&values, 0, 1)
    return vector_get<Pair>(&window, 0).left
""",
                    value,
                ),
                (
                    f"enum-{value}",
                    f"""\
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
    mut values: vector<State> = vector_new<State>(1)
    discard vector_push<State>(&mut values, State.Ready(code={value + 5}))
    return read(vector_get<State>(&values, 0))
""",
                    value + 5,
                ),
                (
                    f"parametric-record-{value}",
                    f"""\
record Box<T: value>:
    value: T
fn main() -> i64:
    mut values: vector<Box<i64>> = vector_new<Box<i64>>(1)
    discard vector_push<Box<i64>>(&mut values, Box<i64>(value={value + 6}))
    return vector_get<Box<i64>>(&values, 0).value
""",
                    value + 6,
                ),
                (
                    f"parametric-enum-{value}",
                    f"""\
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
    discard vector_push<Maybe<i64>>(&mut values, Maybe<i64>.Some(value={value + 7}))
    return read(vector_get<Maybe<i64>>(&values, 0))
""",
                    value + 7,
                ),
                (
                    f"fixed-array-{value}",
                    f"""\
fn main() -> i64:
    mut values: vector<i64[2]> = vector_new<i64[2]>(1)
    pair: i64[2] = [{value}, {value + 8}]
    discard vector_push<i64[2]>(&mut values, pair)
    return vector_get<i64[2]>(&values, 0)[1]
""",
                    value + 8,
                ),
            )
        )
    return tuple(cases)


COMPOSITE_NATIVE_CORPUS = _composite_native_corpus()


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


def test_native_composite_vector_move_and_multiple_vector_types(
    native_toolchain: NativeToolchain,
    tmp_path,
) -> None:
    source = """\
record Pair:
    left: i64
    right: i64
fn consume(values: vector<Pair>) -> i64:
    return vector_get<Pair>(&values, 0).left
fn main() -> i64:
    mut pairs: vector<Pair> = vector_new<Pair>(1)
    mut numbers: vector<i64> = vector_new<i64>(1)
    discard vector_push<Pair>(&mut pairs, Pair(left=8, right=13))
    discard i64_vector_push(&mut numbers, 5)
    return consume(pairs) + i64_vector_get(&numbers, 0)
"""
    _run_native(source, 13, native_toolchain, tmp_path / "move-multiple")


def test_native_composite_vector_compact_ea_falls_back_safely(
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
    return vector_get<Pair>(&values, 0).right
"""
    for optimization in ("O0", "O1"):
        program = compile_source(source, optimization, mode=SyntaxMode.V0_6).assembly
        summary = X8664Backend(native_policy="compact-ea").explain_native_policy(program)
        assert summary.effective_policy.value == "baseline"
        assert summary.fallback_reason_counts == {"reference_operations_present": 1}
        executable = native_toolchain.build(
            generate_native_assembly(program, native_policy="compact-ea"),
            tmp_path / f"compact-{optimization.lower()}",
        )
        completed = native_toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == "program returned: 7\n"
        assert completed.stderr == ""


@pytest.mark.parametrize(
    ("name", "source", "expected"),
    COMPOSITE_NATIVE_CORPUS,
    ids=[case[0] for case in COMPOSITE_NATIVE_CORPUS],
)
def test_native_composite_vector_differential_corpus(
    name: str,
    source: str,
    expected: int,
    native_toolchain: NativeToolchain,
    tmp_path,
) -> None:
    _run_native(source, expected, native_toolchain, tmp_path / name)


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
