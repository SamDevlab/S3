from __future__ import annotations

import platform
import shutil
import struct
from pathlib import Path

import pytest

from tools.s3_native_observatory import (
    _add_dwarf_line_locations,
    _elf_sections,
    _parse_disassembly,
    _text_byte_attribution,
    _text_payload,
    analyze,
)


def test_debug_line_locations_preserve_original_instruction_text() -> None:
    assembly = ".text\n.globl main\nmain:\n  mov $1, %rax\n  ret\n"
    observed = _add_dwarf_line_locations(assembly)

    assert observed.splitlines() == [
        '.file 1 "s3-native-observatory.s"',
        ".text",
        ".globl main",
        "main:",
        ".loc 1 4 0",
        "  mov $1, %rax",
        ".loc 1 5 0",
        "  ret",
    ]


def test_elf_parser_rejects_non_elf_and_truncated_section_tables() -> None:
    with pytest.raises(ValueError, match="not an ELF"):
        _elf_sections(b"not an ELF")

    truncated = bytearray(64)
    truncated[:4] = b"\x7fELF"
    truncated[4:6] = b"\x02\x01"
    struct.pack_into("<HH", truncated, 16, 1, 62)
    struct.pack_into("<Q", truncated, 40, 64)
    struct.pack_into("<HHH", truncated, 58, 64, 1, 0)
    with pytest.raises(ValueError, match="section table exceeds"):
        _elf_sections(bytes(truncated))


def test_text_section_extraction_rejects_missing_and_non_file_backed_text() -> None:
    with pytest.raises(ValueError, match="no file-backed .text"):
        _text_payload(b"", ())
    with pytest.raises(ValueError, match="no file-backed .text"):
        _text_payload(b"", ({"name": ".text", "type": 8, "offset": 0, "size": 4},))


def test_text_byte_accounting_keeps_unmapped_and_undecoded_bytes_separate() -> None:
    result = _text_byte_attribution(
        [
            {"address": 0, "instruction_size_bytes": 2, "origin_status": "MAPPED"},
            {"address": 3, "instruction_size_bytes": 1, "origin_status": "UNMAPPED"},
        ],
        5,
        0,
    )
    assert result == {
        "text_section_bytes": 5,
        "decoded_instruction_text_bytes": 3,
        "attributed_text_bytes": 2,
        "unmapped_text_bytes": 1,
        "undecoded_text_bytes": 2,
    }


def test_text_byte_accounting_rejects_overlapping_instruction_ranges() -> None:
    with pytest.raises(ValueError, match="overlap"):
        _text_byte_attribution(
            [
                {"address": 0, "instruction_size_bytes": 2, "origin_status": "MAPPED"},
                {"address": 1, "instruction_size_bytes": 1, "origin_status": "UNMAPPED"},
            ],
            2,
            0,
        )


def test_disassembly_keeps_instructions_without_exact_origin_unmapped() -> None:
    instructions, per_function = _parse_disassembly(
        "0000000000000000 <s3_user_fn_0>:\n"
        "   0: 48 89 d8 mov rax, rbx\n"
        "   3: c3 ret\n"
        "0000000000000004 <__s3_runtime_helper>:\n"
        "   4: c3 ret\n"
        "0000000000000005 <_start>:\n"
        "   5: c3 ret\n"
        "0000000000000006 <mystery_symbol>:\n"
        "   6: c3 ret\n",
        [],
        {},
        {"s3_user_fn_0": "user_fn"},
    )

    assert [item["origin_status"] for item in instructions] == ["UNMAPPED"] * 5
    assert [item["origin_category"] for item in instructions] == ["UNMAPPED"] * 5
    assert [item["unmapped_symbol_class"] for item in instructions] == [
        "SOURCE_FUNCTION_UNMAPPED",
        "SOURCE_FUNCTION_UNMAPPED",
        "S3_RUNTIME_HELPER_SYMBOL",
        "S3_ENTRY_STUB",
        "UNCLASSIFIED_SYMBOL",
    ]
    assert per_function["user_fn"]["instructions"] == 2
    assert per_function["user_fn"]["text_bytes"] == 4
    assert [row["instruction_size_bytes"] for row in instructions] == [3, 1, 1, 1, 1]


def test_debug_line_instrumentation_refuses_existing_location_directives() -> None:
    with pytest.raises(ValueError, match="already contains DWARF"):
        _add_dwarf_line_locations(".text\n.loc 1 1 0\n  ret\n")


@pytest.mark.skipif(
    platform.system() != "Linux"
    or platform.machine().lower() not in {"x86_64", "amd64"}
    or not all(shutil.which(name) for name in ("cc", "readelf", "objdump")),
    reason="native ELF observatory requires Linux x86-64 binutils",
)
def test_native_observatory_measures_real_elf_and_maps_machine_instructions(tmp_path: Path) -> None:
    source = Path(__file__).parents[1] / "examples/first.s3"
    report = analyze(source, tmp_path / "native-observatory", max_instructions=1000)

    assert report["object"]["format"] == "ELF64-REL-x86_64"
    assert report["object"]["text_identical_after_debug_instrumentation"] is True
    assert report["object"]["text_section_bytes"] > 0
    assert len(report["provenance"]["observatory_tool_sha256"]) == 64
    assert len(report["provenance"]["generated_assembly_sha256"]) == 64
    assert len(report["provenance"]["codegen_report_sha256"]) == 64
    assert report["toolchain"]["readelf_version"]
    assert report["summary"]["native_instruction_count"] > 0
    assert report["summary"]["attributed_native_instructions"] > 0
    assert report["summary"]["attributed_native_instructions"] + report["summary"]["unmapped_native_instructions"] == report["summary"]["native_instruction_count"]
    assert report["summary"]["attributed_text_bytes"] + report["summary"]["unmapped_text_bytes"] + report["summary"]["undecoded_text_bytes"] == report["object"]["text_section_bytes"]
