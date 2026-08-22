from __future__ import annotations

import pytest

from bootstrap.s3.native_conformance import (
    ConformanceStatus,
    NativeConformanceError,
    NativeObservation,
    TargetExecutionType,
    classify_target_execution,
    compare_hosted_native,
    executable_digest,
)


def test_native_conformance_requires_exact_stdout_and_exit_match() -> None:
    observation = NativeObservation("return-7", "linux-x86_64", b"7\n", 0, TargetExecutionType.REAL_EXECUTION, b"7\n", 0, executable_sha256=executable_digest(b"elf"))
    result = compare_hosted_native(observation)
    assert result.status is ConformanceStatus.PASS
    assert "match" in result.reason

    mismatch = NativeObservation("return-7", "linux-x86_64", b"7\n", 0, TargetExecutionType.REAL_EXECUTION, b"8\n", 0)
    assert compare_hosted_native(mismatch).status is ConformanceStatus.MISMATCH


def test_structural_and_unavailable_targets_never_become_runtime_passes() -> None:
    structural = NativeObservation("return-7", "linux-aarch64", b"7\n", 0, TargetExecutionType.CROSS_COMPILE_ONLY, structural_valid=True)
    assert compare_hosted_native(structural).status is ConformanceStatus.STRUCTURAL_ONLY
    deferred = NativeObservation("return-7", "macos-arm64", b"7\n", 0, TargetExecutionType.UNAVAILABLE)
    assert compare_hosted_native(deferred).status is ConformanceStatus.DEFERRED_BY_ENVIRONMENT
    with pytest.raises(NativeConformanceError, match="runtime conformance"):
        compare_hosted_native(NativeObservation("return-7", "linux-x86_64", b"7\n", 0, TargetExecutionType.REAL_EXECUTION))


def test_target_classification_uses_environment_and_explicit_capabilities() -> None:
    assert classify_target_execution("linux-x86_64", system="Linux", machine="x86_64", executable_available=True) is TargetExecutionType.REAL_EXECUTION
    assert classify_target_execution("linux-aarch64", system="Linux", machine="x86_64", cross_compiler_available=True) is TargetExecutionType.CROSS_COMPILE_ONLY
    assert classify_target_execution("macos-arm64", system="Windows", machine="AMD64") is TargetExecutionType.UNAVAILABLE
