"""Deterministic target, memory-map, MMIO and link-layout contracts."""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import hashlib,json

class EmbeddedDiagnostic(ValueError):
    def __init__(self,code,message): self.code=code; self.message=message; super().__init__(f"{code}: {message}")
class DiagnosticCode(str,Enum):
    INVALID_TARGET="INVALID_TARGET"; INVALID_ARCHITECTURE="INVALID_ARCHITECTURE"; INVALID_MEMORY_REGION="INVALID_MEMORY_REGION"; MEMORY_REGION_OVERLAP="MEMORY_REGION_OVERLAP"; ADDRESS_OVERFLOW="ADDRESS_OVERFLOW"; INVALID_ALIGNMENT="INVALID_ALIGNMENT"; INVALID_MMIO_ACCESS="INVALID_MMIO_ACCESS"; UNSUPPORTED_WIDTH="UNSUPPORTED_WIDTH"; UNSUPPORTED_CAPABILITY="UNSUPPORTED_CAPABILITY"; INVALID_ENTRYPOINT="INVALID_ENTRYPOINT"; INVALID_LINK_LAYOUT="INVALID_LINK_LAYOUT"; TARGET_NOT_AVAILABLE="TARGET_NOT_AVAILABLE"; BOARD_NOT_AVAILABLE="BOARD_NOT_AVAILABLE"; TOOLCHAIN_NOT_AVAILABLE="TOOLCHAIN_NOT_AVAILABLE"
class ExecutionMode(str,Enum): HOSTED="hosted"; FREESTANDING="freestanding"
class RegionKind(str,Enum): FLASH="flash"; ROM="rom"; RAM="ram"; MMIO="mmio"; RESERVED="reserved"
class Permission(str,Enum): READ="r"; WRITE="w"; EXECUTE="x"
class ImageKind(str,Enum): ELF="elf"; RAW_BINARY="raw_binary"
class MMIOAccess(str,Enum): READ="read"; WRITE="write"

def _align(value):
    if value<=0 or value&(value-1): raise EmbeddedDiagnostic(DiagnosticCode.INVALID_ALIGNMENT,str(value))

@dataclass(frozen=True)
class MemoryRegion:
    name:str; start:int; size:int; kind:RegionKind; permissions:frozenset[Permission]; alignment:int=1
    def __post_init__(self):
        if not self.name or self.start<0 or self.size<=0: raise EmbeddedDiagnostic(DiagnosticCode.INVALID_MEMORY_REGION,self.name)
        if self.start+self.size>2**64: raise EmbeddedDiagnostic(DiagnosticCode.ADDRESS_OVERFLOW,self.name)
        _align(self.alignment)

@dataclass(frozen=True)
class MemoryMap:
    regions:tuple[MemoryRegion,...]
    def __post_init__(self):
        ordered=sorted(self.regions,key=lambda r:r.start)
        if len({r.name for r in ordered})!=len(ordered): raise EmbeddedDiagnostic(DiagnosticCode.INVALID_MEMORY_REGION,"duplicate region")
        for a,b in zip(ordered,ordered[1:]):
            if a.start+a.size>b.start: raise EmbeddedDiagnostic(DiagnosticCode.MEMORY_REGION_OVERLAP,f"{a.name}/{b.name}")
    def canonical_regions(self): return tuple(sorted(self.regions,key=lambda r:(r.start,r.name)))

@dataclass(frozen=True)
class ArchitectureTarget:
    architecture:str; endianness:str="little"; pointer_width:int=64; object_format:str="elf"; abi:str="freestanding"; isa_extensions:frozenset[str]=frozenset(); os_services:bool=False; atomics:bool=False; floating_point:frozenset[str]=frozenset(); mmu:bool=False; privilege:str="machine"
    def __post_init__(self):
        if self.architecture not in ("aarch64","riscv64"): raise EmbeddedDiagnostic(DiagnosticCode.INVALID_ARCHITECTURE,self.architecture)
        if self.endianness not in ("little","big") or self.pointer_width not in (32,64): raise EmbeddedDiagnostic(DiagnosticCode.INVALID_TARGET,"target fields")

@dataclass(frozen=True)
class BoardTarget:
    name:str; architecture:ArchitectureTarget; memory_map:MemoryMap; entrypoint:str="_start"; uart_address:int|None=None
    def __post_init__(self):
        if not self.name or not self.entrypoint or any(c.isspace() for c in self.entrypoint): raise EmbeddedDiagnostic(DiagnosticCode.INVALID_ENTRYPOINT,self.entrypoint)
        if self.uart_address is not None and self.uart_address<0: raise EmbeddedDiagnostic(DiagnosticCode.INVALID_MMIO_ACCESS,str(self.uart_address))

@dataclass(frozen=True)
class FreestandingTarget:
    architecture:ArchitectureTarget; board:BoardTarget|None=None; mode:ExecutionMode=ExecutionMode.FREESTANDING
    def __post_init__(self):
        if self.mode is not ExecutionMode.FREESTANDING: raise EmbeddedDiagnostic(DiagnosticCode.INVALID_TARGET,"freestanding target required")
        if self.board and self.board.architecture!=self.architecture: raise EmbeddedDiagnostic(DiagnosticCode.INVALID_TARGET,"architecture/board mismatch")

@dataclass(frozen=True)
class MemoryMappedIO:
    address:int; width:int; access:MMIOAccess; volatile:bool=True; alignment:int=1; unsafe:bool=True
    def __post_init__(self):
        if self.address<0 or self.width not in (8,16,32,64): raise EmbeddedDiagnostic(DiagnosticCode.UNSUPPORTED_WIDTH,str(self.width))
        if self.address%(self.width//8): raise EmbeddedDiagnostic(DiagnosticCode.INVALID_MMIO_ACCESS,"misaligned")
        _align(self.alignment)
        if not self.unsafe: raise EmbeddedDiagnostic(DiagnosticCode.INVALID_MMIO_ACCESS,"explicit unsafe boundary required")

@dataclass(frozen=True)
class LinkSection:
    name:str; region:str; alignment:int=1
    def __post_init__(self):
        if self.name not in (".text",".rodata",".data",".bss",".stack",".vector_table"): raise EmbeddedDiagnostic(DiagnosticCode.INVALID_LINK_LAYOUT,self.name)
        _align(self.alignment)

@dataclass(frozen=True)
class LinkLayout:
    sections:tuple[LinkSection,...]
    def __post_init__(self):
        if len({s.name for s in self.sections})!=len(self.sections): raise EmbeddedDiagnostic(DiagnosticCode.INVALID_LINK_LAYOUT,"duplicate section")

@dataclass(frozen=True)
class FreestandingArtifact:
    architecture:str; format:ImageKind; entrypoint:str; image_kind:ImageKind; digest:str; link_map_digest:str|None=None

@dataclass(frozen=True)
class TargetDescription:
    target:FreestandingTarget; memory_map:MemoryMap; layout:LinkLayout; schema:str="s3.target.freestanding.v1"
    def canonical_bytes(self):
        def e(x):
            if isinstance(x,Enum): return x.value
            if isinstance(x,(tuple,list)): return [e(y) for y in x]
            if isinstance(x,frozenset): return sorted(e(y) for y in x)
            if hasattr(x,"__dataclass_fields__"): return {k:e(getattr(x,k)) for k in x.__dataclass_fields__}
            return x
        return (json.dumps({"schema":self.schema,"target":e(self.target),"memory_map":e(self.memory_map),"layout":e(self.layout)},sort_keys=True,separators=(",",":"))+"\n").encode()
    def digest(self): return hashlib.sha256(self.canonical_bytes()).hexdigest()

def aarch64_qemu_virt():
    arch=ArchitectureTarget("aarch64",isa_extensions=frozenset({"A64"}),floating_point=frozenset({"fp_simd"}))
    mmap=MemoryMap((MemoryRegion("flash",0x40000000,0x100000,RegionKind.FLASH,frozenset({Permission.READ,Permission.EXECUTE}),4096),MemoryRegion("ram",0x40000000+0x100000,0x100000,RegionKind.RAM,frozenset({Permission.READ,Permission.WRITE}),4096),MemoryRegion("uart",0x09000000,0x1000,RegionKind.MMIO,frozenset({Permission.READ,Permission.WRITE}),4)))
    return TargetDescription(FreestandingTarget(arch,BoardTarget("qemu-virt-aarch64",arch,mmap,uart_address=0x09000000)),mmap,LinkLayout((LinkSection(".text","flash",4096),LinkSection(".rodata","flash"),LinkSection(".data","ram"),LinkSection(".bss","ram"),LinkSection(".stack","ram",16))))

def riscv64_contract():
    arch=ArchitectureTarget("riscv64",isa_extensions=frozenset({"I","M","A","F","D"}),floating_point=frozenset({"f32","f64"}))
    mmap=MemoryMap((MemoryRegion("ram",0x80000000,0x100000,RegionKind.RAM,frozenset({Permission.READ,Permission.WRITE,Permission.EXECUTE}),4096),))
    return TargetDescription(FreestandingTarget(arch,BoardTarget("qemu-virt-riscv64",arch,mmap)),mmap,LinkLayout((LinkSection(".text","ram",4096),LinkSection(".bss","ram"),LinkSection(".stack","ram",16))))
