"""Deterministic hardware-agnostic accelerator IR reference model."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import hashlib, json

class AcceleratorDiagnostic(ValueError):
    def __init__(self, code, message): self.code=code; self.message=message; super().__init__(f"{code}: {message}")
class DiagnosticCode(str,Enum):
    INVALID_WORK_DIMENSION="INVALID_WORK_DIMENSION"; INVALID_WORKGROUP_SIZE="INVALID_WORKGROUP_SIZE"; INVALID_BUFFER_INDEX="INVALID_BUFFER_INDEX"; INVALID_MEMORY_SPACE="INVALID_MEMORY_SPACE"; INVALID_KERNEL_PARAMETER="INVALID_KERNEL_PARAMETER"; INVALID_OPERATION="INVALID_OPERATION"; TYPE_MISMATCH="TYPE_MISMATCH"; UNSUPPORTED_OPERATION="UNSUPPORTED_OPERATION"; UNSUPPORTED_CAPABILITY="UNSUPPORTED_CAPABILITY"; INVALID_BARRIER_SCOPE="INVALID_BARRIER_SCOPE"; TARGET_NOT_AVAILABLE="TARGET_NOT_AVAILABLE"; DEVICE_NOT_AVAILABLE="DEVICE_NOT_AVAILABLE"; BACKEND_NOT_AVAILABLE="BACKEND_NOT_AVAILABLE"
class MemorySpace(str,Enum): PRIVATE="private"; WORKGROUP="workgroup"; GLOBAL="global"; CONSTANT="constant"
class AccessMode(str,Enum): READ_ONLY="read_only"; WRITE_ONLY="write_only"; READ_WRITE="read_write"
class ValueType(str,Enum): I32="i32"; I64="i64"; U32="u32"; U64="u64"; F32="f32"; F64="f64"
class Operation(str,Enum): CONSTANT="constant"; LOAD="load"; STORE="store"; ADD="add"; SUB="sub"; MUL="mul"; DIV="div"; COMPARE="compare"; SELECT="select"; GLOBAL_ID="global_id"; LOCAL_ID="local_id"; GROUP_ID="group_id"; BARRIER="barrier"; RETURN="return"

def _positive_dims(values, code):
    if not 1<=len(values)<=3 or any(not isinstance(x,int) or x<=0 for x in values): raise AcceleratorDiagnostic(code,str(values))
    return tuple(values)

@dataclass(frozen=True)
class WorkDimensions:
    global_size: tuple[int,...]; workgroup_size: tuple[int,...]
    def __post_init__(self):
        _positive_dims(self.global_size,DiagnosticCode.INVALID_WORK_DIMENSION); _positive_dims(self.workgroup_size,DiagnosticCode.INVALID_WORKGROUP_SIZE)
        if len(self.global_size)!=len(self.workgroup_size): raise AcceleratorDiagnostic(DiagnosticCode.INVALID_WORK_DIMENSION,"rank mismatch")
        if any(g%w for g,w in zip(self.global_size,self.workgroup_size)): raise AcceleratorDiagnostic(DiagnosticCode.INVALID_WORKGROUP_SIZE,"global size not divisible")

@dataclass(frozen=True)
class AcceleratorBuffer:
    name:str; element_type:ValueType; length:int; memory_space:MemorySpace=MemorySpace.GLOBAL; access:AccessMode=AccessMode.READ_WRITE
    def __post_init__(self):
        if not self.name or self.length<=0: raise AcceleratorDiagnostic(DiagnosticCode.INVALID_BUFFER_INDEX,"buffer bounds")

@dataclass(frozen=True)
class AcceleratorInstruction:
    operation:Operation; operands:tuple[object,...]=(); result_type:ValueType|None=None; attributes:tuple[tuple[str,str],...]=()
    def __post_init__(self):
        if self.operation==Operation.BARRIER and dict(self.attributes).get("scope")!="workgroup": raise AcceleratorDiagnostic(DiagnosticCode.INVALID_BARRIER_SCOPE,"only workgroup barrier is valid")

@dataclass(frozen=True)
class AcceleratorKernel:
    name:str; parameters:tuple[ValueType,...]; buffers:tuple[AcceleratorBuffer,...]; instructions:tuple[AcceleratorInstruction,...]; launch:WorkDimensions; required_capabilities:frozenset[str]=frozenset()
    def __post_init__(self):
        if not self.name: raise AcceleratorDiagnostic(DiagnosticCode.INVALID_KERNEL_PARAMETER,"missing kernel entry")
        if len({b.name for b in self.buffers})!=len(self.buffers): raise AcceleratorDiagnostic(DiagnosticCode.INVALID_BUFFER_INDEX,"duplicate buffer")

@dataclass(frozen=True)
class AcceleratorProgram:
    kernels:tuple[AcceleratorKernel,...]
    def __post_init__(self):
        if len({k.name for k in self.kernels})!=len(self.kernels): raise AcceleratorDiagnostic(DiagnosticCode.INVALID_KERNEL_PARAMETER,"duplicate kernel name")

@dataclass(frozen=True)
class AcceleratorTarget:
    name:str; capabilities:"AcceleratorCapabilities"

@dataclass(frozen=True)
class AcceleratorCapabilities:
    max_workgroup_size:int=1024; max_workgroup_dimensions:tuple[int,...]=(1024,1024,64); max_grid_dimensions:tuple[int,...]=(2**31-1,2**31-1,2**31-1); supported_types:frozenset[ValueType]=frozenset(ValueType); supported_operations:frozenset[Operation]=frozenset(Operation); memory_spaces:frozenset[MemorySpace]=frozenset(MemorySpace); float64:bool=False; atomics:bool=False; subgroups:bool=False; qir_profiles:frozenset[str]=frozenset()

def validate_capabilities(program:AcceleratorProgram,target:AcceleratorTarget):
    c=target.capabilities
    for k in program.kernels:
        if any(d>m for d,m in zip(k.launch.workgroup_size,c.max_workgroup_dimensions)) or __import__('math').prod(k.launch.workgroup_size)>c.max_workgroup_size: raise AcceleratorDiagnostic(DiagnosticCode.UNSUPPORTED_CAPABILITY,"workgroup size")
        if any(space not in c.memory_spaces for b in k.buffers for space in (b.memory_space,)): raise AcceleratorDiagnostic(DiagnosticCode.UNSUPPORTED_CAPABILITY,"memory space")
        if any(i.operation not in c.supported_operations for i in k.instructions): raise AcceleratorDiagnostic(DiagnosticCode.UNSUPPORTED_OPERATION,str(k.name))
        if any(t not in c.supported_types for t in k.parameters) or (ValueType.F64 in k.parameters and not c.float64): raise AcceleratorDiagnostic(DiagnosticCode.UNSUPPORTED_CAPABILITY,"f64/type")
        if not k.required_capabilities.issubset({"FLOAT64" if c.float64 else ""} | ({"ATOMICS"} if c.atomics else set())): raise AcceleratorDiagnostic(DiagnosticCode.UNSUPPORTED_CAPABILITY,"required capability")

@dataclass(frozen=True)
class S3AcceleratorIR:
    program:AcceleratorProgram; schema:str="s3.accelerator.ir.v1"
    def canonical_bytes(self):
        def enc(x):
            if isinstance(x,Enum): return x.value
            if isinstance(x,tuple): return [enc(y) for y in x]
            if isinstance(x,frozenset): return sorted(enc(y) for y in x)
            if hasattr(x,"__dataclass_fields__"): return {k:enc(getattr(x,k)) for k in x.__dataclass_fields__}
            return x
        return (json.dumps({"schema":self.schema,"program":enc(self.program)},sort_keys=True,separators=(",",":"))+"\n").encode()
    def digest(self): return hashlib.sha256(self.canonical_bytes()).hexdigest()

def vector_add_fixture():
    b=(AcceleratorBuffer("a",ValueType.F32,1024,MemorySpace.GLOBAL,AccessMode.READ_ONLY),AcceleratorBuffer("b",ValueType.F32,1024,MemorySpace.GLOBAL,AccessMode.READ_ONLY),AcceleratorBuffer("out",ValueType.F32,1024,MemorySpace.GLOBAL,AccessMode.WRITE_ONLY))
    ins=(AcceleratorInstruction(Operation.GLOBAL_ID,(0,),ValueType.I32),AcceleratorInstruction(Operation.LOAD,("a",)),AcceleratorInstruction(Operation.LOAD,("b",)),AcceleratorInstruction(Operation.ADD,("a","b"),ValueType.F32),AcceleratorInstruction(Operation.STORE,("out",)),AcceleratorInstruction(Operation.RETURN))
    return S3AcceleratorIR(AcceleratorProgram((AcceleratorKernel("vector_add",(ValueType.I32,),b,ins,WorkDimensions((1024,),(256,))),)))

def saxpy_fixture():
    b=(AcceleratorBuffer("x",ValueType.F32,1024,MemorySpace.GLOBAL,AccessMode.READ_ONLY),AcceleratorBuffer("y",ValueType.F32,1024,MemorySpace.GLOBAL,AccessMode.READ_ONLY),AcceleratorBuffer("out",ValueType.F32,1024,MemorySpace.GLOBAL,AccessMode.WRITE_ONLY))
    ins=(AcceleratorInstruction(Operation.GLOBAL_ID,(0,),ValueType.I32),AcceleratorInstruction(Operation.LOAD,("x",)),AcceleratorInstruction(Operation.LOAD,("y",)),AcceleratorInstruction(Operation.MUL,("alpha","x"),ValueType.F32),AcceleratorInstruction(Operation.ADD,("alpha_x","y"),ValueType.F32),AcceleratorInstruction(Operation.STORE,("out",)),AcceleratorInstruction(Operation.RETURN))
    return S3AcceleratorIR(AcceleratorProgram((AcceleratorKernel("saxpy",(ValueType.F32,ValueType.I32),b,ins,WorkDimensions((1024,),(256,))),)))
