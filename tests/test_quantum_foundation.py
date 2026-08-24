import hashlib
import pytest
from bootstrap.s3.quantum.ir import *
from bootstrap.s3.quantum.ir import bell_fixture, ghz_fixture

def test_bell_and_ghz_are_deterministic():
    assert bell_fixture().canonical_bytes()==bell_fixture().canonical_bytes()
    assert bell_fixture().digest()==hashlib.sha256(bell_fixture().canonical_bytes()).hexdigest()
    assert ghz_fixture().digest()==ghz_fixture().digest()

def test_openqasm_exact_and_deterministic():
    qasm=emit_openqasm3(bell_fixture())
    assert qasm.startswith('OPENQASM 3.1;\ninclude "stdgates.inc";\nqubit[2] q;')
    assert qasm==emit_openqasm3(bell_fixture())

def test_validation_fail_closed():
    ir=S3QuantumIR(QuantumProgram(1,(QuantumInstruction('reset',(0,)),)))
    with pytest.raises(QuantumDiagnostic) as e: validate_capabilities(ir,QuantumTarget('tiny',frozenset({'h'}),1))
    assert e.value.code is DiagnosticCode.UNSUPPORTED_CAPABILITY

def test_bounds_arity_and_unknown():
    with pytest.raises(QuantumDiagnostic): QuantumProgram(1,(QuantumInstruction('cx',(0,1)),))
    with pytest.raises(QuantumDiagnostic): QuantumInstruction('wat',(0,))

def test_parametric_rotation():
    assert 'rx(1.5) q[0];' in emit_openqasm3(S3QuantumIR(QuantumProgram(1,(QuantumInstruction('rx',(0,),(1.5,)),))))
