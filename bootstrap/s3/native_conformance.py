"""Honest target classification and bounded hosted/native conformance records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import platform


class NativeConformanceError(ValueError):
    """Raised when native evidence is incomplete or contradictory."""


class TargetExecutionType(str, Enum):
    REAL_EXECUTION = "REAL_EXECUTION"
    EMULATED_EXECUTION = "EMULATED_EXECUTION"
    CROSS_COMPILE_ONLY = "CROSS_COMPILE_ONLY"
    UNAVAILABLE = "UNAVAILABLE"


class ConformanceStatus(str, Enum):
    PASS = "PASS"
    STRUCTURAL_ONLY = "STRUCTURAL_ONLY"
    DEFERRED_BY_ENVIRONMENT = "DEFERRED_BY_ENVIRONMENT"
    MISMATCH = "MISMATCH"


@dataclass(frozen=True, slots=True)
class NativeObservation:
    case: str
    target: str
    hosted_stdout: bytes
    hosted_exit_code: int
    execution_type: TargetExecutionType
    native_stdout: bytes | None = None
    native_exit_code: int | None = None
    structural_valid: bool = False
    executable_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.case, str) or not self.case.strip() or not isinstance(self.target, str) or not self.target.strip():
            raise NativeConformanceError("native observation identity is invalid")
        if not isinstance(self.hosted_stdout, bytes):
            raise NativeConformanceError("hosted output must be bytes")
        if isinstance(self.hosted_exit_code, bool) or not isinstance(self.hosted_exit_code, int):
            raise NativeConformanceError("hosted exit code must be an integer")
        if not isinstance(self.execution_type, TargetExecutionType):
            raise NativeConformanceError("native execution type is invalid")
        if self.native_stdout is not None and not isinstance(self.native_stdout, bytes):
            raise NativeConformanceError("native output must be bytes when supplied")
        if self.native_exit_code is not None and (isinstance(self.native_exit_code, bool) or not isinstance(self.native_exit_code, int)):
            raise NativeConformanceError("native exit code must be an integer when supplied")
        if self.executable_sha256 is not None and (
            not isinstance(self.executable_sha256, str) or len(self.executable_sha256) != 64 or any(char not in "0123456789abcdef" for char in self.executable_sha256)
        ):
            raise NativeConformanceError("native executable digest must be lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class ConformanceResult:
    case: str
    target: str
    execution_type: TargetExecutionType
    status: ConformanceStatus
    reason: str

    @property
    def json(self) -> str:
        return json.dumps(
            {
                "case": self.case,
                "execution_type": self.execution_type.value,
                "reason": self.reason,
                "status": self.status.value,
                "target": self.target,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"


def compare_hosted_native(observation: NativeObservation) -> ConformanceResult:
    """Compare exact stdout/exit evidence without treating structure as execution."""

    if not isinstance(observation, NativeObservation):
        raise NativeConformanceError("conformance requires a native observation")
    if observation.execution_type in (TargetExecutionType.REAL_EXECUTION, TargetExecutionType.EMULATED_EXECUTION):
        if observation.native_stdout is None or observation.native_exit_code is None:
            raise NativeConformanceError("runtime conformance requires native stdout and exit code")
        if observation.native_stdout != observation.hosted_stdout or observation.native_exit_code != observation.hosted_exit_code:
            return ConformanceResult(observation.case, observation.target, observation.execution_type, ConformanceStatus.MISMATCH, "hosted and native stdout/exit differ")
        return ConformanceResult(observation.case, observation.target, observation.execution_type, ConformanceStatus.PASS, "hosted and native stdout/exit match")
    if observation.execution_type is TargetExecutionType.CROSS_COMPILE_ONLY:
        if not observation.structural_valid:
            return ConformanceResult(observation.case, observation.target, observation.execution_type, ConformanceStatus.MISMATCH, "cross-compiled artifact failed structural validation")
        return ConformanceResult(observation.case, observation.target, observation.execution_type, ConformanceStatus.STRUCTURAL_ONLY, "cross-compiled artifact was not executed")
    return ConformanceResult(observation.case, observation.target, observation.execution_type, ConformanceStatus.DEFERRED_BY_ENVIRONMENT, "target execution environment is unavailable")


def classify_target_execution(
    target: str,
    *,
    system: str | None = None,
    machine: str | None = None,
    executable_available: bool = False,
    emulator_available: bool = False,
    cross_compiler_available: bool = False,
) -> TargetExecutionType:
    """Classify a target from explicit capabilities, never from an artifact alone."""

    if not isinstance(target, str) or not target.strip():
        raise NativeConformanceError("target identity is required")
    current_system = system or platform.system()
    current_machine = (machine or platform.machine()).lower()
    native_target = (
        target == "linux-x86_64" and current_system == "Linux" and current_machine in {"x86_64", "amd64"}
    ) or (
        target == "linux-aarch64" and current_system == "Linux" and current_machine in {"aarch64", "arm64"}
    ) or (
        target == "macos-arm64" and current_system == "Darwin" and current_machine in {"arm64", "aarch64"}
    )
    if native_target and executable_available:
        return TargetExecutionType.REAL_EXECUTION
    if emulator_available:
        return TargetExecutionType.EMULATED_EXECUTION
    if cross_compiler_available:
        return TargetExecutionType.CROSS_COMPILE_ONLY
    return TargetExecutionType.UNAVAILABLE


def executable_digest(executable: bytes) -> str:
    if not isinstance(executable, bytes) or not executable:
        raise NativeConformanceError("executable digest requires non-empty bytes")
    return hashlib.sha256(executable).hexdigest()
