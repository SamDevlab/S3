from bootstrap.s3.m285_control_flow_candidate import *

def test_exact_deterministic_fixtures():
    for f in (if_fixture,nested_branch_fixture,bounded_loop_fixture):
        assert exact_structure(f())==exact_structure(f()); assert canonical_sha256(f())==canonical_sha256(f())

def test_branch_targets_and_return_are_exact():
    p=if_fixture(); assert [b.id for b in p.blocks]==[0,1,2,3]; assert p.blocks[0].instructions[1].targets==(1,2); assert p.blocks[-1].instructions[-1].opcode=='return'

def test_verifier_interop_and_fail_closed():
    assert all(verifier_interop(f()) for f in (if_fixture,nested_branch_fixture,bounded_loop_fixture))
    bad=M285Program((M285Block(0,(M285Instruction('branch',targets=(9,)),)),),0)
    try: verifier_interop(bad); assert False
    except M285Error: pass

def test_semantic_change_changes_sha256():
    a=if_fixture(); b=M285Program(a.blocks[:-1]+(M285Block(3,(M285Instruction('return',operands=(0,)),)),),a.register_count)
    assert canonical_sha256(a)!=canonical_sha256(b)
