from __future__ import annotations

from hashlib import sha256

import pytest

from bootstrap.s3.aarch64_toolchain import create_cross_platform_backend_registry
from bootstrap.s3.arm64_integration import LinuxAArch64Integration, MacOSArm64Integration
from bootstrap.s3.package_signatures import (
    PackageSignatureEnvelope,
    PackageSignatureService,
    PublicTrustStore,
    TrustedPublicKey,
)
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.release_candidate import CertificateStatus, LocalReleaseCandidateBuilder
from bootstrap.s3.release_stability import ReleaseStabilityError, evaluate_release_stability


LICENSE = "Apache License\nVersion 2.0, January 2004\n"
COMMIT = "a" * 64


class _FixtureVerifier:
    def verify(self, _public_key: bytes, _message: bytes, _signature: bytes) -> bool:
        return True


def _build_candidate():
    source = "fn main() -> i64:\n    return 7\n"
    compilation = compile_source(source)
    registry = create_cross_platform_backend_registry()
    x86 = registry.get_native_assembly("linux-x86_64").generate(compilation.assembly).encode()
    linux = LinuxAArch64Integration().build_program(compilation.assembly).container_header
    macos = MacOSArm64Integration().build_program(compilation.assembly).container_header
    statuses = {
        target: (CertificateStatus.DEFERRED_BY_ENVIRONMENT, "native runner unavailable")
        for target in ("linux-aarch64", "linux-x86_64", "macos-arm64")
    }
    candidate = LocalReleaseCandidateBuilder().build(
        version="2.0.0-rc1",
        compiler_commit=COMMIT,
        source_files={"bootstrap/s3/compiler.py": source.encode()},
        target_artifacts={"linux-aarch64": linux, "linux-x86_64": x86, "macos-arm64": macos},
        native_status=statuses,
        license_text=LICENSE,
    )
    return candidate


def _service() -> PackageSignatureService:
    store = PublicTrustStore()
    assert store.add(TrustedPublicKey("release-key", "SamDevlab", b"public-key")).is_ok
    return PackageSignatureService(store, verifier=_FixtureVerifier())


def _provenance(candidate):
    return PackageSignatureEnvelope(
        name="s3-toolchain-release-candidate",
        version=candidate.version,
        digest=candidate.bundle.sha256,
        publisher="SamDevlab",
        key_id="release-key",
        signature=b"fixture-signature",
        provenance=(
            ("compiler_commit", candidate.compiler_commit),
            ("campaign", "m191-m200"),
        ),
    )


def test_release_stability_is_deterministic_and_explicitly_local() -> None:
    first = _build_candidate()
    second = _build_candidate()
    evidence = evaluate_release_stability(
        first,
        repeat_bundle_sha256=second.bundle.sha256,
        provenance=_provenance(first),
        signature_service=_service(),
        compatibility_scope=("linux-aarch64", "linux-x86_64", "macos-arm64"),
    )
    assert first.bundle_sha256 == second.bundle_sha256
    assert evidence.reproducible
    assert evidence.provenance_verified
    assert evidence.license_bound
    assert evidence.status == "READY_WITH_DEFERRED_NATIVE_TARGETS"
    assert evidence.native_deferred_targets == ("linux-aarch64", "linux-x86_64", "macos-arm64")


def test_release_stability_rejects_unbound_provenance() -> None:
    candidate = _build_candidate()
    provenance = _provenance(candidate)
    broken = type(provenance)(
        provenance.name,
        provenance.version,
        sha256(b"other").hexdigest(),
        provenance.publisher,
        provenance.key_id,
        provenance.signature,
        provenance.provenance,
        provenance.source,
    )
    with pytest.raises(ReleaseStabilityError, match="not bound"):
        evaluate_release_stability(
            candidate,
            repeat_bundle_sha256=candidate.bundle.sha256,
            provenance=broken,
            signature_service=_service(),
            compatibility_scope=("linux-aarch64", "linux-x86_64", "macos-arm64"),
        )


def test_release_stability_rejects_incomplete_target_matrix() -> None:
    candidate = _build_candidate()
    incomplete = type(candidate)(candidate.version, candidate.compiler_commit, candidate.bundle, candidate.certificates[:2])
    with pytest.raises(ReleaseStabilityError, match="exact release target matrix"):
        evaluate_release_stability(
            incomplete,
            repeat_bundle_sha256=candidate.bundle.sha256,
            provenance=_provenance(candidate),
            signature_service=_service(),
            compatibility_scope=("linux-aarch64", "linux-x86_64", "macos-arm64"),
        )
