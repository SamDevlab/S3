from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_gvn


def test_gvn_detects_equivalent_expressions() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    a: tryte = 10\n"
        "    b: tryte = 20\n"
        "    x: tryte = a + b\n"
        "    y: tryte = a + b\n"
        "    return x + y\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, eliminated = run_ssa_gvn(ssa_fn)

    assert eliminated >= 1
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 60


def test_gvn_across_dominating_blocks() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut cond: tryte = 1\n"
        "    a: tryte = 15\n"
        "    b: tryte = 25\n"
        "    base: tryte = a + b\n"
        "    mut res: tryte = 0\n"
        "    match cond <=> 0:\n"
        "        1:\n"
        "            res = a + b\n"
        "        else:\n"
        "            res = base\n"
        "    return res\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 40
