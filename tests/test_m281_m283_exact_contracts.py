import hashlib
from bootstrap.s3.canonical_ir_candidate import *
from bootstrap.s3.expression_lowering_candidate import *
from bootstrap.s3.call_aggregate_lowering_candidate import *
from bootstrap.s3.ir import IRType, IROpcode

def test_m281_exact_structure_and_sha256_distinguish_order():
    a=CanonicalIRProgram((CanonicalIRFunction(1,IRType.TRYTE,(IRType.TRYTE,), (CanonicalIRBlock(1,(CanonicalIRInstruction(IROpcode.CONST,0,(),1),)),)),))
    b=CanonicalIRProgram((CanonicalIRFunction(1,IRType.TRYTE,(IRType.TRYTE,), (CanonicalIRBlock(1,(CanonicalIRInstruction(IROpcode.CONST,0,(),2),)),)),))
    assert canonical_ir_exact_structure(a)!=canonical_ir_exact_structure(b)
    assert canonical_ir_exact_sha256(a)!=canonical_ir_exact_sha256(b)

def test_legacy_mod181_collision_is_not_structural_equivalence():
    a=CanonicalIRProgram((CanonicalIRFunction(1,IRType.TRYTE,(),(CanonicalIRBlock(1,(CanonicalIRInstruction(IROpcode.CONST,immediate=0),)),)),))
    b=CanonicalIRProgram((CanonicalIRFunction(182,IRType.TRYTE,(),(CanonicalIRBlock(1,(CanonicalIRInstruction(IROpcode.CONST,immediate=0),)),)),))
    assert canonical_ir_identity(a)==canonical_ir_identity(b)
    assert canonical_ir_exact_sha256(a)!=canonical_ir_exact_sha256(b)

def test_m282_exact_structural_differential_exposes_hashes():
    p=ExpressionProgram((ExpressionNode(M282_LITERAL,3),),0); e=run_expression_lowering_differential(p)
    assert e.match and e.reference_sha256==e.candidate_sha256

def test_m283_exact_call_plan_is_structural():
    v=CallLoweringInput(7,(IRType.TRYTE,),(1,),(IRType.TRYTE,)); e=run_call_lowering_differential(v)
    assert e.match and e.reference_sha256==e.candidate_sha256
