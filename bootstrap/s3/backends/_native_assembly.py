"""Internal routing for native assembly generation providers."""

from __future__ import annotations

from ..assembly import AssemblyProgram
from ..emulator import (
    DEFAULT_MAX_FRAMES,
    DEFAULT_MAX_INSTRUCTIONS,
    DEFAULT_MAX_MEMORY_TRITS,
)
from ..targets import LINUX_X86_64_TARGET
from .registry import BackendRegistry, create_builtin_backend_registry


def _generate_native_assembly(
    program: AssemblyProgram,
    *,
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
    max_frames: int = DEFAULT_MAX_FRAMES,
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
) -> str:
    return _generate_native_assembly_with_registry(
        program,
        max_memory_trits=max_memory_trits,
        max_frames=max_frames,
        max_instructions=max_instructions,
        registry=create_builtin_backend_registry(),
    )


def _generate_native_assembly_with_registry(
    program: AssemblyProgram,
    *,
    max_memory_trits: int,
    max_frames: int,
    max_instructions: int,
    registry: BackendRegistry,
) -> str:
    provider = registry.get_native_assembly(LINUX_X86_64_TARGET.name)
    return provider.generate(
        program,
        max_memory_trits=max_memory_trits,
        max_frames=max_frames,
        max_instructions=max_instructions,
    )
