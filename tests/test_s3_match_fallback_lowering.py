"""Lowering tests for match statement and match expression fallback in S3 0.52."""

from bootstrap.s3.ir import IROpcode
from bootstrap.s3.lowering import lower
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze
from bootstrap.s3.verifier import verify_ir


def test_lowering_match_statement_fallback():
    program = parse("""
fn main() -> tryte:
    match 0:
        1:
            return 10
        else:
            return 20
""")
    semantic_model = analyze(program)
    ir_module = lower(program, semantic_model)
    verify_ir(ir_module)

    fn = ir_module.functions[0]
    branch3_insts = [i for b in fn.blocks for i in b.instructions if i.opcode == IROpcode.BRANCH3]
    assert len(branch3_insts) == 1
    b3 = branch3_insts[0]
    blocks_dict = {b.name: b for b in fn.blocks}
    neg_block = blocks_dict[b3.targets[0]]
    neut_block = blocks_dict[b3.targets[1]]
    pos_block = blocks_dict[b3.targets[2]]

    # -1 (neg) was first encounter of fallback, lowered block content
    # 0 (neut) was second encounter of fallback, jumps to neg_block
    assert neut_block.instructions[0].opcode == IROpcode.JUMP
    assert neut_block.instructions[0].targets[0] == neg_block.name


def test_lowering_match_expression_fallback():
    program = parse("""
fn main() -> tryte:
    x: tryte = match 0:
        0: 100
        else: 200
    return x
""")
    semantic_model = analyze(program)
    ir_module = lower(program, semantic_model)
    verify_ir(ir_module)

    fn = ir_module.functions[0]
    branch3_insts = [i for b in fn.blocks for i in b.instructions if i.opcode == IROpcode.BRANCH3]
    assert len(branch3_insts) == 1
    b3 = branch3_insts[0]
    blocks_dict = {b.name: b for b in fn.blocks}
    neg_block = blocks_dict[b3.targets[0]]
    pos_block = blocks_dict[b3.targets[2]]

    # -1 (neg) was first encounter of fallback, lowered block content
    # 1 (pos) was second encounter of fallback, jumps to neg_block
    assert pos_block.instructions[0].opcode == IROpcode.JUMP
    assert pos_block.instructions[0].targets[0] == neg_block.name
