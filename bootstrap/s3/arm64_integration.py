"""Cross-target artifact integration and honest execution status for M1.88."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .backends.aarch64 import AArch64Assembly, AArch64Backend, AArch64ElfHeader
from .backends.macos_arm64 import MachOBackend, MachOHeader
from .targets import LINUX_AARCH64_TARGET, MACOS_ARM64_TARGET, TargetSpec


class Arm64ExecutionStatus(Enum):
    STRUCTURAL_CERTIFIED = "structural_certified"
    DEFERRED_BY_ENVIRONMENT = "deferred_by_environment"
    NATIVE_CERTIFIED = "native_certified"


@dataclass(frozen=True, slots=True)
class Arm64TargetArtifact:
    target: TargetSpec
    assembly: AArch64Assembly
    container_header: bytes
    instruction_count: int
    structural_valid: bool
    execution_status: Arm64ExecutionStatus


class LinuxAArch64Integration:
    target = LINUX_AARCH64_TARGET

    def __init__(self, *, max_instructions: int = 100_000) -> None:
        self.backend = AArch64Backend(max_instructions=max_instructions)

    def build_scalar_return(self, value: int) -> Arm64TargetArtifact:
        assembly = self.backend.emit_return(value)
        header = self.backend.elf_header().bytes
        return Arm64TargetArtifact(self.target, assembly, header, len(assembly.instructions), True, Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT)

    def certify_native_result(self, artifact: Arm64TargetArtifact, *, exit_code: int, observed_value: int, expected_value: int) -> Arm64TargetArtifact:
        if exit_code != 0 or observed_value != expected_value:
            raise ValueError("native AArch64 result does not match the artifact contract")
        return Arm64TargetArtifact(artifact.target, artifact.assembly, artifact.container_header, artifact.instruction_count, artifact.structural_valid, Arm64ExecutionStatus.NATIVE_CERTIFIED)


class MacOSArm64Integration:
    target = MACOS_ARM64_TARGET

    def __init__(self) -> None:
        self.backend = MachOBackend()

    def build_scalar_return(self, value: int) -> Arm64TargetArtifact:
        assembly = self.backend.emit_return(value)
        header = self.backend.header().bytes
        return Arm64TargetArtifact(self.target, assembly, header, len(assembly.instructions), True, Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT)

    def certify_native_result(self, artifact: Arm64TargetArtifact, *, exit_code: int, observed_value: int, expected_value: int) -> Arm64TargetArtifact:
        if exit_code != 0 or observed_value != expected_value:
            raise ValueError("native macOS ARM64 result does not match the artifact contract")
        return Arm64TargetArtifact(artifact.target, artifact.assembly, artifact.container_header, artifact.instruction_count, artifact.structural_valid, Arm64ExecutionStatus.NATIVE_CERTIFIED)
