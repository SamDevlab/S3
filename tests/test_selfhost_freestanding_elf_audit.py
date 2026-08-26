from __future__ import annotations

import struct

import pytest

from tools.audit_selfhost_freestanding_elf import (
    ELFDATA2LSB,
    ELFCLASS64,
    ELF64_HEADER_SIZE,
    ELF64_PROGRAM_HEADER_SIZE,
    EM_X86_64,
    ET_EXEC,
    PF_W,
    PF_X,
    PT_DYNAMIC,
    PT_INTERP,
    PT_LOAD,
    ElfAuditError,
    inspect_elf_bytes,
)


pytestmark = pytest.mark.s3_fast


def _elf64(*, interp: bool = False, dynamic: bool = False, wx: bool = False, etype: int = ET_EXEC) -> bytes:
    size = 4096
    data = bytearray(size)
    data[:4] = b"\x7fELF"
    data[4] = ELFCLASS64
    data[5] = ELFDATA2LSB
    data[6] = 1
    data[7] = 0

    headers: list[tuple[int, int, int, int, int, int, int, int]] = []
    load_flags = 4 | PF_X | (PF_W if wx else 0)
    headers.append((PT_LOAD, load_flags, 0, 0x400000, 0x400000, size, size, 0x1000))
    if interp:
        payload = b"/lib64/ld-linux-x86-64.so.2\x00"
        data[0x300 : 0x300 + len(payload)] = payload
        headers.append((PT_INTERP, 4, 0x300, 0x400300, 0x400300, len(payload), len(payload), 1))
    if dynamic:
        headers.append((PT_DYNAMIC, 6, 0x380, 0x400380, 0x400380, 32, 32, 8))

    phoff = ELF64_HEADER_SIZE
    phnum = len(headers)
    struct.pack_into("<H", data, 16, etype)
    struct.pack_into("<H", data, 18, EM_X86_64)
    struct.pack_into("<I", data, 20, 1)
    struct.pack_into("<Q", data, 24, 0x400100)
    struct.pack_into("<Q", data, 32, phoff)
    struct.pack_into("<Q", data, 40, 0)
    struct.pack_into("<I", data, 48, 0)
    struct.pack_into("<H", data, 52, ELF64_HEADER_SIZE)
    struct.pack_into("<H", data, 54, ELF64_PROGRAM_HEADER_SIZE)
    struct.pack_into("<H", data, 56, phnum)
    struct.pack_into("<H", data, 58, 0)
    struct.pack_into("<H", data, 60, 0)
    struct.pack_into("<H", data, 62, 0)
    for index, header in enumerate(headers):
        struct.pack_into(
            "<IIQQQQQQ",
            data,
            phoff + index * ELF64_PROGRAM_HEADER_SIZE,
            *header,
        )
    return bytes(data)


def test_minimal_static_exec_passes_freestanding_gate() -> None:
    result = inspect_elf_bytes(_elf64())
    assert result["status"] == "PASS_FREESTANDING_STATIC_ELF"
    assert result["guards"]["no_pt_interp"] is True
    assert result["guards"]["no_pt_dynamic"] is True
    assert result["guards"]["entrypoint_in_executable_load"] is True
    assert result["guards"]["no_writable_executable_load"] is True
    assert result["qualification"]["landlock_replay_allowed"] is True


@pytest.mark.parametrize(
    "kwargs, guard",
    [
        ({"interp": True}, "no_pt_interp"),
        ({"dynamic": True}, "no_pt_dynamic"),
        ({"wx": True}, "no_writable_executable_load"),
        ({"etype": 3}, "et_exec"),
    ],
)
def test_dynamic_pie_or_wx_artifacts_fail_closed(kwargs: dict[str, object], guard: str) -> None:
    result = inspect_elf_bytes(_elf64(**kwargs))
    assert result["status"] == "FAIL_FREESTANDING_STATIC_ELF"
    assert result["guards"][guard] is False
    assert result["qualification"]["landlock_replay_allowed"] is False


def test_non_elf_or_truncated_elf_is_rejected() -> None:
    with pytest.raises(ElfAuditError, match="smaller"):
        inspect_elf_bytes(b"x")
    bad = bytearray(64)
    bad[:4] = b"NOPE"
    with pytest.raises(ElfAuditError, match="magic"):
        inspect_elf_bytes(bytes(bad))


def test_program_header_outside_file_is_rejected() -> None:
    data = bytearray(_elf64())
    struct.pack_into("<Q", data, 32, len(data) - 8)
    with pytest.raises(ElfAuditError, match="outside"):
        inspect_elf_bytes(bytes(data))
