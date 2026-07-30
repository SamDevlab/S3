from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_cse


def test_cse_redundant_addition() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 10\n"
        "    mut y: tryte = 20\n"
        "    mut a: tryte = x + y\n"
        "    mut b: tryte = x + y\n"
        "    return a + b\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa = run_ssa_cse(ssa_fn)

    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 60


def test_cse_across_dominating_blocks() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut cond: tryte = 1\n"
        "    mut x: tryte = 10\n"
        "    mut y: tryte = 20\n"
        "    mut base: tryte = x + y\n"
        "    mut res: tryte = 0\n"
        "    match cond <=> 0:\n"
        "        1:\n"
        "            res = x + y\n"
        "        else:\n"
        "            res = base\n"
        "    return res\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 30


def test_cse_preserves_semantics_with_different_operands() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 5\n"
        "    mut y: tryte = 10\n"
        "    mut z: tryte = 15\n"
        "    mut a: tryte = x + y\n"
        "    mut b: tryte = x + z\n"
        "    return a + b\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 35
