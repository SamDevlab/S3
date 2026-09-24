import hashlib,pytest
from bootstrap.s3.embedded.model import *

def test_targets_are_deterministic():
    a=aarch64_qemu_virt(); assert a.canonical_bytes()==aarch64_qemu_virt().canonical_bytes(); assert a.digest()==hashlib.sha256(a.canonical_bytes()).hexdigest(); assert a.digest()!=riscv64_contract().digest()

def test_memory_map_overlap_overflow_alignment():
    with pytest.raises(EmbeddedDiagnostic): MemoryMap((MemoryRegion('a',0,10,RegionKind.RAM,frozenset({Permission.READ})),MemoryRegion('b',5,10,RegionKind.RAM,frozenset({Permission.READ}))))
    with pytest.raises(EmbeddedDiagnostic): MemoryRegion('x',2**64-2,4,RegionKind.RAM,frozenset())
    with pytest.raises(EmbeddedDiagnostic): MemoryRegion('x',0,4,RegionKind.RAM,frozenset(),3)

def test_mmio_is_explicit_unsafe_and_width_checked():
    assert MemoryMappedIO(0x1000,32,MMIOAccess.WRITE).volatile
    with pytest.raises(EmbeddedDiagnostic): MemoryMappedIO(0x1001,32,MMIOAccess.WRITE)
    with pytest.raises(EmbeddedDiagnostic): MemoryMappedIO(0x1000,24,MMIOAccess.WRITE)
    with pytest.raises(EmbeddedDiagnostic): MemoryMappedIO(0x1000,32,MMIOAccess.WRITE,unsafe=False)

def test_hosted_freestanding_separation_and_layout():
    with pytest.raises(EmbeddedDiagnostic): FreestandingTarget(ArchitectureTarget('aarch64'),mode=ExecutionMode.HOSTED)
    with pytest.raises(EmbeddedDiagnostic): LinkLayout((LinkSection('.text','flash'),LinkSection('.text','ram')))
    assert aarch64_qemu_virt().target.board.name=='qemu-virt-aarch64'; assert riscv64_contract().target.board.name=='qemu-virt-riscv64'

def test_invalid_architecture_and_board_mismatch():
    with pytest.raises(EmbeddedDiagnostic): ArchitectureTarget('x86')
    arch=ArchitectureTarget('aarch64'); other=ArchitectureTarget('riscv64'); mmap=MemoryMap((MemoryRegion('ram',0,1,RegionKind.RAM,frozenset()),))
    board=BoardTarget('bad',other,mmap)
    with pytest.raises(EmbeddedDiagnostic): FreestandingTarget(arch,board)
