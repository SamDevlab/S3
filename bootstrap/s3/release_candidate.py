"""Local cross-platform release candidate and certification matrix for M1.90."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import struct
from typing import Callable

from .backends.aarch64 import AARCH64_ELF_MACHINE
from .backends.macos_arm64 import ARM64_CPU_TYPE
from .toolchain_distribution import ToolchainBundle, ToolchainBundler


class ReleaseCandidateError(ValueError):
    pass


class CertificateStatus(Enum):
    STRUCTURAL_PASS = "structural_pass"
    NATIVE_PASS = "native_pass"
    DEFERRED_BY_ENVIRONMENT = "deferred_by_environment"
    NOT_ATTEMPTED = "not_attempted"


@dataclass(frozen=True, slots=True)
class TargetCertificate:
    target: str
    artifact_sha256: str
    structural: CertificateStatus
    native: CertificateStatus
    reason: str


@dataclass(frozen=True, slots=True)
class ReleaseCandidate:
    version: str
    compiler_commit: str
    bundle: ToolchainBundle
    certificates: tuple[TargetCertificate, ...]

    @property
    def bundle_sha256(self) -> str:
        return self.bundle.sha256

    @property
    def certificate_matrix_json(self) -> str:
        payload = {
            "compiler_commit": self.compiler_commit,
            "targets": [
                {
                    "artifact_sha256": item.artifact_sha256,
                    "native": item.native.value,
                    "reason": item.reason,
                    "structural": item.structural.value,
                    "target": item.target,
                }
                for item in self.certificates
            ],
            "version": self.version,
        }
        return json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"


StructuralValidator = Callable[[bytes], bool]


class LocalReleaseCandidateBuilder:
    def __init__(self, *, bundler: ToolchainBundler | None = None) -> None:
        self.bundler = bundler or ToolchainBundler()

    def build(
        self,
        *,
        version: str,
        compiler_commit: str,
        source_files: dict[str, bytes],
        target_artifacts: dict[str, bytes],
        native_status: dict[str, tuple[CertificateStatus, str]],
        license_text: str,
        structural_validators: dict[str, StructuralValidator] | None = None,
    ) -> ReleaseCandidate:
        if not version or not compiler_commit:
            raise ReleaseCandidateError("version and compiler commit are required")
        if not isinstance(source_files, dict) or not isinstance(target_artifacts, dict):
            raise ReleaseCandidateError("candidate inputs must be mappings")
        _require_apache_2_license(license_text)
        validators = {**_builtin_structural_validators(), **(structural_validators or {})}
        files = dict(source_files)
        certificates: list[TargetCertificate] = []
        for target in sorted(target_artifacts):
            artifact = target_artifacts[target]
            if not isinstance(target, str) or not target or not isinstance(artifact, bytes) or not artifact:
                raise ReleaseCandidateError("target artifact identity is invalid")
            validator = validators.get(target)
            if validator is None:
                raise ReleaseCandidateError(f"target {target!r} has no structural validator")
            try:
                structurally_valid = validator(artifact) is True
            except Exception as error:
                raise ReleaseCandidateError(f"target {target!r} structural validation failed") from error
            if not structurally_valid:
                raise ReleaseCandidateError(f"target {target!r} artifact failed structural validation")
            path = f"targets/{target}/artifact.bin"
            files[path] = artifact
            native, reason = native_status.get(target, (CertificateStatus.NOT_ATTEMPTED, "native evidence was not supplied"))
            if native is CertificateStatus.STRUCTURAL_PASS:
                raise ReleaseCandidateError("native certificate field cannot contain structural status")
            certificates.append(
                TargetCertificate(
                    target,
                    hashlib.sha256(artifact).hexdigest(),
                    CertificateStatus.STRUCTURAL_PASS,
                    native,
                    reason,
                )
            )
        bundle = self.bundler.build(
            files,
            license_text=license_text,
            metadata={"compiler_commit": compiler_commit, "license": "Apache-2.0", "version": version},
        )
        self.bundler.verify(bundle)
        return ReleaseCandidate(version, compiler_commit, bundle, tuple(certificates))

    def publish(self, _candidate: ReleaseCandidate) -> None:
        raise ReleaseCandidateError("release candidate builder is local-only; publication is disabled")


def _builtin_structural_validators() -> dict[str, StructuralValidator]:
    return {
        "linux-aarch64": _validate_linux_aarch64,
        "macos-arm64": _validate_macos_arm64,
    }


def _validate_linux_aarch64(artifact: bytes) -> bool:
    return (
        len(artifact) >= 64
        and artifact[:4] == b"\x7fELF"
        and artifact[4] == 2
        and artifact[5] == 1
        and struct.unpack_from("<H", artifact, 18)[0] == AARCH64_ELF_MACHINE
    )


def _validate_macos_arm64(artifact: bytes) -> bool:
    return (
        len(artifact) >= 32
        and struct.unpack_from("<I", artifact, 0)[0] == 0xFEEDFACF
        and struct.unpack_from("<i", artifact, 4)[0] == ARM64_CPU_TYPE
    )


def _require_apache_2_license(license_text: str) -> None:
    if not isinstance(license_text, str) or "Apache License" not in license_text or "Version 2.0" not in license_text:
        raise ReleaseCandidateError("release candidate requires the Apache-2.0 LICENSE text")
