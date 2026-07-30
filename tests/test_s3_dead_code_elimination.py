from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_dead_code_elimination


def test_dead_code_elimination_unused_variables() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    a: tryte = 10\n"
        "    b: tryte = a + 50\n"
        "    return a\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa = run_ssa_dead_code_elimination(ssa_fn)

    orig_inst_count = sum(len(b.instructions) for b in ssa_fn.blocks)
    opt_inst_count = sum(len(b.instructions) for b in opt_ssa.blocks)
    assert opt_inst_count < orig_inst_count

    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 10


def test_dead_code_elimination_preserves_side_effects() -> None:
    source = (
        "fn helper() -> tryte:\n"
        "    return 42\n"
        "fn main() -> tryte:\n"
        "    mut dead_res: tryte = helper()\n"
        "    return 1\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 1


def test_dead_code_elimination_dead_phis_and_loops() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut i: tryte = 0\n"
        "    mut dead_phi: tryte = 0\n"
        "    while i < 3:\n"
        "        dead_phi = dead_phi + 1\n"
        "        i = i + 1\n"
        "    return i\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 3
