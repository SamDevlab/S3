from __future__ import annotations

from bootstrap.s3.arm64_integration import LinuxAArch64Integration, MacOSArm64Integration
from bootstrap.s3.release_candidate import CertificateStatus, LocalReleaseCandidateBuilder, ReleaseCandidateError


APACHE_FIXTURE = "Apache License\nVersion 2.0, January 2004\n"


def _build():
    linux = LinuxAArch64Integration().build_scalar_return(7)
    macos = MacOSArm64Integration().build_scalar_return(3)
    return LocalReleaseCandidateBuilder().build(
        version="1.90.0-rc1",
        compiler_commit="local-test-sha",
        source_files={"bootstrap/s3/module.py": b"module"},
        target_artifacts={
            "linux-aarch64": linux.container_header,
            "macos-arm64": macos.container_header,
        },
        native_status={
            "linux-aarch64": (CertificateStatus.DEFERRED_BY_ENVIRONMENT, "no Linux AArch64 host"),
            "macos-arm64": (CertificateStatus.DEFERRED_BY_ENVIRONMENT, "no Apple Silicon host"),
        },
        license_text=APACHE_FIXTURE,
    )


def test_release_candidate_is_deterministic_and_has_explicit_matrix() -> None:
    first = _build()
    second = _build()
    assert first.bundle_sha256 == second.bundle_sha256
    assert first.certificate_matrix_json == second.certificate_matrix_json
    assert all(item.structural is CertificateStatus.STRUCTURAL_PASS for item in first.certificates)
    assert {item.native for item in first.certificates} == {CertificateStatus.DEFERRED_BY_ENVIRONMENT}
    assert first.bundle.manifest["metadata"]["license"] == "Apache-2.0"


def test_release_candidate_rejects_fake_structural_artifacts() -> None:
    builder = LocalReleaseCandidateBuilder()
    try:
        builder.build(
            version="1.90.0-rc1",
            compiler_commit="sha",
            source_files={},
            target_artifacts={"linux-aarch64": b"elf"},
            native_status={},
            license_text=APACHE_FIXTURE,
        )
    except ReleaseCandidateError as error:
        assert "structural" in str(error)
    else:
        raise AssertionError("invalid target bytes must not receive structural PASS")


def test_release_candidate_requires_apache_license_text() -> None:
    linux = LinuxAArch64Integration().build_scalar_return(1)
    try:
        LocalReleaseCandidateBuilder().build(
            version="1.90.0-rc1",
            compiler_commit="sha",
            source_files={},
            target_artifacts={"linux-aarch64": linux.container_header},
            native_status={},
            license_text="S3 local release candidate; not published.\n",
        )
    except ReleaseCandidateError as error:
        assert "Apache-2.0" in str(error)
    else:
        raise AssertionError("release bundle must carry Apache-2.0 license text")


def test_release_candidate_is_local_only() -> None:
    candidate = _build()
    try:
        LocalReleaseCandidateBuilder().publish(candidate)
    except ReleaseCandidateError as error:
        assert "publication" in str(error)
    else:
        raise AssertionError("release candidate publication must be disabled")
