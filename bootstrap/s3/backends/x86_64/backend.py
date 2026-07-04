"""Public boundary for validated S3 Assembly native generation."""

from __future__ import annotations

from dataclasses import dataclass

from ...assembly import AssemblyProgram
from ...emulator import (
    DEFAULT_MAX_FRAMES,
    DEFAULT_MAX_MEMORY_TRITS,
    Emulator,
)
from .diagnostics import NativeBackendError
from .emitter import X8664Emitter


@dataclass(frozen=True, slots=True)
class X8664Backend:
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS
    max_frames: int = DEFAULT_MAX_FRAMES

    def generate(self, program: AssemblyProgram) -> str:
        if self.max_frames < 1:
            raise NativeBackendError("max_frames must be at least 1")
        Emulator(max_memory_trits=self.max_memory_trits).validate(
            program,
            entry="main",
        )
        return X8664Emitter(program, max_frames=self.max_frames).emit()


def generate_native_assembly(
    program: AssemblyProgram,
    *,
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
    max_frames: int = DEFAULT_MAX_FRAMES,
) -> str:
    return X8664Backend(
        max_memory_trits=max_memory_trits,
        max_frames=max_frames,
    ).generate(program)
