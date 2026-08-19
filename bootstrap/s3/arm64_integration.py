"""Cross-target AArch64 program integration with honest execution status."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .aarch64_program import AArch64ProgramArtifact, AArch64ProgramLowerer, validate_aarch64_program_artifact
from .assembly import AssemblyProgram
from .backends.aarch64 import AArch64Assembly, AArch64Backend
from .backends.macos_arm64 import MachOBackend
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


@dataclass(frozen=True, slots=True)
class Arm64ProgramIntegrationArtifact:
    target: TargetSpec
    program: AArch64ProgramArtifact
    structural_valid: bool
    execution_status: Arm64ExecutionStatus

    @property
    def container_header(self) -> bytes:
        return self.program.container_header

    @property
    def text(self) -> str:
        return self.program.text

    @property
    def instruction_count(self) -> int:
        return self.program.instruction_count

    @property
    def runtime_symbols(self) -> tuple[str, ...]:
        return self.program.runtime_symbols


class LinuxAArch64Integration:
    target = LINUX_AARCH64_TARGET

    def __init__(self, *, max_instructions: int = 100_000) -> None:
        self.backend = AArch64Backend(max_instructions=max_instructions)
        self.program_lowerer = AArch64ProgramLowerer("linux-aarch64", max_instructions=max_instructions)

    def build_scalar_return(self, value: int) -> Arm64TargetArtifact:
        assembly = self.backend.emit_return(value)
        header = self.backend.elf_header().bytes
        return Arm64TargetArtifact(self.target, assembly, header, len(assembly.instructions), True, Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT)

    def build_program(self, program: AssemblyProgram) -> Arm64ProgramIntegrationArtifact:
        lowered = self.program_lowerer.lower(program)
        validate_aarch64_program_artifact(lowered)
        return Arm64ProgramIntegrationArtifact(self.target, lowered, True, Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT)

    def certify_native_result(self, artifact: Arm64TargetArtifact, *, exit_code: int, observed_value: int, expected_value: int) -> Arm64TargetArtifact:
        if exit_code != 0 or observed_value != expected_value:
            raise ValueError("native AArch64 result does not match the artifact contract")
        return Arm64TargetArtifact(artifact.target, artifact.assembly, artifact.container_header, artifact.instruction_count, artifact.structural_valid, Arm64ExecutionStatus.NATIVE_CERTIFIED)

    def certify_native_program(self, artifact: Arm64ProgramIntegrationArtifact, *, exit_code: int) -> Arm64ProgramIntegrationArtifact:
        if exit_code != 0 or not artifact.structural_valid:
            raise ValueError("native Linux AArch64 program execution did not satisfy the artifact contract")
        return Arm64ProgramIntegrationArtifact(artifact.target, artifact.program, True, Arm64ExecutionStatus.NATIVE_CERTIFIED)


class MacOSArm64Integration:
    target = MACOS_ARM64_TARGET

    def __init__(self, *, max_instructions: int = 100_000) -> None:
        self.backend = MachOBackend()
        self.program_lowerer = AArch64ProgramLowerer("macos-arm64", max_instructions=max_instructions)

    def build_scalar_return(self, value: int) -> Arm64TargetArtifact:
        assembly = self.backend.emit_return(value)
        header = self.backend.header().bytes
        return Arm64TargetArtifact(self.target, assembly, header, len(assembly.instructions), True, Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT)

    def build_program(self, program: AssemblyProgram) -> Arm64ProgramIntegrationArtifact:
        lowered = self.program_lowerer.lower(program)
        validate_aarch64_program_artifact(lowered)
        return Arm64ProgramIntegrationArtifact(self.target, lowered, True, Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT)

    def certify_native_result(self, artifact: Arm64TargetArtifact, *, exit_code: int, observed_value: int, expected_value: int) -> Arm64TargetArtifact:
        if exit_code != 0 or observed_value != expected_value:
            raise ValueError("native macOS ARM64 result does not match the artifact contract")
        return Arm64TargetArtifact(artifact.target, artifact.assembly, artifact.container_header, artifact.instruction_count, artifact.structural_valid, Arm64ExecutionStatus.NATIVE_CERTIFIED)

    def certify_native_program(self, artifact: Arm64ProgramIntegrationArtifact, *, exit_code: int) -> Arm64ProgramIntegrationArtifact:
        if exit_code != 0 or not artifact.structural_valid:
            raise ValueError("native macOS ARM64 program execution did not satisfy the artifact contract")
        return Arm64ProgramIntegrationArtifact(artifact.target, artifact.program, True, Arm64ExecutionStatus.NATIVE_CERTIFIED)
