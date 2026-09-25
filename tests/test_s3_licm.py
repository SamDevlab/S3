from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from bootstrap.s3.ir import IROpcode, IRMemoryObject, IRType
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.ssa import SSABlock, SSAFunction, SSAInstruction, SSABuilder, SSAValue
from bootstrap.s3.ssa_opt import run_ssa_licm


def _value(name: str, original_register: int, block: str = "entry") -> SSAValue:
    return SSAValue(
        name,
        original_register=original_register,
        type=IRType.TRYTE,
        def_block=block,
    )


def _ambiguous_preheader_fixture() -> SSAFunction:
    cond = _value("cond", 0)
    invariant = _value("invariant", 1, "header")
    direct = _value("direct", 2, "direct")
    return SSAFunction(
        name="main",
        parameters=(),
        values=(cond, invariant, direct),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=cond, immediate=-1),
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(cond,),
                        targets=("left", "right", "direct"),
                    ),
                ],
            ),
            SSABlock("left", instructions=[SSAInstruction(IROpcode.JUMP, targets=("header",))]),
            SSABlock("right", instructions=[SSAInstruction(IROpcode.JUMP, targets=("header",))]),
            SSABlock(
                "direct",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=direct, immediate=7),
                    SSAInstruction(IROpcode.RETURN, operands=(direct,)),
                ],
            ),
            SSABlock(
                "header",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=invariant, immediate=10),
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(cond,),
                        targets=("body", "exit0", "exit1"),
                    ),
                ],
            ),
            SSABlock("body", instructions=[SSAInstruction(IROpcode.JUMP, targets=("header",))]),
            SSABlock("exit0", instructions=[SSAInstruction(IROpcode.RETURN, operands=(invariant,))]),
            SSABlock("exit1", instructions=[SSAInstruction(IROpcode.RETURN, operands=(invariant,))]),
        ),
        return_type=IRType.TRYTE,
    )


def _shape(ssa_fn: SSAFunction) -> list[tuple[str, list[tuple[str, str | None, tuple[str, ...]]]]]:
    return [
        (
            block.name,
            [
                (
                    instruction.opcode.value,
                    None if instruction.result is None else instruction.result.name,
                    tuple(operand.name for operand in instruction.operands),
                )
                for instruction in block.instructions
            ],
        )
        for block in ssa_fn.blocks
    ]


def test_licm_keeps_invariant_when_header_has_ambiguous_preheaders() -> None:
    optimized, hoisted = run_ssa_licm(_ambiguous_preheader_fixture())

    assert hoisted == 0
    locations = {
        instruction.result.name: block.name
        for block in optimized.blocks
        for instruction in block.instructions
        if instruction.result is not None
    }
    assert locations["invariant"] == "header"


def test_licm_moves_invariant_and_keeps_variant_in_loop() -> None:
    index = _value("index", 0)
    left = _value("left", 1)
    right = _value("right", 2)
    invariant = _value("invariant", 3, "header")
    variant = _value("variant", 4, "body")
    fixture = SSAFunction(
        name="main",
        parameters=(),
        values=(index, left, right, invariant, variant),
        memory_objects=(IRMemoryObject(0, IRType.TRYTE, 1, True),),
        blocks=(
            SSABlock(
                "entry",
                instructions=[
                    SSAInstruction(IROpcode.CONST, result=index, immediate=0),
                    SSAInstruction(IROpcode.CONST, result=left, immediate=2),
                    SSAInstruction(IROpcode.CONST, result=right, immediate=3),
                    SSAInstruction(IROpcode.JUMP, targets=("header",)),
                ],
            ),
            SSABlock(
                "header",
                instructions=[
                    SSAInstruction(IROpcode.ADD, result=invariant, operands=(left, right)),
                    SSAInstruction(
                        IROpcode.BRANCH3,
                        operands=(index,),
                        targets=("body", "exit0", "exit1"),
                    ),
                ],
            ),
            SSABlock(
                "body",
                instructions=[
                    SSAInstruction(IROpcode.LOAD, result=variant, operands=(index,), memory=0),
                    SSAInstruction(IROpcode.JUMP, targets=("header",)),
                ],
            ),
            SSABlock("exit0", instructions=[SSAInstruction(IROpcode.RETURN, operands=(invariant,))]),
            SSABlock("exit1", instructions=[SSAInstruction(IROpcode.RETURN, operands=(invariant,))]),
        ),
        return_type=IRType.TRYTE,
    )

    optimized, hoisted = run_ssa_licm(fixture)
    locations = {
        instruction.result.name: block.name
        for block in optimized.blocks
        for instruction in block.instructions
        if instruction.result is not None
    }

    assert hoisted == 1
    assert locations["invariant"] == "entry"
    assert locations["variant"] == "body"


def test_licm_shape_is_identical_across_hash_seeds() -> None:
    script = (
        "from tests.test_s3_licm import _ambiguous_preheader_fixture, _shape\n"
        "from bootstrap.s3.ssa_opt import run_ssa_licm\n"
        "optimized, hoisted = run_ssa_licm(_ambiguous_preheader_fixture())\n"
        "print(json.dumps({'hoisted': hoisted, 'shape': _shape(optimized)}, sort_keys=True))\n"
    )
    root = Path(__file__).resolve().parents[1]
    outputs = []
    for seed in ("0", "1", "42"):
        environment = os.environ.copy()
        environment["PYTHONHASHSEED"] = seed
        environment["PYTHONPATH"] = str(root)
        completed = subprocess.run(
            [sys.executable, "-c", "import json\n" + script],
            cwd=root,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(json.loads(completed.stdout))

    assert outputs[0] == outputs[1] == outputs[2]


def test_licm_hoists_invariant_computation() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut i: tryte = 0\n"
        "    mut sum: tryte = 0\n"
        "    c1: tryte = 10\n"
        "    c2: tryte = 20\n"
        "    while i < 3:\n"
        "        inv: tryte = c1 + c2\n"
        "        sum = sum + inv\n"
        "        i = i + 1\n"
        "    return sum\n"
    )
    compilation = compile_source(source, mode=SyntaxMode.V0_6)
    fn = compilation.ir.functions[0]
    ssa_fn = SSABuilder.build_function(fn)
    opt_ssa, hoisted = run_ssa_licm(ssa_fn)

    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 90


def test_licm_preserves_side_effects_in_loop() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut i: tryte = 0\n"
        "    mut total: tryte = 0\n"
        "    while i < 2:\n"
        "        total = total + 5\n"
        "        i = i + 1\n"
        "    return total\n"
    )
    res = run_source(source, optimization="O1", mode=SyntaxMode.V0_6)
    assert res == 10
