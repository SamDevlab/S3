import hashlib
import pytest
from bootstrap.s3.quantum.ir import *
from bootstrap.s3.quantum.providers import QIR_BASE_PROFILE
from bootstrap.s3.quantum.ir import bell_fixture, ghz_fixture

def test_bell_and_ghz_are_deterministic():
    assert bell_fixture().canonical_bytes()==bell_fixture().canonical_bytes()
    assert bell_fixture().digest()==hashlib.sha256(bell_fixture().canonical_bytes()).hexdigest()
    assert ghz_fixture().digest()==ghz_fixture().digest()

def test_openqasm_exact_and_deterministic():
    qasm=emit_openqasm3(bell_fixture())
    assert qasm == 'OPENQASM 3.1;\ninclude "stdgates.inc";\nqubit[2] q;\nbit[2] c;\nh q[0];\ncx q[0], q[1];\nc[0] = measure q[0];\nc[1] = measure q[1];\n'
    assert qasm.count('measure') == 2

def test_ghz_exact_and_no_duplicate_measurements():
    qasm=emit_openqasm3(ghz_fixture())
    assert qasm == 'OPENQASM 3.1;\ninclude "stdgates.inc";\nqubit[3] q;\nbit[3] c;\nh q[0];\ncx q[0], q[1];\ncx q[1], q[2];\nc[0] = measure q[0];\nc[1] = measure q[1];\nc[2] = measure q[2];\n'
    assert qasm.count('measure') == 3

def test_validation_fail_closed():
    ir=S3QuantumIR(QuantumProgram(1,(QuantumInstruction('reset',(0,)),)))
    with pytest.raises(QuantumDiagnostic) as e: validate_capabilities(ir,QuantumTarget('tiny',frozenset({'h'}),1))
    assert e.value.code is DiagnosticCode.UNSUPPORTED_CAPABILITY

def test_bounds_arity_and_unknown():
    with pytest.raises(QuantumDiagnostic): QuantumProgram(1,(QuantumInstruction('cx',(0,1)),))
    with pytest.raises(QuantumDiagnostic): QuantumInstruction('wat',(0,))

def test_measurement_contracts_and_parameters():
    with pytest.raises(QuantumDiagnostic): QuantumInstruction('measure',(0,))
    with pytest.raises(QuantumDiagnostic): QuantumProgram(1,(QuantumInstruction('measure',(0,),classical_targets=(0,)),QuantumInstruction('measure',(0,),classical_targets=(0,))))
    with pytest.raises(QuantumDiagnostic): QuantumProgram(1,(QuantumInstruction('measure',(0,),classical_targets=(2,)),),2)
    for value in (float('nan'),float('inf'),float('-inf')):
        with pytest.raises(QuantumDiagnostic): QuantumInstruction('rx',(0,),(value,))

def test_alias_barrier_and_profile_contract():
    assert S3QuantumIR(QuantumProgram(2,(QuantumInstruction('cnot',(0,1)),))).canonical_bytes() == S3QuantumIR(QuantumProgram(2,(QuantumInstruction('cx',(0,1)),))).canonical_bytes()
    with pytest.raises(QuantumDiagnostic): QuantumInstruction('barrier',(0,))
    assert QIR_BASE_PROFILE == 'base_profile'

def test_parametric_rotation():
    assert 'rx(1.5) q[0];' in emit_openqasm3(S3QuantumIR(QuantumProgram(1,(QuantumInstruction('rx',(0,),(1.5,)),))))
