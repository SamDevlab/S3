from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_sccp


def test_sccp_prunes_unreachable_branches() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    cond: tryte = 1\n"
        "    mut res: tryte = 0\n"
        "    match cond <=> 0:\n"
        "        1:\n"
        "            res = 42\n"
        "        else:\n"
        "            res = 99\n"
        "    return res\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, folded, br_removed = run_ssa_sccp(ssa_fn)

    assert br_removed >= 1
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 42


def test_sccp_propagates_constants_through_phi() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 0\n"
        "    mut i: tryte = 10\n"
        "    match i <=> 0:\n"
        "        1:\n"
        "            x = 100\n"
        "        else:\n"
        "            x = 100\n"
        "    return x\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 100
