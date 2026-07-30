from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_adce


def test_adce_removes_dead_computation_chains() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    a: tryte = 10\n"
        "    b: tryte = a + 5\n"
        "    c: tryte = b + 20\n"
        "    res: tryte = 42\n"
        "    return res\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, removed = run_ssa_adce(ssa_fn)

    assert removed >= 1
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 42


def test_adce_preserves_side_effects() -> None:
    source = (
        "fn helper() -> tryte:\n"
        "    return 100\n"
        "fn main() -> tryte:\n"
        "    mut call_res: tryte = helper()\n"
        "    return 5\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 5
