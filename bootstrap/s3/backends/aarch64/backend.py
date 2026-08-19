"""Reviewable Linux AArch64 ABI and ELF structural contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import struct


AARCH64_ELF_MACHINE = 183
ELF64_CLASS = 2
ELF_LITTLE_ENDIAN = 1
AAPCS64_ARGUMENT_REGISTERS = tuple(f"x{index}" for index in range(8))
MAX_STRUCTURAL_INSTRUCTIONS = 100_000


class AArch64BackendError(ValueError):
    pass


class ExecutionCertification(Enum):
    CERTIFIED = "execution_certified"
    DEFERRED = "execution_certification_deferred"


@dataclass(frozen=True, slots=True)
class Aapcs64Call:
    argument_count: int
    return_register: str = "x0"

    def __post_init__(self) -> None:
        if isinstance(self.argument_count, bool) or not isinstance(self.argument_count, int) or self.argument_count < 0:
            raise AArch64BackendError("argument_count must be non-negative")
        if self.return_register != "x0":
            raise AArch64BackendError("scalar return must use x0 under AAPCS64")

    def location(self, index: int) -> str:
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < self.argument_count:
            raise AArch64BackendError("argument index is outside this call")
        if index < len(AAPCS64_ARGUMENT_REGISTERS):
            return AAPCS64_ARGUMENT_REGISTERS[index]
        return f"[sp+{8 * (index - len(AAPCS64_ARGUMENT_REGISTERS))}]"


@dataclass(frozen=True, slots=True)
class AArch64Assembly:
    instructions: tuple[str, ...]

    @property
    def text(self) -> str:
        return ".text\n" + "\n".join(f"    {item}" for item in self.instructions) + "\n"


@dataclass(frozen=True, slots=True)
class AArch64ElfHeader:
    entrypoint: int = 0

    def __post_init__(self) -> None:
        if isinstance(self.entrypoint, bool) or not isinstance(self.entrypoint, int) or self.entrypoint < 0:
            raise AArch64BackendError("ELF entrypoint must be non-negative")

    @property
    def bytes(self) -> bytes:
        header = bytearray(64)
        header[:4] = b"\x7fELF"
        header[4] = ELF64_CLASS
        header[5] = ELF_LITTLE_ENDIAN
        header[6] = 1
        struct.pack_into("<H", header, 16, 2)
        struct.pack_into("<H", header, 18, AARCH64_ELF_MACHINE)
        struct.pack_into("<I", header, 20, 1)
        struct.pack_into("<Q", header, 24, self.entrypoint)
        return bytes(header)

    def validate(self) -> None:
        if self.bytes[:4] != b"\x7fELF" or self.bytes[4] != ELF64_CLASS or self.bytes[5] != ELF_LITTLE_ENDIAN:
            raise AArch64BackendError("ELF identity is not ELF64 little endian")
        if struct.unpack_from("<H", self.bytes, 18)[0] != AARCH64_ELF_MACHINE:
            raise AArch64BackendError("ELF machine is not AArch64")


class AArch64Backend:
    """Structural V1 backend; native execution is intentionally separate."""

    execution_certification = ExecutionCertification.DEFERRED

    def __init__(self, *, max_instructions: int = MAX_STRUCTURAL_INSTRUCTIONS) -> None:
        if isinstance(max_instructions, bool) or not isinstance(max_instructions, int) or not 1 <= max_instructions <= MAX_STRUCTURAL_INSTRUCTIONS:
            raise AArch64BackendError("invalid structural instruction limit")
        self.max_instructions = max_instructions

    def emit_return(self, value: int) -> AArch64Assembly:
        if isinstance(value, bool) or not isinstance(value, int) or not -(1 << 15) <= value < (1 << 15):
            raise AArch64BackendError("V1 immediate return must fit the structural MOV contract")
        assembly = AArch64Assembly((f"mov x0, #{value}", "ret"))
        if len(assembly.instructions) > self.max_instructions:
            raise AArch64BackendError("instruction limit exceeded")
        return assembly

    def elf_header(self, *, entrypoint: int = 0) -> AArch64ElfHeader:
        header = AArch64ElfHeader(entrypoint)
        header.validate()
        return header

    def execution_status(self) -> ExecutionCertification:
        return self.execution_certification
