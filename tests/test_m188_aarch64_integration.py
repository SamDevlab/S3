from __future__ import annotations

import struct

from bootstrap.s3.arm64_integration import Arm64ExecutionStatus, LinuxAArch64Integration
from bootstrap.s3.arm64_integration import MacOSArm64Integration
from bootstrap.s3.backends.aarch64 import AARCH64_ELF_MACHINE
from bootstrap.s3.backends.macos_arm64 import ARM64_CPU_TYPE


def test_linux_aarch64_artifact_is_structurally_integrated_without_fake_execution() -> None:
    artifact = LinuxAArch64Integration().build_scalar_return(7)
    assert artifact.target.name == "linux-aarch64"
    assert artifact.assembly.instructions == ("mov x0, #7", "ret")
    assert struct.unpack_from("<H", artifact.container_header, 18)[0] == AARCH64_ELF_MACHINE
    assert artifact.structural_valid
    assert artifact.execution_status is Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT


def test_macos_arm64_artifact_uses_macho_identity_and_explicit_deferment() -> None:
    artifact = MacOSArm64Integration().build_scalar_return(3)
    assert artifact.target.name == "macos-arm64"
    assert struct.unpack_from("<I", artifact.container_header, 0)[0] == 0xFEEDFACF
    assert struct.unpack_from("<i", artifact.container_header, 4)[0] == ARM64_CPU_TYPE
    assert artifact.execution_status is Arm64ExecutionStatus.DEFERRED_BY_ENVIRONMENT


def test_native_certificate_requires_exact_result() -> None:
    integration = LinuxAArch64Integration()
    artifact = integration.build_scalar_return(11)
    certified = integration.certify_native_result(artifact, exit_code=0, observed_value=11, expected_value=11)
    assert certified.execution_status is Arm64ExecutionStatus.NATIVE_CERTIFIED
