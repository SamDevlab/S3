from __future__ import annotations

from bootstrap.s3.cfg import ControlFlowGraph
from bootstrap.s3.dominance import DominatorTree
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.memory_ssa import MemoryDef, MemorySSA, MemoryUse
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa import SSABuilder


def test_memory_ssa_construction() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 10\n"
        "    mut y: tryte = x + 5\n"
        "    x = 20\n"
        "    return x + y\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    cfg = ControlFlowGraph.build(fn)
    dom_tree = DominatorTree.build(cfg)
    ssa_fn = SSABuilder.build_function(fn)

    mem_ssa = MemorySSA.build(ssa_fn, cfg, dom_tree)
    assert isinstance(mem_ssa, MemorySSA)
    assert len(mem_ssa.defs) > 0
    assert len(mem_ssa.uses) > 0
    assert isinstance(mem_ssa.defs[0], MemoryDef)
    assert isinstance(mem_ssa.uses[0], MemoryUse)
