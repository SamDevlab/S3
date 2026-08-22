"""M2.00 reproducible release-candidate stability gate."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re

from .package_signatures import PackageSignatureEnvelope, PackageSignatureService
from .release_candidate import CertificateStatus, ReleaseCandidate


RELEASE_TARGETS = ("linux-aarch64", "linux-x86_64", "macos-arm64")
_COMMIT = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
# M1.90 used the historical 2.0.0-rc label.  The canonical S3 1.0 RC uses
# 1.0.0-rc; retaining both forms keeps old evidence readable without allowing
# arbitrary release versions through the stability gate.
_VERSION = re.compile(r"^(?:1|2)\.0\.0-rc[0-9]+$")


class ReleaseStabilityError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ReleaseStabilityEvidence:
    version: str
    compiler_commit: str
    bundle_sha256: str
    certificate_matrix_sha256: str
    target_names: tuple[str, ...]
    license_bound: bool
    reproducible: bool
    provenance_verified: bool
    provenance_provider: str
    provenance_status: str
    native_deferred_targets: tuple[str, ...]
    status: str
    provenance_policy_status: str = "POLICY_PASS"
    provenance_signature_status: str = "DEFERRED_BY_ENVIRONMENT"

    @property
    def json(self) -> str:
        return json.dumps(
            {
                "bundle_sha256": self.bundle_sha256,
                "certificate_matrix_sha256": self.certificate_matrix_sha256,
                "compiler_commit": self.compiler_commit,
                "license_bound": self.license_bound,
                "native_deferred_targets": list(self.native_deferred_targets),
                "provenance_verified": self.provenance_verified,
                "provenance_provider": self.provenance_provider,
                "provenance_policy_status": self.provenance_policy_status,
                "provenance_signature_status": self.provenance_signature_status,
                "provenance_status": self.provenance_status,
                "reproducible": self.reproducible,
                "status": self.status,
                "target_names": list(self.target_names),
                "version": self.version,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"


def evaluate_release_stability(
    candidate: ReleaseCandidate,
    *,
    repeat_bundle_sha256: str,
    provenance: PackageSignatureEnvelope,
    signature_service: PackageSignatureService,
    compatibility_scope: tuple[str, ...],
) -> ReleaseStabilityEvidence:
    if not isinstance(candidate, ReleaseCandidate):
        raise ReleaseStabilityError("release stability requires a ReleaseCandidate")
    if _VERSION.fullmatch(candidate.version) is None:
        raise ReleaseStabilityError("candidate version must be an S3 1.0.0 or historical 2.0.0 release candidate")
    if _COMMIT.fullmatch(candidate.compiler_commit) is None:
        raise ReleaseStabilityError("candidate compiler commit must be an exact lowercase Git SHA-1 or SHA-256")
    if tuple(sorted(compatibility_scope)) != tuple(sorted(RELEASE_TARGETS)):
        raise ReleaseStabilityError("compatibility scope must cover the exact release target matrix")
    target_names = tuple(item.target for item in candidate.certificates)
    if target_names != RELEASE_TARGETS:
        raise ReleaseStabilityError("candidate certificates do not cover the exact release target matrix")
    if any(item.structural is not CertificateStatus.STRUCTURAL_PASS for item in candidate.certificates):
        raise ReleaseStabilityError("release candidate has a non-structural target certificate")
    deferred = tuple(
        item.target
        for item in candidate.certificates
        if item.native is CertificateStatus.DEFERRED_BY_ENVIRONMENT
    )
    if any(item.native is CertificateStatus.NOT_ATTEMPTED for item in candidate.certificates):
        raise ReleaseStabilityError("release candidate has an unattempted native target")
    metadata = candidate.bundle.manifest.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("compiler_commit") != candidate.compiler_commit or metadata.get("version") != candidate.version or metadata.get("license") != "Apache-2.0":
        raise ReleaseStabilityError("bundle metadata is not bound to the candidate identity")
    license_bound = candidate.bundle.manifest.get("license") == "LICENSE" and isinstance(candidate.bundle.manifest.get("license_sha256"), str)
    if not license_bound:
        raise ReleaseStabilityError("release bundle has no bound LICENSE")
    if repeat_bundle_sha256 != candidate.bundle.sha256:
        raise ReleaseStabilityError("repeated release bundle is not byte-identical")
    if provenance.digest != candidate.bundle.sha256 or provenance.version != candidate.version or provenance.name != "s3-toolchain-release-candidate":
        raise ReleaseStabilityError("provenance envelope is not bound to this candidate")
    policy = signature_service.validate_policy(provenance, candidate.bundle.data)
    if policy.is_err:
        error = policy.error_or(None)
        raise ReleaseStabilityError(f"release provenance policy failed: {error.detail if error is not None else 'unknown policy error'}")
    provenance_metadata = dict(provenance.provenance)
    if provenance_metadata.get("compiler_commit") != candidate.compiler_commit:
        raise ReleaseStabilityError("release provenance compiler commit is not bound to this candidate")
    if not signature_service.provider_is_vetted:
        raise ReleaseStabilityError("release provenance provider is not vetted")
    if not signature_service.provider_is_available:
        provenance_verified = False
        provenance_status = "DEFERRED_PROVIDER_UNAVAILABLE"
    else:
        verified = signature_service.verify(provenance, candidate.bundle.data)
        if not verified.is_ok:
            raise ReleaseStabilityError("release provenance verification failed")
        provenance_verified = True
        provenance_status = "VERIFIED"
    matrix_sha = hashlib.sha256(candidate.certificate_matrix_json.encode("utf-8")).hexdigest()
    status = "READY_WITH_DEFERRED_NATIVE_TARGETS" if deferred and provenance_verified else ("READY_WITH_DEFERRED_NATIVE_AND_PROVENANCE" if deferred else ("READY_WITH_DEFERRED_PROVENANCE" if not provenance_verified else "COMPLETE"))
    return ReleaseStabilityEvidence(
        candidate.version,
        candidate.compiler_commit,
        candidate.bundle.sha256,
        matrix_sha,
        target_names,
        True,
        True,
        provenance_verified,
        signature_service.provider_identity,
        provenance_status,
        deferred,
        status,
        "POLICY_PASS",
        provenance_status,
    )
