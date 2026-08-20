"""AArch64 ABI, target-selection, and native toolchain boundary for M1.88/M1.89."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .aarch64_program import AArch64ProgramArtifact, AArch64ProgramLowerer
from .assembly import AssemblyProgram
from .codegen_optimization import eliminate_redundant_noop_moves
from .backends.registry import (
    BackendRegistry,
    HostedEmulatorBackend,
    LinuxX8664NativeAssemblyBackend,
)
from .targets import (
    LINUX_AARCH64_TARGET,
    LINUX_X86_64_TARGET,
    MACOS_ARM64_TARGET,
    cross_platform_target_catalog,
)


@dataclass(frozen=True, slots=True)
class AArch64ABIContract:
    stack_alignment: int = 16
    integer_arguments: tuple[str, ...] = ("x0", "x1", "x2", "x3", "x4", "x5", "x6", "x7")
    floating_arguments: tuple[str, ...] = ("v0", "v1", "v2", "v3", "v4", "v5", "v6", "v7")
    indirect_result: str = "x8"
    frame_pointer: str = "x29"
    link_register: str = "x30"
    callee_saved: tuple[str, ...] = ("x19", "x20", "x21", "x22", "x23", "x24", "x25", "x26", "x27", "x28")
    max_program_instructions: int = 100_000


AAPCS64_V1 = AArch64ABIContract()


@dataclass(frozen=True, slots=True)
class AArch64Relocation:
    symbol: str
    kind: str = "call26"
    offset: int = 0


@dataclass(frozen=True, slots=True)
class AArch64NativeBuildPlan:
    target: str
    assembly_text: str
    container_header: bytes
    runtime_symbols: tuple[str, ...]
    relocations: tuple[AArch64Relocation, ...]
    abi: AArch64ABIContract = AAPCS64_V1
    defined_symbols: tuple[str, ...] = ()
    entry_symbol: str = "main"

    @property
    def structurally_complete(self) -> bool:
        return bool(self.assembly_text) and self.abi.stack_alignment == 16 and self.abi.max_program_instructions == 100_000


class AArch64NativeToolchainProvider(Protocol):
    """Platform provider boundary; implementation is environment/toolchain specific."""

    def assemble_and_link(self, plan: AArch64NativeBuildPlan) -> bytes: ...


@dataclass(frozen=True, slots=True)
class LinuxAArch64NativeAssemblyBackend:
    max_instructions: int = 100_000

    def generate(self, program: AssemblyProgram, **limits) -> str:
        requested = int(limits.get("max_instructions", self.max_instructions))
        limit = min(self.max_instructions, requested, 100_000)
        optimized, _optimization = eliminate_redundant_noop_moves(program)
        return AArch64ProgramLowerer("linux-aarch64", max_instructions=limit).lower(optimized).text

    def build_plan(self, program: AssemblyProgram) -> AArch64NativeBuildPlan:
        return _plan(
            AArch64ProgramLowerer("linux-aarch64", max_instructions=self.max_instructions).lower(
                eliminate_redundant_noop_moves(program)[0]
            ),
            program,
        )


@dataclass(frozen=True, slots=True)
class MacOSArm64NativeAssemblyBackend:
    max_instructions: int = 100_000

    def generate(self, program: AssemblyProgram, **limits) -> str:
        requested = int(limits.get("max_instructions", self.max_instructions))
        limit = min(self.max_instructions, requested, 100_000)
        optimized, _optimization = eliminate_redundant_noop_moves(program)
        return AArch64ProgramLowerer("macos-arm64", max_instructions=limit).lower(optimized).text

    def build_plan(self, program: AssemblyProgram) -> AArch64NativeBuildPlan:
        return _plan(
            AArch64ProgramLowerer("macos-arm64", max_instructions=self.max_instructions).lower(
                eliminate_redundant_noop_moves(program)[0]
            ),
            program,
        )


def create_cross_platform_backend_registry() -> BackendRegistry:
    """Explicit opt-in registry containing x86-64 and both ARM64 native routes.

    The historical builtin registry remains Linux-x86_64-only so existing
    default target behavior does not change accidentally.  M1.88/M1.89 target
    selection is explicit through this cross-platform registry.
    """

    return BackendRegistry(
        hosted_execution=(("hosted-emulator", HostedEmulatorBackend()),),
        native_assembly=(
            (LINUX_X86_64_TARGET, LinuxX8664NativeAssemblyBackend()),
            (LINUX_AARCH64_TARGET, LinuxAArch64NativeAssemblyBackend()),
            (MACOS_ARM64_TARGET, MacOSArm64NativeAssemblyBackend()),
        ),
        target_catalog=cross_platform_target_catalog(),
    )


def build_native_with_provider(
    plan: AArch64NativeBuildPlan,
    provider: AArch64NativeToolchainProvider,
    *,
    max_output_bytes: int = 64 * 1024 * 1024,
) -> bytes:
    if not plan.structurally_complete:
        raise ValueError("AArch64 native build plan is structurally incomplete")
    if isinstance(max_output_bytes, bool) or not isinstance(max_output_bytes, int) or max_output_bytes <= 0:
        raise ValueError("native output limit must be positive")
    output = provider.assemble_and_link(plan)
    if not isinstance(output, bytes) or not output or len(output) > max_output_bytes:
        raise ValueError("native toolchain provider returned invalid or oversized output")
    return output


def _plan(artifact: AArch64ProgramArtifact, program: AssemblyProgram) -> AArch64NativeBuildPlan:
    defined_symbols = tuple(function.name for function in program.functions)
    relocations: list[AArch64Relocation] = []
    for offset, line in enumerate(artifact.text.splitlines()):
        stripped = line.strip()
        if stripped.startswith("bl "):
            relocations.append(AArch64Relocation(stripped[3:].strip(), offset=offset))
    return AArch64NativeBuildPlan(
        artifact.target,
        artifact.text,
        artifact.container_header,
        artifact.runtime_symbols,
        tuple(relocations),
        defined_symbols=defined_symbols,
    )
