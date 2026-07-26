"""Execution tests for match statement and match expression fallback in S3 0.52."""

import pytest

from bootstrap.s3.pipeline import run_source


@pytest.mark.parametrize("opt_level", ["O0", "O1"])
def test_execution_match_statement_fallback(opt_level: str):
    source = """
fn main() -> tryte:
    mut res: tryte = 0
    sel: trit = -1
    match sel:
        1:
            res = 10
        else:
            res = 99
    return res
"""
    assert run_source(source, optimization=opt_level) == 99


@pytest.mark.parametrize("opt_level", ["O0", "O1"])
def test_execution_match_statement_explicit_branch(opt_level: str):
    source = """
fn main() -> tryte:
    mut res: tryte = 0
    sel: trit = 1
    match sel:
        1:
            res = 10
        else:
            res = 99
    return res
"""
    assert run_source(source, optimization=opt_level) == 10


@pytest.mark.parametrize("opt_level", ["O0", "O1"])
def test_execution_match_expression_fallback(opt_level: str):
    source = """
fn main() -> tryte:
    sel: trit = 0
    val: tryte = match sel:
        1: 50
        else: 100
    return val
"""
    assert run_source(source, optimization=opt_level) == 100


@pytest.mark.parametrize("opt_level", ["O0", "O1"])
def test_execution_nested_match_fallback(opt_level: str):
    source = """
fn main() -> tryte:
    a: trit = -1
    b: trit = 1
    res: tryte = match a:
        1: 10
        else: match b:
            0: 20
            else: 30
    return res
"""
    assert run_source(source, optimization=opt_level) == 30


@pytest.mark.parametrize("opt_level", ["O0", "O1"])
def test_execution_match_fallback_in_loop(opt_level: str):
    source = """
fn helper(sel: trit) -> tryte:
    mut res: tryte = 0
    match sel:
        0:
            res = 5
        else:
            res = 1
    return res

fn main() -> tryte:
    mut sum: tryte = 0
    sum += helper(-1)
    sum += helper(0)
    sum += helper(1)
    return sum
"""
    assert run_source(source, optimization=opt_level) == 7
