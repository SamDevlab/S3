"""Audit a Stage compiler ELF for the freestanding Pythonless sandbox gate.

This parser intentionally covers only the properties required by the strict
self-hosting proof. It does not execute the artifact and is not native compiler
evidence by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


ELF_MAGIC = b"\x7fELF"
ELFCLASS64 = 2
ELFDATA2LSB = 1
ET_EXEC = 2
EM_X86_64 = 62
PT_LOAD = 1
PT_DYNAMIC = 2
PT_INTERP = 3
PF_X = 1
PF_W = 2
ELF64_HEADER_SIZE = 64
ELF64_PROGRAM_HEADER_SIZE = 56


class ElfAuditError(ValueError):
    pass


def _u16(data: bytes, offset: int) -> int:
    return struct.unpack_from("<H", data, offset)[0]


def _u64(data: bytes, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def inspect_elf_bytes(data: bytes) -> dict[str, object]:
    if len(data) < ELF64_HEADER_SIZE:
        raise ElfAuditError("ELF file is smaller than the ELF64 header")
    if data[:4] != ELF_MAGIC:
        raise ElfAuditError("artifact does not have ELF magic")
    if data[4] != ELFCLASS64:
        raise ElfAuditError("artifact is not ELF64")
    if data[5] != ELFDATA2LSB:
        raise ElfAuditError("artifact is not little-endian ELF")
    if data[6] != 1:
        raise ElfAuditError("unsupported ELF identification version")

    elf_type = _u16(data, 16)
    machine = _u16(data, 18)
    entry = _u64(data, 24)
    phoff = _u64(data, 32)
    ehsize = _u16(data, 52)
    phentsize = _u16(data, 54)
    phnum = _u16(data, 56)

    if ehsize < ELF64_HEADER_SIZE:
        raise ElfAuditError("ELF header size is smaller than ELF64 minimum")
    if phnum and phentsize < ELF64_PROGRAM_HEADER_SIZE:
        raise ElfAuditError("program-header entry size is smaller than ELF64 minimum")
    if phnum:
        end = phoff + phentsize * phnum
        if phoff < ELF64_HEADER_SIZE or end > len(data):
            raise ElfAuditError("program-header table is outside artifact bytes")

    program_headers: list[dict[str, int]] = []
    for index in range(phnum):
        offset = phoff + index * phentsize
        p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_align = struct.unpack_from(
            "<IIQQQQQQ",
            data,
            offset,
        )
        if p_filesz and p_offset + p_filesz > len(data):
            raise ElfAuditError(f"program header {index} file range escapes artifact")
        if p_filesz > p_memsz:
            raise ElfAuditError(f"program header {index} filesz exceeds memsz")
        program_headers.append(
            {
                "index": index,
                "type": p_type,
                "flags": p_flags,
                "offset": p_offset,
                "vaddr": p_vaddr,
                "filesz": p_filesz,
                "memsz": p_memsz,
                "align": p_align,
            }
        )

    load_segments = [header for header in program_headers if header["type"] == PT_LOAD]
    executable_loads = [
        header for header in load_segments if int(header["flags"]) & PF_X
    ]
    wx_loads = [
        header
        for header in load_segments
        if int(header["flags"]) & PF_X and int(header["flags"]) & PF_W
    ]
    entry_in_executable_load = any(
        int(header["vaddr"]) <= entry < int(header["vaddr"]) + int(header["memsz"])
        for header in executable_loads
    )
    has_interp = any(header["type"] == PT_INTERP for header in program_headers)
    has_dynamic = any(header["type"] == PT_DYNAMIC for header in program_headers)

    guards = {
        "elf64": data[4] == ELFCLASS64,
        "little_endian": data[5] == ELFDATA2LSB,
        "et_exec": elf_type == ET_EXEC,
        "x86_64": machine == EM_X86_64,
        "program_headers_present": phnum > 0,
        "load_segment_present": bool(load_segments),
        "executable_load_present": bool(executable_loads),
        "entrypoint_in_executable_load": entry_in_executable_load,
        "no_pt_interp": not has_interp,
        "no_pt_dynamic": not has_dynamic,
        "no_writable_executable_load": not wx_loads,
    }
    passed = all(guards.values())
    return {
        "schema": "s3.selfhost.freestanding-elf-audit.v1",
        "status": "PASS_FREESTANDING_STATIC_ELF" if passed else "FAIL_FREESTANDING_STATIC_ELF",
        "native_execution_evidence": False,
        "elf": {
            "type": elf_type,
            "machine": machine,
            "entry": entry,
            "program_header_offset": phoff,
            "program_header_entry_size": phentsize,
            "program_header_count": phnum,
            "program_headers": program_headers,
            "load_segment_count": len(load_segments),
            "executable_load_count": len(executable_loads),
            "writable_executable_load_count": len(wx_loads),
            "pt_interp_present": has_interp,
            "pt_dynamic_present": has_dynamic,
        },
        "guards": guards,
        "qualification": {
            "landlock_replay_allowed": passed,
            "full_self_hosting": False,
            "next": "LANDLOCK_SANDBOX_REPLAY" if passed else "REBUILD_STAGE_ARTIFACT_FREESTANDING_STATIC",
        },
    }


def audit_path(path: Path) -> dict[str, object]:
    resolved = path.resolve()
    data = resolved.read_bytes()
    result = inspect_elf_bytes(data)
    result["artifact"] = {
        "path": str(resolved),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    try:
        result = audit_path(args.artifact)
    except (OSError, ElfAuditError) as error:
        parser.exit(2, f"freestanding ELF audit blocked: {error}\n")
    if args.report is not None:
        destination = args.report.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"SHA256={result['artifact']['sha256']}")
    print(f"PT_INTERP={result['elf']['pt_interp_present']}")
    print(f"PT_DYNAMIC={result['elf']['pt_dynamic_present']}")
    print(f"WX_LOADS={result['elf']['writable_executable_load_count']}")
    print("NATIVE_EXECUTION_EVIDENCE=False")
    print(f"NEXT={result['qualification']['next']}")
    return 0 if result["status"] == "PASS_FREESTANDING_STATIC_ELF" else 2


if __name__ == "__main__":
    raise SystemExit(main())
