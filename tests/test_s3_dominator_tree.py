from __future__ import annotations

from bootstrap.s3.cfg import ControlFlowGraph
from bootstrap.s3.dominance import DominatorTree
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def test_dominator_tree_linear_program() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 10\n"
        "    return a\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    fn = result.ir.functions[0]
    cfg = ControlFlowGraph.build(fn)
    dom_tree = DominatorTree.build(cfg)

    assert dom_tree.entry_name == "entry"
    assert dom_tree.dominates("entry", "entry")
    assert dom_tree.idom["entry"] is None


def test_dominator_tree_branch_and_loop() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut i: tryte = 0\n"
        "    while i < 3:\n"
        "        i = i + 1\n"
        "    return i\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    fn = result.ir.functions[0]
    cfg = ControlFlowGraph.build(fn)
    dom_tree = DominatorTree.build(cfg)

    # Every reachable node must be dominated by entry
    for node_name in cfg.reachable_nodes():
        assert dom_tree.dominates("entry", node_name)
