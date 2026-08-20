"""Cross-target AArch64 program integration with honest execution status."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import re

from .aarch64_program import AArch64ProgramArtifact, AArch64ProgramLowerer, validate_aarch64_program_artifact
from .assembly import AssemblyProgram
from .backends.aarch64 import AArch64Assembly, AArch64Backend
from .backends.macos_arm64 import MachOBackend
from .targets import LINUX_AARCH64_TARGET, MACOS_ARM64_TARGET, TargetSpec


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


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


@dataclass(frozen=True, slots=True)
class Arm64NativeExecutionEvidence:
    """Evidence record bound to one structural artifact and native executable."""

    target: str
    artifact_sha256: str
    executable_sha256: str
    toolchain_id: str
    exit_code: int
    observed_value: int | None = None
    expected_value: int | None = None


def create_native_execution_evidence(
    artifact: Arm64TargetArtifact | Arm64ProgramIntegrationArtifact,
    *,
    executable: bytes,
    toolchain_id: str,
    exit_code: int,
    observed_value: int | None = None,
    expected_value: int | None = None,
) -> Arm64NativeExecutionEvidence:
    """Create a bounded evidence record after an external native execution.

    This helper does not execute code. Platform-specific runners must supply the
    actual executable bytes and observed result; the record cryptographically
    binds those bytes to the exact structural artifact that is later certified.
    """

    if not isinstance(executable, bytes) or not executable:
        raise ValueError("native execution evidence requires non-empty executable bytes")
    if not isinstance(toolchain_id, str) or not toolchain_id.strip() or len(toolchain_id) > 256:
        raise ValueError("native execution evidence requires a bounded toolchain identity")
    if isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise ValueError("native execution evidence exit code must be an integer")
    if observed_value is not None and (isinstance(observed_value, bool) or not isinstance(observed_value, int)):
        raise ValueError("native observed value must be an integer when supplied")
    if expected_value is not None and (isinstance(expected_value, bool) or not isinstance(expected_value, int)):
        raise ValueError("native expected value must be an integer when supplied")
    return Arm64NativeExecutionEvidence(
        artifact.target.name,
        _artifact_sha256(artifact),
        hashlib.sha256(executable).hexdigest(),
        toolchain_id.strip(),
        exit_code,
        observed_value,
        expected_value,
    )


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

    def certify_native_result(self, artifact: Arm64TargetArtifact, *, evidence: Arm64NativeExecutionEvidence) -> Arm64TargetArtifact:
        _validate_execution_evidence(artifact, evidence, require_value=True)
        if evidence.exit_code != 0 or evidence.observed_value != evidence.expected_value:
            raise ValueError("native AArch64 result does not match the artifact contract")
        return Arm64TargetArtifact(artifact.target, artifact.assembly, artifact.container_header, artifact.instruction_count, artifact.structural_valid, Arm64ExecutionStatus.NATIVE_CERTIFIED)

    def certify_native_program(self, artifact: Arm64ProgramIntegrationArtifact, *, evidence: Arm64NativeExecutionEvidence) -> Arm64ProgramIntegrationArtifact:
        _validate_execution_evidence(artifact, evidence, require_value=False)
        if evidence.exit_code != 0 or not artifact.structural_valid:
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

    def certify_native_result(self, artifact: Arm64TargetArtifact, *, evidence: Arm64NativeExecutionEvidence) -> Arm64TargetArtifact:
        _validate_execution_evidence(artifact, evidence, require_value=True)
        if evidence.exit_code != 0 or evidence.observed_value != evidence.expected_value:
            raise ValueError("native macOS ARM64 result does not match the artifact contract")
        return Arm64TargetArtifact(artifact.target, artifact.assembly, artifact.container_header, artifact.instruction_count, artifact.structural_valid, Arm64ExecutionStatus.NATIVE_CERTIFIED)

    def certify_native_program(self, artifact: Arm64ProgramIntegrationArtifact, *, evidence: Arm64NativeExecutionEvidence) -> Arm64ProgramIntegrationArtifact:
        _validate_execution_evidence(artifact, evidence, require_value=False)
        if evidence.exit_code != 0 or not artifact.structural_valid:
            raise ValueError("native macOS ARM64 program execution did not satisfy the artifact contract")
        return Arm64ProgramIntegrationArtifact(artifact.target, artifact.program, True, Arm64ExecutionStatus.NATIVE_CERTIFIED)


def _validate_execution_evidence(
    artifact: Arm64TargetArtifact | Arm64ProgramIntegrationArtifact,
    evidence: Arm64NativeExecutionEvidence,
    *,
    require_value: bool,
) -> None:
    if not isinstance(evidence, Arm64NativeExecutionEvidence):
        raise ValueError("native certification requires an execution evidence record")
    if evidence.target != artifact.target.name or evidence.artifact_sha256 != _artifact_sha256(artifact):
        raise ValueError("native execution evidence is not bound to this artifact")
    if _SHA256.fullmatch(evidence.executable_sha256) is None or not evidence.toolchain_id:
        raise ValueError("native execution evidence is incomplete")
    if require_value and (evidence.observed_value is None or evidence.expected_value is None):
        raise ValueError("native scalar certification requires observed and expected values")


def _artifact_sha256(artifact: Arm64TargetArtifact | Arm64ProgramIntegrationArtifact) -> str:
    digest = hashlib.sha256()
    digest.update(artifact.target.name.encode("utf-8"))
    digest.update(b"\0")
    digest.update(artifact.container_header)
    digest.update(b"\0")
    digest.update(str(artifact.instruction_count).encode("ascii"))
    if isinstance(artifact, Arm64TargetArtifact):
        for instruction in artifact.assembly.instructions:
            digest.update(b"\0")
            digest.update(instruction.encode("utf-8"))
    else:
        digest.update(b"\0")
        digest.update(artifact.text.encode("utf-8"))
        for symbol in artifact.runtime_symbols:
            digest.update(b"\0")
            digest.update(symbol.encode("utf-8"))
    return digest.hexdigest()
