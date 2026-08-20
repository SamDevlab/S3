"""Explicit macOS ARM64 artifact/program integration for M1.89."""

from __future__ import annotations

from dataclasses import dataclass

from .arm64_integration import (
    Arm64ExecutionStatus,
    Arm64ProgramIntegrationArtifact,
    Arm64TargetArtifact,
    MacOSArm64Integration,
)
from .assembly import AssemblyProgram


@dataclass(frozen=True, slots=True)
class MacOSArm64ReleaseArtifact:
    artifact: Arm64TargetArtifact
    format: str = "mach-o-64-arm64"

    @property
    def execution_deferred(self) -> bool:
        return self.artifact.execution_status is Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT


@dataclass(frozen=True, slots=True)
class MacOSArm64ProgramArtifact:
    artifact: Arm64ProgramIntegrationArtifact
    format: str = "mach-o-64-arm64"

    @property
    def execution_deferred(self) -> bool:
        return self.artifact.execution_status is Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT

    @property
    def text(self) -> str:
        return self.artifact.text


def build_macos_arm64_scalar_return(value: int) -> MacOSArm64ReleaseArtifact:
    return MacOSArm64ReleaseArtifact(MacOSArm64Integration().build_scalar_return(value))


def build_macos_arm64_program(program: AssemblyProgram, *, max_instructions: int = 100_000) -> MacOSArm64ProgramArtifact:
    return MacOSArm64ProgramArtifact(MacOSArm64Integration(max_instructions=max_instructions).build_program(program))
