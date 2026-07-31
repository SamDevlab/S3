from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_strength_reduction


def test_strength_reduction_self_addition_is_not_counted_without_rewrite() -> None:
    source = (
        "fn helper(a: tryte) -> tryte:\n"
        "    double_a: tryte = a + a\n"
        "    return double_a\n"
        "fn main() -> tryte:\n"
        "    return helper(15)\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, reductions = run_ssa_strength_reduction(ssa_fn)

    assert reductions == 0
    assert opt_ssa.blocks == ssa_fn.blocks
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 30


def test_strength_reduction_double_inversion() -> None:
    source = (
        "fn helper(x: tryte) -> tryte:\n"
        "    inv1: tryte = ~x\n"
        "    inv2: tryte = ~inv1\n"
        "    return inv2\n"
        "fn main() -> tryte:\n"
        "    return helper(7)\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, reductions = run_ssa_strength_reduction(ssa_fn)

    assert reductions >= 1
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 7

