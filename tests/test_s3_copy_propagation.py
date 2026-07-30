from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_copy_propagation


def test_copy_propagation_basic_aliases() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 100\n"
        "    mut b: tryte = a\n"
        "    mut c: tryte = b\n"
        "    return c\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa = run_ssa_copy_propagation(ssa_fn)

    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 100


def test_copy_propagation_phi_and_control_flow() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut cond: tryte = 1\n"
        "    mut x: tryte = 10\n"
        "    mut y: tryte = 20\n"
        "    mut res: tryte = 0\n"
        "    match cond <=> 0:\n"
        "        1:\n"
        "            res = x\n"
        "        else:\n"
        "            res = y\n"
        "    mut final_val: tryte = res\n"
        "    return final_val\n"
    )
    res_pos = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res_pos == 10


def test_copy_propagation_loops() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut i: tryte = 0\n"
        "    mut temp: tryte = i\n"
        "    while temp < 5:\n"
        "        i = temp + 1\n"
        "        temp = i\n"
        "    return temp\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 5
