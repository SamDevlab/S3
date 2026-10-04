import hashlib, pytest
from bootstrap.s3.accelerator.ir import *

def test_fixtures_are_deterministic_and_distinct():
    v,s=vector_add_fixture(),saxpy_fixture(); assert v.canonical_bytes()==vector_add_fixture().canonical_bytes(); assert v.digest()==hashlib.sha256(v.canonical_bytes()).hexdigest(); assert v.digest()!=s.digest()

def test_dimensions_and_workgroup_fail_closed():
    with pytest.raises(AcceleratorDiagnostic): WorkDimensions((1,2,3,4),(1,1,1,1))
    with pytest.raises(AcceleratorDiagnostic): WorkDimensions((1024,),(0,))
    with pytest.raises(AcceleratorDiagnostic): WorkDimensions((10,),(3,))

def test_memory_access_and_duplicate_kernel_contracts():
    assert vector_add_fixture().program.kernels[0].buffers[0].memory_space is MemorySpace.GLOBAL
    k=vector_add_fixture().program.kernels[0]
    with pytest.raises(AcceleratorDiagnostic): AcceleratorProgram((k,k))
    with pytest.raises(AcceleratorDiagnostic): AcceleratorBuffer("",ValueType.F32,1)

def test_barrier_and_capability_validation():
    with pytest.raises(AcceleratorDiagnostic): AcceleratorInstruction(Operation.BARRIER,attributes=(("scope","global"),))
    p=vector_add_fixture().program; target=AcceleratorTarget("minimal",AcceleratorCapabilities(max_workgroup_size=32))
    with pytest.raises(AcceleratorDiagnostic): validate_capabilities(p,target)

def test_f64_rejected_without_capability_and_operations_fail_closed():
    k=AcceleratorKernel("f64",(ValueType.F64,),(),(AcceleratorInstruction(Operation.RETURN),),WorkDimensions((1,),(1,)))
    with pytest.raises(AcceleratorDiagnostic): validate_capabilities(AcceleratorProgram((k,)),AcceleratorTarget("no-f64",AcceleratorCapabilities()))
