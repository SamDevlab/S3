from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_constant_propagation


def test_ssa_constant_propagation_assignments() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 10\n"
        "    mut b: tryte = a + 5\n"
        "    return b\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa = run_ssa_constant_propagation(ssa_fn)

    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 15


def test_ssa_constant_propagation_phi_and_branches() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 0\n"
        "    mut i: tryte = 1\n"
        "    match i <=> 0:\n"
        "        1:\n"
        "            x = 42\n"
        "        else:\n"
        "            x = 42\n"
        "    return x\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa = run_ssa_constant_propagation(ssa_fn)

    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 42


def test_ssa_constant_propagation_partial_constants_and_loops() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut sum: tryte = 0\n"
        "    mut i: tryte = 0\n"
        "    while i < 3:\n"
        "        sum = sum + 5\n"
        "        i = i + 1\n"
        "    return sum\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 15


def test_ssa_constant_propagation_side_effect_preservation() -> None:
    source = (
        "fn side_effect() -> tryte:\n"
        "    return 7\n"
        "fn main() -> tryte:\n"
        "    mut a: tryte = side_effect()\n"
        "    mut b: tryte = a + 0\n"
        "    return b\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 7
