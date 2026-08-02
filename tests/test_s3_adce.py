from __future__ import annotations

from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.ir import IROpcode
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


def test_adce_preserves_discarded_aggregate_call_as_single_instruction() -> None:
    source = (
        "record Pair:\n"
        "    left: tryte\n"
        "    right: trit\n"
        "fn make() -> Pair:\n"
        "    return Pair(left=6, right=-1)\n"
        "fn main() -> tryte:\n"
        "    discard make()\n"
        "    return 5\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = next(function for function in compilation.ir.functions if function.name == "main")
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, _removed = run_ssa_adce(ssa_fn)
    calls = [
        instruction
        for block in opt_ssa.blocks
        for instruction in block.instructions
        if instruction.opcode is IROpcode.CALL and instruction.immediate == "make"
    ]

    assert len(calls) == 1
    assert len(calls[0].results) == 2
