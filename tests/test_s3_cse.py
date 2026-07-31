from __future__ import annotations

from bootstrap.s3.ir import IRMemoryObject, IROpcode, IRType
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABlock, SSAFunction, SSAInstruction, SSAParameter, SSAValue, SSABuilder
from bootstrap.s3.ssa_opt import run_ssa_cse


def _value(
    name: str,
    original_register: int,
    type_name: IRType = IRType.TRYTE,
    block: str = "entry",
) -> SSAValue:
    return SSAValue(
        name,
        original_register=original_register,
        type=type_name,
        def_block=block,
    )


def test_cse_redundant_addition() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 10\n"
        "    mut y: tryte = 20\n"
        "    mut a: tryte = x + y\n"
        "    mut b: tryte = x + y\n"
        "    return a + b\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa = run_ssa_cse(ssa_fn)

    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 60


def test_cse_across_dominating_blocks() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut cond: tryte = 1\n"
        "    mut x: tryte = 10\n"
        "    mut y: tryte = 20\n"
        "    mut base: tryte = x + y\n"
        "    mut res: tryte = 0\n"
        "    match cond <=> 0:\n"
        "        1:\n"
        "            res = x + y\n"
        "        else:\n"
        "            res = base\n"
        "    return res\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 30


def test_cse_preserves_semantics_with_different_operands() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut x: tryte = 5\n"
        "    mut y: tryte = 10\n"
        "    mut z: tryte = 15\n"
        "    mut a: tryte = x + y\n"
        "    mut b: tryte = x + z\n"
        "    return a + b\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 35


def test_cse_preserves_trit_return_type_and_metadata_when_rewriting() -> None:
    param = _value("param", 0)
    left = _value("left", 1)
    right = _value("right", 2)
    first = _value("first", 3, IRType.TRIT)
    second = _value("second", 4, IRType.TRIT)
    memory = IRMemoryObject(index=0, element_type=IRType.TRYTE, length=3, mutable=True)
    ssa_fn = SSAFunction(
        name="keeps_trit_metadata",
        parameters=(SSAParameter(param),),
        values=(param, left, right, first, second),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=left, immediate=10),
                    SSAInstruction(IROpcode.CONST, result=right, immediate=20),
                    SSAInstruction(IROpcode.COMPARE, result=first, operands=(left, right)),
                    SSAInstruction(IROpcode.COMPARE, result=second, operands=(left, right)),
                    SSAInstruction(IROpcode.RETURN, operands=(second,)),
                ],
            ),
        ),
        memory_objects=(memory,),
        return_type=IRType.TRIT,
    )

    optimized = run_ssa_cse(ssa_fn)

    assert optimized.name == ssa_fn.name
    assert optimized.parameters == ssa_fn.parameters
    assert optimized.memory_objects == ssa_fn.memory_objects
    assert optimized.return_type is IRType.TRIT


def test_cse_preserves_tryte_return_type_and_metadata_when_rewriting() -> None:
    param = _value("param", 0)
    left = _value("left", 1)
    right = _value("right", 2)
    first = _value("first", 3)
    second = _value("second", 4)
    memory = IRMemoryObject(index=0, element_type=IRType.TRYTE, length=3, mutable=True)
    ssa_fn = SSAFunction(
        name="keeps_tryte_metadata",
        parameters=(SSAParameter(param),),
        values=(param, left, right, first, second),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=left, immediate=10),
                    SSAInstruction(IROpcode.CONST, result=right, immediate=20),
                    SSAInstruction(IROpcode.ADD, result=first, operands=(left, right)),
                    SSAInstruction(IROpcode.ADD, result=second, operands=(left, right)),
                    SSAInstruction(IROpcode.RETURN, operands=(second,)),
                ],
            ),
        ),
        memory_objects=(memory,),
        return_type=IRType.TRYTE,
    )

    optimized = run_ssa_cse(ssa_fn)

    assert optimized.name == ssa_fn.name
    assert optimized.parameters == ssa_fn.parameters
    assert optimized.memory_objects == ssa_fn.memory_objects
    assert optimized.return_type is IRType.TRYTE
