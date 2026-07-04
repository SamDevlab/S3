"""Public boundary for validated S3 Assembly native generation."""

from __future__ import annotations

from dataclasses import dataclass

from ...assembly import AssemblyProgram
from ...emulator import DEFAULT_MAX_MEMORY_TRITS, Emulator
from .emitter import X8664Emitter


@dataclass(frozen=True, slots=True)
class X8664Backend:
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS

    def generate(self, program: AssemblyProgram) -> str:
        Emulator(max_memory_trits=self.max_memory_trits).validate(
            program,
            entry="main",
        )
        return X8664Emitter(program).emit()


def generate_native_assembly(
    program: AssemblyProgram,
    *,
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
) -> str:
    return X8664Backend(max_memory_trits=max_memory_trits).generate(program)

