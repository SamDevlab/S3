from __future__ import annotations

from bootstrap.s3.release_candidate import CertificateStatus, LocalReleaseCandidateBuilder, ReleaseCandidateError


def _build():
    return LocalReleaseCandidateBuilder().build(
        version="1.90.0-rc1",
        compiler_commit="local-test-sha",
        source_files={"bootstrap/s3/module.py": b"module"},
        target_artifacts={"linux-aarch64": b"elf", "macos-arm64": b"macho"},
        native_status={
            "linux-aarch64": (CertificateStatus.DEFERRED_BY_ENVIRONMENT, "no Linux AArch64 host"),
            "macos-arm64": (CertificateStatus.DEFERRED_BY_ENVIRONMENT, "no Apple Silicon host"),
        },
    )


def test_release_candidate_is_deterministic_and_has_explicit_matrix() -> None:
    first = _build()
    second = _build()
    assert first.bundle_sha256 == second.bundle_sha256
    assert first.certificate_matrix_json == second.certificate_matrix_json
    assert all(item.structural is CertificateStatus.STRUCTURAL_PASS for item in first.certificates)
    assert {item.native for item in first.certificates} == {CertificateStatus.DEFERRED_BY_ENVIRONMENT}


def test_release_candidate_is_local_only() -> None:
    candidate = _build()
    try:
        LocalReleaseCandidateBuilder().publish(candidate)
    except ReleaseCandidateError as error:
        assert "publication" in str(error)
    else:
        raise AssertionError("release candidate publication must be disabled")
