"""Local cross-platform release candidate and certification matrix for M1.90."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json

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
        license_text: str = "S3 local release candidate; not published.\n",
    ) -> ReleaseCandidate:
        if not version or not compiler_commit:
            raise ReleaseCandidateError("version and compiler commit are required")
        if not isinstance(source_files, dict) or not isinstance(target_artifacts, dict):
            raise ReleaseCandidateError("candidate inputs must be mappings")
        files = dict(source_files)
        certificates: list[TargetCertificate] = []
        for target in sorted(target_artifacts):
            artifact = target_artifacts[target]
            if not isinstance(target, str) or not target or not isinstance(artifact, bytes):
                raise ReleaseCandidateError("target artifact identity is invalid")
            path = f"targets/{target}/artifact.bin"
            files[path] = artifact
            native, reason = native_status.get(target, (CertificateStatus.NOT_ATTEMPTED, "native evidence was not supplied"))
            certificates.append(TargetCertificate(target, hashlib.sha256(artifact).hexdigest(), CertificateStatus.STRUCTURAL_PASS, native, reason))
        bundle = self.bundler.build(files, license_text=license_text, metadata={"compiler_commit": compiler_commit, "version": version})
        return ReleaseCandidate(version, compiler_commit, bundle, tuple(certificates))

    def publish(self, _candidate: ReleaseCandidate) -> None:
        raise ReleaseCandidateError("release candidate builder is local-only; publication is disabled")
