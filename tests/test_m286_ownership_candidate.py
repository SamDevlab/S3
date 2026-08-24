import pytest
from bootstrap.s3.m286_ownership_candidate import *

def test_positive_exact_s3_differential():
    for f in (mutable_local,shared_read,mutable_write):
        assert candidate_diagnostic(f())==0
        assert candidate_matches(f())

def test_negative_diagnostics_are_deterministic():
    for f,code in ((invalid_shared_write,'SHARED_WRITE'),(moved_use,'USE_AFTER_MOVE')):
        with pytest.raises(M286Error) as e: validate(f())
        assert e.value.code==code

def test_negative_diagnostic_is_observed_from_s3():
    for f,code in ((invalid_shared_write,209),(moved_use,210)):
        assert candidate_diagnostic(f())==code

def test_reference_shape_rejects_invalid_kind_and_target():
    with pytest.raises(M286Error) as e: validate(OwnershipProgram((Place(0,1,True),),(Reference(0,0,'unknown'),),()))
    assert e.value.code=='INVALID_REFERENCE_KIND'
    with pytest.raises(M286Error) as e: validate(OwnershipProgram((Place(0,1,True),),(Reference(0,2,'shared'),),()))
    assert e.value.code=='INVALID_REFERENCE'

def test_ids_must_use_contiguous_canonical_slots():
    with pytest.raises(M286Error) as e: validate(OwnershipProgram((Place(1,1,True),),(),()))
    assert e.value.code=='NON_CANONICAL_ID_LAYOUT'

def test_initialization_and_move_rules():
    with pytest.raises(M286Error) as e: validate(OwnershipProgram((Place(0,1,True,False),),(),(M286Op('load_place',0),)))
    assert e.value.code=='READ_UNINITIALIZED'
    with pytest.raises(M286Error) as e: validate(OwnershipProgram((Place(0,1,True),),(),(M286Op('move_value',0),M286Op('move_value',0))))
    assert e.value.code=='DOUBLE_MOVE'

def test_selfhost_candidate_guard_and_no_constant_echo():
    import bootstrap.s3.m286_ownership_candidate as candidate
    source=candidate._CANDIDATE_SOURCE
    assert 'ownership_validate' in source and 'ownership_lane' in source and 'while' in source
    assert 'fn lane_' not in candidate._candidate_source(mutable_local(), 0)

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
