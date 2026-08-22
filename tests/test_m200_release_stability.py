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
COMMIT = "0123456789abcdef0123456789abcdef01234567"


class _FixtureVerifier:
    def verify(self, _public_key: bytes, _message: bytes, _signature: bytes) -> bool:
        return True


def _build_candidate(version: str = "2.0.0-rc1"):
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
        version=version,
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


def test_release_stability_rejects_unvetted_fixture_provenance() -> None:
    first = _build_candidate()
    second = _build_candidate()
    with pytest.raises(ReleaseStabilityError, match="not vetted"):
        evaluate_release_stability(
            first,
            repeat_bundle_sha256=second.bundle.sha256,
            provenance=_provenance(first),
            signature_service=_service(),
            compatibility_scope=("linux-aarch64", "linux-x86_64", "macos-arm64"),
        )


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


def test_release_stability_validates_policy_before_provider_availability() -> None:
    candidate = _build_candidate()
    provenance = _provenance(candidate)
    unknown_key = type(provenance)(
        provenance.name,
        provenance.version,
        provenance.digest,
        provenance.publisher,
        "unknown-key",
        provenance.signature,
        provenance.provenance,
        provenance.source,
    )
    with pytest.raises(ReleaseStabilityError, match="policy failed"):
        evaluate_release_stability(
            candidate,
            repeat_bundle_sha256=candidate.bundle.sha256,
            provenance=unknown_key,
            signature_service=_service(),
            compatibility_scope=("linux-aarch64", "linux-x86_64", "macos-arm64"),
        )


def test_release_stability_requires_provenance_commit_binding() -> None:
    candidate = _build_candidate()
    provenance = _provenance(candidate)
    broken = type(provenance)(
        provenance.name,
        provenance.version,
        provenance.digest,
        provenance.publisher,
        provenance.key_id,
        provenance.signature,
        (("compiler_commit", "f" * 40),),
        provenance.source,
    )
    with pytest.raises(ReleaseStabilityError, match="compiler commit"):
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


@pytest.mark.parametrize("commit", ("a" * 39, "a" * 41, "A" * 40, "g" * 40))
def test_release_stability_rejects_noncanonical_git_commit_width_or_characters(commit: str) -> None:
    candidate = _build_candidate()
    broken = type(candidate)(candidate.version, commit, candidate.bundle, candidate.certificates)
    with pytest.raises(ReleaseStabilityError, match="exact lowercase Git"):
        evaluate_release_stability(
            broken,
            repeat_bundle_sha256=candidate.bundle.sha256,
            provenance=_provenance(candidate),
            signature_service=_service(),
            compatibility_scope=("linux-aarch64", "linux-x86_64", "macos-arm64"),
        )


def test_release_stability_accepts_the_canonical_s3_one_point_zero_rc_label() -> None:
    candidate = _build_candidate("1.0.0-rc1")
    provenance = type(_provenance(candidate))(
        "s3-toolchain-release-candidate",
        candidate.version,
        candidate.bundle.sha256,
        "SamDevlab",
        "release-key",
        b"fixture-signature",
        (("compiler_commit", candidate.compiler_commit), ("campaign", "m231-m240")),
    )
    with pytest.raises(ReleaseStabilityError, match="not vetted"):
        evaluate_release_stability(
            candidate,
            repeat_bundle_sha256=candidate.bundle.sha256,
            provenance=provenance,
            signature_service=_service(),
            compatibility_scope=("linux-aarch64", "linux-x86_64", "macos-arm64"),
        )
