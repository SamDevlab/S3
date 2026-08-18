from __future__ import annotations

import pytest

from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.results import Option, Result


def test_hosted_result_explicit_branches_and_composition() -> None:
    parsed: Result[int, str] = Result.ok(4)
    rejected: Result[int, str] = Result.err("bad input")

    assert parsed.fold(lambda value: value + 1, lambda _: -1) == 5
    assert rejected.fold(lambda value: value + 1, lambda error: len(error)) == 9
    assert parsed.bind(lambda value: Result.ok(value * 2)).value_or(-1) == 8
    assert rejected.bind(lambda value: Result.ok(value * 2)).error_or("") == "bad input"
    assert rejected.map(lambda value: value * 2).is_err


def test_hosted_option_explicit_present_absent_and_map() -> None:
    present = Option.some(7)
    absent: Option[int] = Option.none()

    assert present.fold(lambda value: value + 1, lambda: -1) == 8
    assert absent.fold(lambda value: value + 1, lambda: -1) == -1
    assert present.map(lambda value: value * 3).value_or(0) == 21
    assert absent.map(lambda value: value * 3).is_none
    assert absent.bind(lambda value: Option.some(value * 3)).value_or(11) == 11


def test_generic_result_and_option_use_explicit_match_at_source_level() -> None:
    source = """\
enum Result<T: value, E: value>:
    Ok(value: T)
    Err(error: E)
enum Option<T: value>:
    Some(value: T)
    None
fn inspect(result: Result<i64, i64>, option: Option<i64>) -> i64:
    match result:
        Result<i64, i64>.Ok(value):
            match option:
                Option<i64>.Some(value):
                    return value + value
                Option<i64>.None:
                    return value
        Result<i64, i64>.Err(error):
            return 0 - error
fn main() -> i64:
    return inspect(Result<i64, i64>.Ok(value=7), Option<i64>.Some(value=5))
"""

    assert run_source(source, optimization="O0") == 10
    assert run_source(source, optimization="O1") == 10
    compilation = compile_source(source, optimization="O0")
    assert "__s3_generic_type__Result__i64__i64" in {
        enum.name for enum in compilation.ast.enums
    }
    assert "__s3_generic_type__Option__i64" in {
        enum.name for enum in compilation.ast.enums
    }


def test_result_bind_requires_explicit_result_value() -> None:
    with pytest.raises(TypeError, match="must return Result"):
        Result.ok(1).bind(lambda _: 2)  # type: ignore[arg-type]


def test_result_and_option_do_not_use_sentinel_payloads() -> None:
    assert Result.ok(None).is_ok
    assert Result.err(None).is_err
    assert Option.some(None).is_some
    assert Option.none().is_none
