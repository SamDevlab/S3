from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_licm


def test_licm_hoists_invariant_computation() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut i: tryte = 0\n"
        "    mut sum: tryte = 0\n"
        "    c1: tryte = 10\n"
        "    c2: tryte = 20\n"
        "    while i < 3:\n"
        "        inv: tryte = c1 + c2\n"
        "        sum = sum + inv\n"
        "        i = i + 1\n"
        "    return sum\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, hoisted = run_ssa_licm(ssa_fn)

    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 90


def test_licm_preserves_side_effects_in_loop() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut i: tryte = 0\n"
        "    mut total: tryte = 0\n"
        "    while i < 2:\n"
        "        total = total + 5\n"
        "        i = i + 1\n"
        "    return total\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 10
