"""Deterministic Mach-O ARM64 structural contract for M1.78."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import struct

from ..aarch64 import AArch64Assembly, Aapcs64Call


MACHO64_MAGIC = 0xFEEDFACF
ARM64_CPU_TYPE = 0x0100000C
MH_EXECUTE = 2


class MachOBackendError(ValueError):
    pass


class ExecutionCertification(Enum):
    CERTIFIED = "execution_certified"
    DEFERRED = "execution_certification_deferred"


@dataclass(frozen=True, slots=True)
class MachOHeader:
    cpu_subtype: int = 0
    file_type: int = MH_EXECUTE

    def __post_init__(self) -> None:
        if isinstance(self.cpu_subtype, bool) or not isinstance(self.cpu_subtype, int) or self.cpu_subtype < 0:
            raise MachOBackendError("CPU subtype must be non-negative")
        if self.file_type != MH_EXECUTE:
            raise MachOBackendError("V1 supports executable Mach-O only")

    @property
    def bytes(self) -> bytes:
        return struct.pack(
            "<IiiIIIII",
            MACHO64_MAGIC,
            ARM64_CPU_TYPE,
            self.cpu_subtype,
            self.file_type,
            0,
            0,
            0,
            0,
        )

    def validate(self) -> None:
        magic, cpu_type, cpu_subtype, file_type, _ncmds, _sizeofcmds, _flags, _reserved = struct.unpack("<IiiIIIII", self.bytes)
        if magic != MACHO64_MAGIC or cpu_type != ARM64_CPU_TYPE or cpu_subtype != self.cpu_subtype or file_type != MH_EXECUTE:
            raise MachOBackendError("invalid ARM64 Mach-O identity")


class MachOBackend:
    execution_certification = ExecutionCertification.DEFERRED

    def emit_return(self, value: int) -> AArch64Assembly:
        # The scalar ARM64 instruction contract is shared with M1.77.
        from ..aarch64 import AArch64Backend

        return AArch64Backend().emit_return(value)

    def header(self, *, cpu_subtype: int = 0) -> MachOHeader:
        header = MachOHeader(cpu_subtype=cpu_subtype)
        header.validate()
        return header

    def abi_call(self, argument_count: int) -> Aapcs64Call:
        return Aapcs64Call(argument_count)

    def execution_status(self) -> ExecutionCertification:
        return self.execution_certification
