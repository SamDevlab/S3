"""Small deterministic S3 Quantum IR reference implementation (experimental)."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
import hashlib, json, math

class DiagnosticCode(str, Enum):
    INVALID_QUBIT_INDEX="INVALID_QUBIT_INDEX"; DUPLICATE_QUBIT_USE="DUPLICATE_QUBIT_USE"
    INVALID_GATE_ARITY="INVALID_GATE_ARITY"; INVALID_PARAMETER="INVALID_PARAMETER"
    UNKNOWN_GATE="UNKNOWN_GATE"; UNSUPPORTED_INSTRUCTION="UNSUPPORTED_INSTRUCTION"
    UNSUPPORTED_CAPABILITY="UNSUPPORTED_CAPABILITY"; INVALID_MEASUREMENT_TARGET="INVALID_MEASUREMENT_TARGET"
    TARGET_NOT_AVAILABLE="TARGET_NOT_AVAILABLE"

class QuantumDiagnostic(ValueError):
    def __init__(self, code: DiagnosticCode, message: str):
        self.code, self.message = code, message; super().__init__(f"{code}: {message}")

_ARITY = {"x":1,"y":1,"z":1,"h":1,"s":1,"t":1,"rx":1,"ry":1,"rz":1,
          "cx":2,"cnot":2,"cz":2,"swap":2,"measure":1,"reset":1,"barrier":0}
_PARAM = {"rx","ry","rz"}

@dataclass(frozen=True)
class QuantumInstruction:
    name: str; operands: tuple[int,...] = (); parameters: tuple[float,...] = ()
    def __post_init__(self):
        n=self.name.lower()
        if n not in _ARITY: raise QuantumDiagnostic(DiagnosticCode.UNKNOWN_GATE, self.name)
        if _ARITY[n] and len(self.operands)!=_ARITY[n]: raise QuantumDiagnostic(DiagnosticCode.INVALID_GATE_ARITY,n)
        if not _ARITY[n] and n != "barrier" and self.operands: raise QuantumDiagnostic(DiagnosticCode.INVALID_GATE_ARITY,n)
        if n in _PARAM and len(self.parameters)!=1: raise QuantumDiagnostic(DiagnosticCode.INVALID_PARAMETER,n)
        if n not in _PARAM and self.parameters: raise QuantumDiagnostic(DiagnosticCode.INVALID_PARAMETER,n)
        if any(not isinstance(q,int) or q < 0 for q in self.operands): raise QuantumDiagnostic(DiagnosticCode.INVALID_QUBIT_INDEX,n)
    @property
    def normalized_name(self): return self.name.lower()

@dataclass(frozen=True)
class QuantumProgram:
    qubits: int
    instructions: tuple[QuantumInstruction,...]
    measurements: tuple[tuple[int,int],...] = ()
    def __post_init__(self):
        if self.qubits < 1: raise QuantumDiagnostic(DiagnosticCode.INVALID_QUBIT_INDEX,"qubit count")
        for i in self.instructions:
            if any(q>=self.qubits for q in i.operands): raise QuantumDiagnostic(DiagnosticCode.INVALID_QUBIT_INDEX,str(i.operands))
        seen=set()
        for q,b in self.measurements:
            if q<0 or q>=self.qubits or b<0: raise QuantumDiagnostic(DiagnosticCode.INVALID_MEASUREMENT_TARGET,str((q,b)))
            if q in seen: raise QuantumDiagnostic(DiagnosticCode.INVALID_MEASUREMENT_TARGET,str(q))
            seen.add(q)

@dataclass(frozen=True)
class QuantumTarget:
    name: str; capabilities: frozenset[str]; max_qubits: int|None=None; openqasm_version: str="3.1"

@dataclass(frozen=True)
class S3QuantumIR:
    program: QuantumProgram
    schema: str = "s3.quantum.ir.v1"
    def canonical_bytes(self) -> bytes:
        p=self.program
        data={"schema":self.schema,"qubits":p.qubits,"instructions":[{"name":i.normalized_name,"operands":list(i.operands),"parameters":[format(x,'.17g') for x in i.parameters]} for i in p.instructions],"measurements":[list(x) for x in p.measurements]}
        return (json.dumps(data,sort_keys=True,separators=(",",":"),ensure_ascii=True)+"\n").encode()
    def digest(self): return hashlib.sha256(self.canonical_bytes()).hexdigest()

def validate_capabilities(ir:S3QuantumIR, target:QuantumTarget):
    if target.max_qubits is not None and ir.program.qubits>target.max_qubits: raise QuantumDiagnostic(DiagnosticCode.UNSUPPORTED_CAPABILITY,"max_qubits")
    for i in ir.program.instructions:
        if i.normalized_name not in target.capabilities: raise QuantumDiagnostic(DiagnosticCode.UNSUPPORTED_CAPABILITY,i.normalized_name)

def emit_openqasm3(ir:S3QuantumIR, target:QuantumTarget|None=None)->str:
    if target: validate_capabilities(ir,target)
    p=ir.program; lines=["OPENQASM 3.1;","include \"stdgates.inc\";",f"qubit[{p.qubits}] q;"]
    if p.measurements: lines.append(f"bit[{max(b for _,b in p.measurements)+1}] c;")
    for i in p.instructions:
        n=i.normalized_name; args=", ".join(f"q[{q}]" for q in i.operands)
        if n=="cnot": n="cx"
        if n in _PARAM: lines.append(f"{n}({format(i.parameters[0],'.17g')}) {args};")
        elif n=="measure": lines.append(f"c[0] = measure {args};")
        elif n=="barrier": lines.append("barrier q;")
        else: lines.append(f"{n} {args};")
    for q,b in p.measurements: lines.append(f"c[{b}] = measure q[{q}];")
    return "\n".join(lines)+"\n"

def bell_fixture(): return S3QuantumIR(QuantumProgram(2,(QuantumInstruction("h",(0,)),QuantumInstruction("cx",(0,1)),QuantumInstruction("measure",(0,)),QuantumInstruction("measure",(1,)),),((0,0),(1,1))))
def ghz_fixture(): return S3QuantumIR(QuantumProgram(3,(QuantumInstruction("h",(0,)),QuantumInstruction("cx",(0,1)),QuantumInstruction("cx",(1,2)),),((0,0),(1,1),(2,2))))
