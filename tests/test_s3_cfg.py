from __future__ import annotations

from bootstrap.s3.cfg import ControlFlowGraph
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def test_cfg_construction_simple_program() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 10\n"
        "    return a\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    fn = result.ir.functions[0]
    cfg = ControlFlowGraph.build(fn)
    assert cfg.entry_name == "entry"
    assert "entry" in cfg.nodes
    assert len(cfg.nodes) == len(fn.blocks)


def test_cfg_construction_with_loop_and_branches() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut i: tryte = 0\n"
        "    while i < 5:\n"
        "        i = i + 1\n"
        "    return i\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    fn = result.ir.functions[0]
    cfg = ControlFlowGraph.build(fn)
    assert len(cfg.nodes) > 1
    # Check predecessors and successors tracking
    for name, node in cfg.nodes.items():
        for succ in node.successors:
            assert name in cfg.nodes[succ].predecessors
