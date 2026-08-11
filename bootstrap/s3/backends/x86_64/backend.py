"""Public boundary for validated S3 Assembly native generation."""

from __future__ import annotations

from dataclasses import dataclass

from ...assembly import AssemblyProgram, AssemblyType
from ...assembly_verifier import AssemblyVerifier
from ...emulator import DEFAULT_MAX_FRAMES, DEFAULT_MAX_INSTRUCTIONS, DEFAULT_MAX_MEMORY_TRITS
from .diagnostics import NativeBackendError
from .emitter import X8664Emitter

NATIVE_MAX_INSTRUCTIONS = (1 << 64) - 1


@dataclass(frozen=True, slots=True)
class X8664Backend:
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS
    max_frames: int = DEFAULT_MAX_FRAMES
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS
    register_allocation: bool = False

    def generate(self, program: AssemblyProgram) -> str:
        if isinstance(self.max_instructions, bool) or not isinstance(self.max_instructions, int):
            raise TypeError("max_instructions must be an integer")
        if self.max_frames < 1:
            raise NativeBackendError("max_frames must be at least 1")
        if self.max_instructions < 1:
            raise NativeBackendError("max_instructions must be at least 1")
        if self.max_instructions > NATIVE_MAX_INSTRUCTIONS:
            raise NativeBackendError(f"max_instructions exceeds physical 64-bit limit of {NATIVE_MAX_INSTRUCTIONS}")
        AssemblyVerifier(max_memory_trits=self.max_memory_trits).validate(
            program,
            entry="main",
        )
        main = next(function for function in program.functions if function.name == "main")
        if main.return_type is AssemblyType.STRING:
            raise NativeBackendError(
                "native entry function 'main' cannot return string"
            )
        if main.return_type is AssemblyType.F64:
            raise NativeBackendError(
                "native entry function 'main' cannot return f64 until the "
                "standalone runtime provides decimal float output"
            )
        if main.result_width != 1:
            raise NativeBackendError(
                "native entry function 'main' must return one result cell"
            )
        return X8664Emitter(
            program,
            max_frames=self.max_frames,
            max_instructions=self.max_instructions,
            register_allocation=self.register_allocation,
        ).emit()

    def _generate_ffi(self, program: AssemblyProgram) -> str:
        return X8664Emitter(
            program,
            max_frames=self.max_frames,
            max_instructions=self.max_instructions,
            register_allocation=self.register_allocation,
        ).emit()


def generate_native_assembly(
    program: AssemblyProgram,
    *,
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
    max_frames: int = DEFAULT_MAX_FRAMES,
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
) -> str:
    from .._native_assembly import _generate_native_assembly

    return _generate_native_assembly(
        program,
        max_memory_trits=max_memory_trits,
        max_frames=max_frames,
        max_instructions=max_instructions,
    )


def generate_ffi_assembly(
    program: AssemblyProgram,
    *,
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
    max_frames: int = DEFAULT_MAX_FRAMES,
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
) -> str:
    """Generate native text for a hosted FFI artifact without entry restrictions."""

    AssemblyVerifier(max_memory_trits=max_memory_trits).validate(program)
    return X8664Backend(
        max_memory_trits=max_memory_trits,
        max_frames=max_frames,
        max_instructions=max_instructions,
    )._generate_ffi(program)
