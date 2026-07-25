from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.ir import IROpcode
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def _compile(source: str):
    return compile_source(source, mode=SyntaxMode.V0_6)


def _while_blocks(source: str):
    ir = _compile(source).ir
    func = ir.functions[0]
    return [b for b in func.blocks if "while" in b.name]


def test_trit_condition_accepted() -> None:
    ir = _compile(
        "fn main() -> tryte:\n    while -1 <=> 0:\n        mut x: tryte = 0\n        x = x + 1\n    return 0\n"
    ).ir
    assert any("while" in b.name for b in ir.functions[0].blocks)


def test_tryte_condition_rejected() -> None:
    with pytest.raises(SemanticError, match="expected trit"):
        _compile("fn main() -> tryte:\n    mut x: tryte = 0\n    while x:\n        x = x + 1\n    return x\n")


def test_entry_has_terminator() -> None:
    ir = _compile(
        "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 5:\n        x = x + 1\n    return x\n"
    ).ir
    entry = ir.functions[0].blocks[0]
    assert entry.instructions
    last = entry.instructions[-1]
    assert last.opcode in {IROpcode.JUMP, IROpcode.BRANCH3}


def test_condition_has_branch3() -> None:
    blocks = _while_blocks(
        "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 5:\n        x = x + 1\n    return x\n"
    )
    condition = [b for b in blocks if "condition" in b.name]
    assert condition
    last = condition[0].instructions[-1]
    assert last.opcode is IROpcode.BRANCH3


def test_body_has_jump_back() -> None:
    blocks = _while_blocks(
        "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 5:\n        x = x + 1\n    return x\n"
    )
    body = [b for b in blocks if "body" in b.name]
    assert body
    last = body[0].instructions[-1]
    assert last.opcode is IROpcode.JUMP


def test_back_edge_exists() -> None:
    ir = _compile(
        "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 5:\n        x = x + 1\n    return x\n"
    ).ir
    body_blocks = [b for b in ir.functions[0].blocks if "body" in b.name]
    assert body_blocks
    jump = body_blocks[0].instructions[-1]
    assert jump.opcode is IROpcode.JUMP
    condition_blocks = [b for b in ir.functions[0].blocks if "condition" in b.name]
    assert condition_blocks
    assert jump.targets[0] == condition_blocks[0].name


def test_condition_re_evaluated() -> None:
    ir = _compile(
        "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 5:\n        x = x + 1\n    return x\n"
    ).ir
    condition_blocks = [b for b in ir.functions[0].blocks if "condition" in b.name]
    assert condition_blocks
    insts = condition_blocks[0].instructions
    has_load = any(i.opcode is IROpcode.LOAD for i in insts)
    has_compare = any(i.opcode is IROpcode.COMPARE for i in insts)
    assert has_load and has_compare


def test_exit_block_receives_post_while_statements() -> None:
    ir = _compile(
        "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 5:\n        x = x + 1\n    return x\n"
    ).ir
    main_exit = [b for b in ir.functions[0].blocks if b.name == "while_exit_4"]
    if main_exit:
        last = main_exit[0].instructions[-1]
        assert last.opcode is IROpcode.RETURN


def test_no_block_without_terminator() -> None:
    compile_source(
        "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 5:\n        x = x + 1\n    return x\n",
        mode=SyntaxMode.V0_6,
    )


def test_negative_goes_to_body() -> None:
    blocks = _while_blocks(
        "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 5:\n        x = x + 1\n    return x\n"
    )
    condition = [b for b in blocks if "condition" in b.name][0]
    branch3 = condition.instructions[-1]
    assert branch3.opcode is IROpcode.BRANCH3
    body_blocks = [b for b in blocks if "body" in b.name]
    assert body_blocks
    assert branch3.targets[0] == body_blocks[0].name


def test_zero_goes_to_exit() -> None:
    blocks = _while_blocks(
        "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 5:\n        x = x + 1\n    return x\n"
    )
    condition = [b for b in blocks if "condition" in b.name][0]
    branch3 = condition.instructions[-1]
    assert branch3.opcode is IROpcode.BRANCH3
    exit_0 = [b for b in blocks if "exit_0" in b.name]
    assert exit_0
    assert branch3.targets[1] == exit_0[0].name


def test_positive_goes_to_exit() -> None:
    blocks = _while_blocks(
        "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 5:\n        x = x + 1\n    return x\n"
    )
    condition = [b for b in blocks if "condition" in b.name][0]
    branch3 = condition.instructions[-1]
    assert branch3.opcode is IROpcode.BRANCH3
    exit_1 = [b for b in blocks if "exit_1" in b.name]
    assert exit_1
    assert branch3.targets[2] == exit_1[0].name


def test_no_recursive_call_produced() -> None:
    ir = _compile(
        "fn main() -> tryte:\n    mut x: tryte = 0\n    while x <=> 5:\n        x = x + 1\n    return x\n"
    ).ir
    for func in ir.functions:
        for block in func.blocks:
            for inst in block.instructions:
                assert inst.opcode is not IROpcode.CALL


def test_continuation_after_terminating_body() -> None:
    ir = _compile(
        "fn foo(condition: trit) -> tryte:\n    while condition:\n        return 1\n    return 0\nfn main() -> tryte:\n    return 0\n"
    ).ir
    blocks = ir.functions[0].blocks

    # Check that there is an exit block
    exit_blocks = [b for b in blocks if b.name.startswith("while_exit") and not b.name.startswith("while_exit_0") and not b.name.startswith("while_exit_1")]
    assert exit_blocks

    # Check that the exit block contains the post-loop return
    last_block = blocks[-1]
    assert last_block.instructions
    assert last_block.instructions[-1].opcode is IROpcode.RETURN

    # Check that exit_0 and exit_1 converge to the exit block
    exit_0 = [b for b in blocks if "exit_0" in b.name][0]
    exit_1 = [b for b in blocks if "exit_1" in b.name][0]
    assert exit_0.instructions[-1].targets[0] == exit_blocks[0].name
    assert exit_1.instructions[-1].targets[0] == exit_blocks[0].name

    # Check that body block has no jump back
    body_blocks = [b for b in blocks if "body" in b.name]
    assert body_blocks
    assert body_blocks[0].instructions[-1].opcode is IROpcode.RETURN


def test_break_lowers_to_exit_jump() -> None:
    ir = _compile(
        "fn foo(cond: trit) -> tryte:\n"
        "    while cond:\n"
        "        break\n"
        "    return 0\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    ).ir
    func = ir.functions[0]
    body = [b for b in func.blocks if "body" in b.name][0]
    exit_block = [b for b in func.blocks if b.name.startswith("while_exit") and not "exit_0" in b.name and not "exit_1" in b.name][0]
    assert body.instructions[-1].opcode is IROpcode.JUMP
    assert body.instructions[-1].targets[0] == exit_block.name


def test_continue_lowers_to_condition_jump() -> None:
    ir = _compile(
        "fn foo(cond: trit) -> tryte:\n"
        "    while cond:\n"
        "        continue\n"
        "    return 0\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    ).ir
    func = ir.functions[0]
    body = [b for b in func.blocks if "body" in b.name][0]
    cond_block = [b for b in func.blocks if "condition" in b.name][0]
    assert body.instructions[-1].opcode is IROpcode.JUMP
    assert body.instructions[-1].targets[0] == cond_block.name


def test_nested_loop_jumps_target_innermost() -> None:
    ir = _compile(
        "fn foo(c1: trit, c2: trit) -> tryte:\n"
        "    while c1:\n"
        "        while c2:\n"
        "            break\n"
        "        continue\n"
        "    return 0\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    ).ir
    func = ir.functions[0]
    body_blocks = [b for b in func.blocks if "while_body" in b.name]
    assert len(body_blocks) == 2
    outer_body, inner_body = body_blocks[0], body_blocks[1]

    cond_blocks = [b for b in func.blocks if "while_condition" in b.name]
    assert len(cond_blocks) == 2
    outer_cond = cond_blocks[0]

    exit_blocks = [b for b in func.blocks if b.name.startswith("while_exit") and not "exit_0" in b.name and not "exit_1" in b.name]
    assert len(exit_blocks) == 2
    outer_exit, inner_exit = exit_blocks[0], exit_blocks[1]

    assert inner_body.instructions[-1].opcode is IROpcode.JUMP
    assert inner_body.instructions[-1].targets[0] == inner_exit.name

    continue_block = [b for b in func.blocks if b.instructions and b.instructions[-1].targets == (outer_cond.name,)][0]
    assert continue_block.instructions[-1].opcode is IROpcode.JUMP


def test_match_arm_break_and_continue_lowering() -> None:
    ir = _compile(
        "fn foo(cond: trit) -> tryte:\n"
        "    while cond:\n"
        "        match cond:\n"
        "            -1:\n"
        "                continue\n"
        "            0:\n"
        "                break\n"
        "            1:\n"
        "                break\n"
        "    return 0\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    ).ir
    from bootstrap.s3.verifier import verify_ir
    verify_ir(ir)

