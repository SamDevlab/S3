from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_dse


def test_dse_eliminates_overwritten_stores() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 10\n"
        "    x = 20\n"
        "    return x\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, removed = run_ssa_dse(ssa_fn)

    assert removed >= 1
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 20


def test_dse_preserves_stores_before_load() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 15\n"
        "    mut y: tryte = x + 5\n"
        "    x = 30\n"
        "    return y + x\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 50
