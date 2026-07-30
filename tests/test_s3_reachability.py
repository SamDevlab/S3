from __future__ import annotations

from bootstrap.s3.cfg import ControlFlowGraph, remove_unreachable_blocks_cfg
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def test_reachability_all_blocks_reachable() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 1\n"
        "    return a\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    fn = result.ir.functions[0]
    cfg = ControlFlowGraph.build(fn)
    assert cfg.unreachable_nodes() == set()


def test_reachability_unreachable_block_elimination() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 1\n"
        "    match 0:\n"
        "        0:\n"
        "            a = 10\n"
        "        else:\n"
        "            a = 20\n"
        "    return a\n"
    )
    # Lowering already eliminates dead branch for match 0, leaving unreachable blocks if any
    result = compile_source(source, mode=SyntaxMode.V0_6)
    fn = result.ir.functions[0]
    cleaned = remove_unreachable_blocks_cfg(fn)
    cfg_before = ControlFlowGraph.build(fn)
    cfg_after = ControlFlowGraph.build(cleaned)
    assert len(cfg_after.nodes) <= len(cfg_before.nodes)
    assert cfg_after.unreachable_nodes() == set()
