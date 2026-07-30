from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa import SSABuilder, SSAPhiNode


def test_phi_placement_loop_variable() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut i: tryte = 0\n"
        "    while i < 3:\n"
        "        i = i + 1\n"
        "    return i\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    fn = result.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)

    # Check if any block contains a Phi node for variable `i`
    total_phis = sum(len(b.phis) for b in ssa_fn.blocks)
    assert total_phis >= 1
    for block in ssa_fn.blocks:
        for phi in block.phis:
            assert isinstance(phi, SSAPhiNode)
            assert phi.target is not None


def test_phi_placement_no_phi_in_straight_line_code() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut a: tryte = 10\n"
        "    a = a + 1\n"
        "    return a\n"
    )
    result = compile_source(source, mode=SyntaxMode.V0_6)
    fn = result.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)

    total_phis = sum(len(b.phis) for b in ssa_fn.blocks)
    assert total_phis == 0
