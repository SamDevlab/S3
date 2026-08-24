import pytest
from bootstrap.s3.m286_ownership_candidate import *

def test_positive_exact_s3_differential():
    for f in (mutable_local,shared_read,mutable_write):
        assert candidate_matches(f())
        assert digest(f())==candidate_digest(f())

def test_negative_diagnostics_are_deterministic():
    for f,code in ((invalid_shared_write,'SHARED_WRITE'),(moved_use,'USE_AFTER_MOVE')):
        with pytest.raises(M286Error) as e: validate(f())
        assert e.value.code==code

def test_reference_permissions_and_types_preserved():
    p=mutable_write(); assert p.places[0].type_id==1 and p.references[0].kind=='mutable'; assert candidate_structure(p)==structure(p)

def test_invalid_operation_and_conflict_fail_closed():
    with pytest.raises(M286Error) as e: validate(OwnershipProgram((Place(0,1,True),),(Reference(0,0,'shared'),),(M286Op('write_ref',reference_id=0),))); assert e.value.code=='SHARED_WRITE'
    bad=OwnershipProgram((Place(0,1,True),),(Reference(0,0,'mutable'),),(M286Op('borrow_mut',0),M286Op('borrow_mut',0)))
    with pytest.raises(M286Error): validate(bad)

def test_m285_composition_is_explicitly_accounted():
    from bootstrap.s3.m285_control_flow_candidate import if_fixture,candidate_matches_reference
    assert len(if_fixture().blocks)>1 and candidate_matches_reference(if_fixture())

def test_m284_real_linear_interop():
    from bootstrap.s3.m285_control_flow_candidate import m284_linear_interop
    assert m284_linear_interop().match
