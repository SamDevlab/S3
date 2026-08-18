from __future__ import annotations

import struct

import pytest

from bootstrap.s3.backends.aarch64 import (
    AARCH64_ELF_MACHINE,
    AAPCS64_ARGUMENT_REGISTERS,
    Aapcs64Call,
    AArch64Backend,
    AArch64BackendError,
    ExecutionCertification,
)
from bootstrap.s3.targets import LINUX_AARCH64_TARGET, arm64_target_catalog, cross_platform_target_catalog


pytestmark = pytest.mark.s3_contract


def test_linux_aarch64_target_is_registered_without_changing_builtin_default() -> None:
    assert LINUX_AARCH64_TARGET.name == "linux-aarch64"
    assert arm64_target_catalog().names == ("linux-aarch64",)
    assert "linux-aarch64" in cross_platform_target_catalog().names


def test_aapcs64_uses_x0_to_x7_then_aligned_stack_arguments() -> None:
    call = Aapcs64Call(10)
    assert tuple(call.location(index) for index in range(8)) == AAPCS64_ARGUMENT_REGISTERS
    assert call.location(8) == "[sp+0]"
    assert call.location(9) == "[sp+8]"
    assert call.return_register == "x0"


def test_aarch64_emission_and_elf_identity_are_deterministic() -> None:
    backend = AArch64Backend()
    first = backend.emit_return(7)
    second = backend.emit_return(7)
    assert first == second
    assert first.text == ".text\n    mov x0, #7\n    ret\n"
    header = backend.elf_header(entrypoint=0x1000)
    assert header.bytes[:4] == b"\x7fELF"
    assert struct.unpack_from("<H", header.bytes, 18)[0] == AARCH64_ELF_MACHINE
    assert backend.execution_status() is ExecutionCertification.DEFERRED


def test_aarch64_structural_contract_rejects_invalid_inputs() -> None:
    with pytest.raises(AArch64BackendError):
        Aapcs64Call(-1)
    with pytest.raises(AArch64BackendError):
        Aapcs64Call(1, return_register="x1")
    with pytest.raises(AArch64BackendError):
        AArch64Backend().emit_return(1 << 20)
