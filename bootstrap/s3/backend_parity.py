"""Cross-platform native backend parity contracts for M1.98.

The matrix binds every emitted artifact to an explicit registered target.  It
does not turn structural assembly into native execution evidence; native
results remain target-specific provider evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re

from .assembly import AssemblyProgram
from .backends.registry import BackendRegistry, BackendRegistryError
from .emulator import AssemblyValue
from .targets import LINUX_AARCH64_TARGET, LINUX_X86_64_TARGET, MACOS_ARM64_TARGET, TargetSpec


PARITY_TARGETS = (LINUX_X86_64_TARGET, LINUX_AARCH64_TARGET, MACOS_ARM64_TARGET)
MAX_PARITY_INSTRUCTIONS = 100_000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class BackendParityError(ValueError):
    """Raised when registered backends cannot satisfy the parity contract."""


@dataclass(frozen=True, slots=True)
class BackendParityEvidence:
    target: TargetSpec
    source_sha256: str
    assembly_sha256: str
    instruction_count: int
    hosted_result: AssemblyValue
    native_status: str = "STRUCTURAL_ONLY_TOOLCHAIN_DEFERRED"


@dataclass(frozen=True, slots=True)
class BackendParityMatrix:
    source_sha256: str
    hosted_result: AssemblyValue
    targets: tuple[BackendParityEvidence, ...]

    @property
    def target_names(self) -> tuple[str, ...]:
        return tuple(item.target.name for item in self.targets)

    @property
    def structural_valid(self) -> bool:
        try:
            validate_backend_parity(self)
        except BackendParityError:
            return False
        return True


def build_backend_parity_matrix(
    registry: BackendRegistry,
    program: AssemblyProgram,
    *,
    source_sha256: str,
    entry: str = "main",
) -> BackendParityMatrix:
    if not isinstance(registry, BackendRegistry):
        raise BackendParityError("parity requires a BackendRegistry")
    if not isinstance(program, AssemblyProgram) or not program.functions:
        raise BackendParityError("parity requires a non-empty AssemblyProgram")
    if _SHA256.fullmatch(source_sha256) is None:
        raise BackendParityError("parity source identity must be a lowercase SHA-256")
    if not isinstance(entry, str) or not entry or not any(function.name == entry for function in program.functions):
        raise BackendParityError("parity entry function is not present")
    try:
        hosted = registry.get_hosted_execution("hosted-emulator")
    except BackendRegistryError as error:
        raise BackendParityError("parity requires the canonical hosted emulator") from error
    hosted_result = hosted.execute(program, entry)
    evidence: list[BackendParityEvidence] = []
    for target in sorted(PARITY_TARGETS, key=lambda item: item.name):
        if target.name not in registry.target_catalog.names:
            raise BackendParityError(f"parity target {target.name!r} is not registered")
        try:
            provider = registry.get_native_assembly(target.name)
        except BackendRegistryError as error:
            raise BackendParityError(f"parity target {target.name!r} has no native provider") from error
        text = provider.generate(program)
        _validate_target_text(target, text, entry)
        instruction_count = sum(1 for line in text.splitlines() if line.startswith("    "))
        if not 1 <= instruction_count <= MAX_PARITY_INSTRUCTIONS:
            raise BackendParityError(f"target {target.name!r} emitted an invalid instruction count")
        evidence.append(
            BackendParityEvidence(
                target,
                source_sha256,
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
                instruction_count,
                hosted_result,
            )
        )
    matrix = BackendParityMatrix(source_sha256, hosted_result, tuple(evidence))
    validate_backend_parity(matrix)
    return matrix


def validate_backend_parity(matrix: BackendParityMatrix) -> None:
    if not isinstance(matrix, BackendParityMatrix) or _SHA256.fullmatch(matrix.source_sha256) is None:
        raise BackendParityError("parity matrix source identity is invalid")
    if matrix.target_names != tuple(sorted(target.name for target in PARITY_TARGETS)):
        raise BackendParityError("parity matrix does not cover the exact registered target set")
    seen: set[str] = set()
    for item in matrix.targets:
        if item.target.name in seen or item.source_sha256 != matrix.source_sha256:
            raise BackendParityError("parity target identities are inconsistent")
        seen.add(item.target.name)
        if _SHA256.fullmatch(item.assembly_sha256) is None:
            raise BackendParityError("parity assembly identity is invalid")
        if item.native_status != "STRUCTURAL_ONLY_TOOLCHAIN_DEFERRED":
            raise BackendParityError("unbound native parity status is not allowed")
        if isinstance(item.hosted_result, float) and not math.isfinite(item.hosted_result):
            raise BackendParityError("parity semantic result is not finite")
    if tuple(sorted(seen)) != tuple(sorted(target.name for target in PARITY_TARGETS)):
        raise BackendParityError("parity matrix target coverage is incomplete")


def _validate_target_text(target: TargetSpec, text: str, entry: str) -> None:
    if not isinstance(text, str) or not text.strip():
        raise BackendParityError(f"target {target.name!r} emitted empty assembly")
    labels = {line.strip() for line in text.splitlines() if line.strip().endswith(":")}
    if target.name == "linux-x86_64":
        required = (".intel_syntax noprefix",)
        required_labels = (f"s3_{entry}:",)
        forbidden = ("stp x29",)
        forbidden_labels = (f"_{entry}:",)
    elif target.name == "linux-aarch64":
        required = (".text", "x29")
        required_labels = (f"{entry}:",)
        forbidden = (".intel_syntax",)
        forbidden_labels = (f"s3_{entry}:", f"_{entry}:")
    elif target.name == "macos-arm64":
        required = (".text", "x29")
        required_labels = (f"_{entry}:",)
        forbidden = (".intel_syntax",)
        forbidden_labels = (f"s3_{entry}:",)
    else:
        raise BackendParityError(f"unsupported parity target {target.name!r}")
    if any(marker not in text for marker in required):
        raise BackendParityError(f"target {target.name!r} lacks its target-specific assembly identity")
    if any(label not in labels for label in required_labels):
        raise BackendParityError(f"target {target.name!r} lacks its target-specific symbol identity")
    if any(marker in text for marker in forbidden) or any(label in labels for label in forbidden_labels):
        raise BackendParityError(f"target {target.name!r} contains a different target's assembly identity")
