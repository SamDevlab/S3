from __future__ import annotations

from bootstrap.s3.cfg import ControlFlowGraph
from bootstrap.s3.dominance import DominatorTree
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABuilder, validate_ssa


def test_ssa_pipeline_with_complex_control_flow() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut total: tryte = 0\n"
        "    mut i: tryte = 0\n"
        "    while i < 3:\n"
        "        match i <=> 1:\n"
        "            -1:\n"
        "                total = total + 10\n"
        "            0:\n"
        "                total = total + 20\n"
        "            else:\n"
        "                total = total + 30\n"
        "        i = i + 1\n"
        "    return total\n"
    )
    # Build SSA from IR and validate
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    for fn in compilation.ir.functions:
        cfg = ControlFlowGraph.build(fn)
        dom_tree = DominatorTree.build(cfg)
        ssa_fn = SSABuilder.build_function(fn)
        validate_ssa(ssa_fn, cfg, dom_tree)

    # Execution behavior must remain identical
    res = run_source(source, mode=SyntaxMode.V0_6)
    assert res == 60
