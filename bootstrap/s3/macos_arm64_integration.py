"""Explicit macOS ARM64 artifact integration for M1.89."""

from __future__ import annotations

from dataclasses import dataclass

from .arm64_integration import Arm64ExecutionStatus, Arm64TargetArtifact, MacOSArm64Integration


@dataclass(frozen=True, slots=True)
class MacOSArm64ReleaseArtifact:
    artifact: Arm64TargetArtifact
    format: str = "mach-o-64-arm64"

    @property
    def execution_deferred(self) -> bool:
        return self.artifact.execution_status is Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT


def build_macos_arm64_scalar_return(value: int) -> MacOSArm64ReleaseArtifact:
    return MacOSArm64ReleaseArtifact(MacOSArm64Integration().build_scalar_return(value))
