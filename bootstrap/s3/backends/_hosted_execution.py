"""Internal routing for hosted assembly execution providers."""

from __future__ import annotations

from ..assembly import AssemblyProgram
from ..emulator import (
    DEFAULT_MAX_FRAMES,
    DEFAULT_MAX_INSTRUCTIONS,
    DEFAULT_MAX_MEMORY_TRITS,
)
from .registry import BackendRegistry, create_builtin_backend_registry


_HOSTED_EMULATOR_PROVIDER = "hosted-emulator"


def _execute_hosted_assembly(
    program: AssemblyProgram,
    entry: str = "main",
    *,
    max_frames: int = DEFAULT_MAX_FRAMES,
    max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
    max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
) -> int:
    return _execute_hosted_assembly_with_registry(
        program,
        entry,
        max_frames=max_frames,
        max_instructions=max_instructions,
        max_memory_trits=max_memory_trits,
        registry=create_builtin_backend_registry(),
    )


def _execute_hosted_assembly_with_registry(
    program: AssemblyProgram,
    entry: str,
    *,
    max_frames: int,
    max_instructions: int,
    max_memory_trits: int,
    registry: BackendRegistry,
) -> int:
    provider = registry.get_hosted_execution(_HOSTED_EMULATOR_PROVIDER)
    return provider.execute(
        program,
        entry,
        max_frames=max_frames,
        max_instructions=max_instructions,
        max_memory_trits=max_memory_trits,
    )
