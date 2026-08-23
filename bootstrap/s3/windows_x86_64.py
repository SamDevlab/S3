"""Structural Win64 ABI facts for the bounded M1.65 backend preflight."""

from __future__ import annotations

from dataclasses import dataclass
import platform
import shutil
from typing import Sequence

from .assembly import AssemblyProgram, AssemblyType
from .targets import WINDOWS_X86_64_TARGET


WIN64_INTEGER_ARGUMENT_REGISTERS = ("rcx", "rdx", "r8", "r9")
WIN64_FLOAT_ARGUMENT_REGISTERS = ("xmm0", "xmm1", "xmm2", "xmm3")
WIN64_INTEGER_RETURN_REGISTER = "rax"
WIN64_FLOAT_RETURN_REGISTER = "xmm0"
WIN64_SHADOW_SPACE_BYTES = 32
WIN64_STACK_ALIGNMENT_BYTES = 16
WIN64_CALLEE_SAVED_REGISTERS = (
    "rbx",
    "rbp",
    "rdi",
    "rsi",
    "r12",
    "r13",
    "r14",
    "r15",
)
WIN64_CALLER_SAVED_REGISTERS = (
    "rax",
    "rcx",
    "rdx",
    "r8",
    "r9",
    "r10",
    "r11",
    "xmm0",
    "xmm1",
    "xmm2",
    "xmm3",
    "xmm4",
    "xmm5",
)


@dataclass(frozen=True, slots=True)
class Win64ArgumentLocation:
    index: int
    type_name: AssemblyType
    register: str | None
    stack_offset: int | None


@dataclass(frozen=True, slots=True)
class Win64CallLayout:
    arguments: tuple[Win64ArgumentLocation, ...]
    shadow_space_bytes: int
    stack_reservation_bytes: int

    @classmethod
    def for_arguments(cls, types: Sequence[AssemblyType]) -> Win64CallLayout:
        locations: list[Win64ArgumentLocation] = []
        stack_count = max(0, len(types) - 4)
        reservation = WIN64_SHADOW_SPACE_BYTES + stack_count * 8
        reservation = (reservation + 15) // WIN64_STACK_ALIGNMENT_BYTES * WIN64_STACK_ALIGNMENT_BYTES
        for index, type_name in enumerate(types):
            if not isinstance(type_name, AssemblyType):
                raise TypeError("Win64 argument types must be AssemblyType values")
            if index < 4:
                register = (
                    WIN64_FLOAT_ARGUMENT_REGISTERS[index]
                    if type_name is AssemblyType.F64
                    else WIN64_INTEGER_ARGUMENT_REGISTERS[index]
                )
                locations.append(Win64ArgumentLocation(index, type_name, register, None))
            else:
                locations.append(
                    Win64ArgumentLocation(
                        index,
                        type_name,
                        None,
                        WIN64_SHADOW_SPACE_BYTES + (index - 4) * 8,
                    )
                )
        return cls(tuple(locations), WIN64_SHADOW_SPACE_BYTES, reservation)


@dataclass(frozen=True, slots=True)
class Win64ResultLayout:
    logical_slots: tuple[int, ...]
    scalar_register: str | None
    transport: str

    @classmethod
    def for_result_types(cls, types: Sequence[AssemblyType]) -> Win64ResultLayout:
        normalized = tuple(types)
        if not normalized:
            return cls((), None, "void")
        if len(normalized) == 1:
            register = (
                WIN64_FLOAT_RETURN_REGISTER
                if normalized[0] is AssemblyType.F64
                else WIN64_INTEGER_RETURN_REGISTER
            )
            return cls((0,), register, "scalar-register")
        return cls(tuple(range(len(normalized))), None, "s3-logical-result-slots")


@dataclass(frozen=True, slots=True)
class Win64FunctionPlan:
    name: str
    call_layout: Win64CallLayout
    result_layout: Win64ResultLayout


@dataclass(frozen=True, slots=True)
class WindowsX8664BackendPlan:
    target_name: str
    functions: tuple[Win64FunctionPlan, ...]
    codegen_status: str

    @classmethod
    def from_program(cls, program: AssemblyProgram) -> WindowsX8664BackendPlan:
        if not isinstance(program, AssemblyProgram):
            raise TypeError("Win64 backend plans require an AssemblyProgram")
        return cls(
            WINDOWS_X86_64_TARGET.name,
            tuple(
                Win64FunctionPlan(
                    function.name,
                    Win64CallLayout.for_arguments(
                        tuple(parameter.type for parameter in function.parameters)
                    ),
                    Win64ResultLayout.for_result_types(function.result_types),
                )
                for function in program.functions
            ),
            "STRUCTURAL_ONLY_TOOLCHAIN_DEFERRED",
        )


@dataclass(frozen=True, slots=True)
class WindowsToolchainProbe:
    compiler: str | None
    linker: str | None
    assembler: str | None

    @property
    def available(self) -> bool:
        return self.compiler is not None and self.linker is not None

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, value in (
                ("compiler", self.compiler),
                ("linker", self.linker),
                ("assembler", self.assembler),
            )
            if value is None
        )


def probe_windows_toolchain() -> WindowsToolchainProbe:
    if platform.system() != "Windows":
        return WindowsToolchainProbe(None, None, None)
    compiler = next((shutil.which(name) for name in ("clang-cl", "clang") if shutil.which(name)), None)
    linker = next((shutil.which(name) for name in ("lld-link", "link") if shutil.which(name)), None)
    assembler = next((shutil.which(name) for name in ("ml64", "llvm-mc") if shutil.which(name)), None)
    return WindowsToolchainProbe(compiler, linker, assembler)
