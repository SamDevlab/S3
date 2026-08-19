from __future__ import annotations

import struct

import pytest

from bootstrap.s3.backends.macos_arm64 import (
    ARM64_CPU_TYPE,
    MACHO64_MAGIC,
    ExecutionCertification,
    MachOBackend,
    MachOBackendError,
)
from bootstrap.s3.targets import MACOS_ARM64_TARGET, apple_arm64_target_catalog, cross_platform_target_catalog


pytestmark = pytest.mark.s3_contract


def test_macos_arm64_target_is_registered() -> None:
    assert MACOS_ARM64_TARGET.name == "macos-arm64"
    assert apple_arm64_target_catalog().names == ("macos-arm64",)
    assert "macos-arm64" in cross_platform_target_catalog().names


def test_macho_header_and_aapcs64_emission_are_deterministic() -> None:
    backend = MachOBackend()
    header = backend.header()
    assert struct.unpack_from("<I", header.bytes, 0)[0] == MACHO64_MAGIC
    assert struct.unpack_from("<i", header.bytes, 4)[0] == ARM64_CPU_TYPE
    assert backend.abi_call(2).location(0) == "x0"
    assert backend.emit_return(4).text.endswith("ret\n")
    assert backend.execution_status() is ExecutionCertification.DEFERRED


def test_macho_rejects_non_executable_header_contract() -> None:
    with pytest.raises(MachOBackendError):
        backend = MachOBackend()
        backend.header(cpu_subtype=-1)
