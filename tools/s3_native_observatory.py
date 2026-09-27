"""Experimental ELF object and native-instruction provenance report for S3."""

from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import platform
import re
import shutil
import struct
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bootstrap.s3.backends.x86_64 import (
    InstructionBudgetMode,
    NativeCodegenPolicy,
    generate_native_assembly,
)
from bootstrap.s3.codegen_report import build_codegen_report
from bootstrap.s3.backends.x86_64.emitter import X8664Emitter, function_symbol
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source
from tools.s3_source_identity import canonical_source_sha256


_ELF64_SECTION = struct.Struct("<IIQQQQIIQQ")
_ELF64_SYMBOL = struct.Struct("<IBBHQQ")
_MNEMONIC = re.compile(r"^([A-Za-z][A-Za-z0-9_.]*)(?:\s+(.*))?$")
_DISASSEMBLY_HEADER = re.compile(r"^\s*([0-9a-fA-F]+)\s+<([^>]+)>:$")
_DISASSEMBLY_INSTRUCTION = re.compile(
    r"^\s*([0-9a-fA-F]+):\s+((?:[0-9a-fA-F]{2}\s+)+)\s*"
    r"([A-Za-z][A-Za-z0-9_.]*)\s*(.*)$"
)
_DECODED_LINE = re.compile(r"^s3-native-observatory\.s\s+(\d+)\s+(0x[0-9a-fA-F]+)\b")


def _run(command: list[str], *, cwd: Path, timeout: float = 30.0) -> str:
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(f"command failed ({completed.returncode}): {command[0]}: {detail}")
    return completed.stdout


def _elf_sections(payload: bytes) -> tuple[dict[str, object], ...]:
    if len(payload) < 64 or payload[:4] != b"\x7fELF":
        raise ValueError("artifact is not an ELF file")
    if payload[4] != 2 or payload[5] != 1:
        raise ValueError("only ELF64 little-endian objects are supported")
    elf_type, machine = struct.unpack_from("<HH", payload, 16)
    if elf_type != 1 or machine != 62:
        raise ValueError("object must be ELF64 ET_REL for x86-64")
    section_offset = struct.unpack_from("<Q", payload, 40)[0]
    entry_size, section_count, names_index = struct.unpack_from("<HHH", payload, 58)
    if entry_size != _ELF64_SECTION.size or section_count == 0 or names_index >= section_count:
        raise ValueError("ELF section table is unsupported or incomplete")
    if section_offset + entry_size * section_count > len(payload):
        raise ValueError("ELF section table exceeds the object file")

    raw_sections = [
        _ELF64_SECTION.unpack_from(payload, section_offset + index * entry_size)
        for index in range(section_count)
    ]
    names_header = raw_sections[names_index]
    names_start, names_size = names_header[4], names_header[5]
    if names_start + names_size > len(payload):
        raise ValueError("ELF section-name table exceeds the object file")
    names = payload[names_start : names_start + names_size]
    sections: list[dict[str, object]] = []
    for index, raw in enumerate(raw_sections):
        name_index, section_type, flags, address, offset, size, link, info, alignment, entsize = raw
        if name_index >= len(names):
            raise ValueError("ELF section name is outside its string table")
        end = names.find(b"\0", name_index)
        if end < 0:
            raise ValueError("ELF section name is unterminated")
        name = names[name_index:end].decode("ascii", errors="strict")
        if section_type != 8 and offset + size > len(payload):
            raise ValueError(f"ELF section {name!r} exceeds the object file")
        sections.append(
            {
                "index": index,
                "name": name,
                "type": section_type,
                "flags": flags,
                "address": address,
                "offset": offset,
                "size": size,
                "link": link,
                "info": info,
                "alignment": alignment,
                "entry_size": entsize,
            }
        )
    return tuple(sections)


def _text_payload(payload: bytes, sections: tuple[dict[str, object], ...]) -> bytes:
    section = next((item for item in sections if item["name"] == ".text"), None)
    if section is None or section["type"] == 8:
        raise ValueError("ELF object has no file-backed .text section")
    start = int(section["offset"])
    return payload[start : start + int(section["size"])]


def _function_symbols(payload: bytes, sections: tuple[dict[str, object], ...]) -> list[dict[str, object]]:
    string_tables = {
        int(item["index"]): payload[int(item["offset"]) : int(item["offset"]) + int(item["size"])]
        for item in sections
        if item["type"] == 3
    }
    output: list[dict[str, object]] = []
    for table in sections:
        if table["type"] != 2:
            continue
        strings = string_tables.get(int(table["link"]))
        entry_size = int(table["entry_size"])
        if strings is None or entry_size < _ELF64_SYMBOL.size:
            raise ValueError("ELF symbol table has an invalid string table or entry size")
        start, size = int(table["offset"]), int(table["size"])
        for cursor in range(start, start + size, entry_size):
            if cursor + _ELF64_SYMBOL.size > start + size:
                raise ValueError("ELF symbol table ends with a partial entry")
            name_index, info, _other, section_index, value, symbol_size = _ELF64_SYMBOL.unpack_from(payload, cursor)
            if (info & 0x0F) != 2 or section_index == 0:
                continue
            if not any(int(item["index"]) == section_index and item["name"] == ".text" for item in sections):
                continue
            if name_index >= len(strings):
                raise ValueError("ELF function symbol name is outside its string table")
            end = strings.find(b"\0", name_index)
            if end < 0:
                raise ValueError("ELF function symbol name is unterminated")
            name = strings[name_index:end].decode("utf-8", errors="strict")
            output.append({"symbol": name, "address": value, "size": symbol_size})
    return sorted(output, key=lambda item: (int(item["address"]), str(item["symbol"])))


def _is_instruction(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith(("#", ";", ".")) or stripped.endswith(":"):
        return False
    return _MNEMONIC.fullmatch(stripped) is not None


def _add_dwarf_line_locations(assembly: str) -> str:
    lines = assembly.splitlines()
    if any(re.match(r"^\s*\.(?:file|loc)\s", line) for line in lines):
        raise ValueError("source assembly already contains DWARF line directives")
    output = ['.file 1 "s3-native-observatory.s"']
    for line_number, line in enumerate(lines, start=1):
        if _is_instruction(line):
            output.append(f".loc 1 {line_number} 0")
        output.append(line)
    return "\n".join(output) + "\n"


def _decoded_line_rows(text: str) -> list[tuple[int, int]]:
    rows: list[tuple[int, int]] = []
    for line in text.splitlines():
        match = _DECODED_LINE.match(line.strip())
        if match:
            rows.append((int(match.group(2), 16), int(match.group(1))))
    return sorted(rows)


def _instruction_category(mnemonic: str, operands: str) -> str:
    if mnemonic.startswith("j") or mnemonic in {"ret", "retq"}:
        return "CONTROL_FLOW"
    if mnemonic in {"call", "callq"}:
        return "CALL"
    if mnemonic in {"push", "pushq", "pop", "popq", "leave", "enter"}:
        return "STACK"
    if mnemonic.startswith(("mov", "xchg")):
        return "MOVE"
    if mnemonic in {"lea", "leaq"}:
        return "ADDRESSING"
    if "[" in operands:
        return "MEMORY_ACCESS"
    return "UNKNOWN"


def _parse_disassembly(
    text: str,
    line_rows: list[tuple[int, int]],
    line_origins: dict[int, dict[str, object]],
    symbol_names: dict[str, str],
) -> tuple[list[dict[str, object]], dict[str, Counter[str]]]:
    addresses = [item[0] for item in line_rows]
    instructions: list[dict[str, object]] = []
    counts_by_function: dict[str, Counter[str]] = defaultdict(Counter)
    current_symbol: str | None = None
    for line in text.splitlines():
        header = _DISASSEMBLY_HEADER.match(line)
        if header:
            current_symbol = header.group(2).split("+", 1)[0]
            continue
        match = _DISASSEMBLY_INSTRUCTION.match(line)
        if not match:
            continue
        address = int(match.group(1), 16)
        raw_bytes = match.group(2).split()
        mnemonic = match.group(3).lower()
        operands = match.group(4).strip()
        row_index = bisect.bisect_right(addresses, address) - 1
        source_line = line_rows[row_index][1] if row_index >= 0 else None
        origin = line_origins.get(source_line) if source_line is not None else None
        symbol_function = symbol_names.get(current_symbol or "")
        if origin is not None and origin.get("function") == symbol_function:
            status = "MAPPED"
            category = str(origin["assembly_origin_category"])
            unmapped_symbol_class = None
        else:
            status = "UNMAPPED"
            category = "UNMAPPED"
            if symbol_function is not None:
                unmapped_symbol_class = "SOURCE_FUNCTION_UNMAPPED"
            elif current_symbol == "_start":
                unmapped_symbol_class = "S3_ENTRY_STUB"
            elif current_symbol is not None and current_symbol.startswith("__s3_"):
                unmapped_symbol_class = "S3_RUNTIME_HELPER_SYMBOL"
            else:
                unmapped_symbol_class = "UNCLASSIFIED_SYMBOL"
        native_category = _instruction_category(mnemonic, operands)
        function = symbol_function or "UNMAPPED"
        counts = counts_by_function[function]
        counts["instructions"] += 1
        counts["text_bytes"] += len(raw_bytes)
        counts["memory_operand_instructions"] += int("[" in operands)
        counts["branches"] += int(mnemonic.startswith("j") or mnemonic in {"ret", "retq"})
        counts["calls"] += int(mnemonic in {"call", "callq"})
        counts[f"native_category:{native_category}"] += 1
        counts[f"origin_category:{category}"] += 1
        counts[f"origin_status:{status}"] += 1
        if unmapped_symbol_class is not None:
            counts[f"unmapped_symbol_class:{unmapped_symbol_class}"] += 1
        instructions.append(
            {
                "address": address,
                "address_hex": f"0x{address:x}",
                "instruction_size_bytes": len(raw_bytes),
                "encoding_bytes": " ".join(raw_bytes),
                "function_symbol": current_symbol,
                "function": function,
                "mnemonic": mnemonic,
                "operands": operands,
                "native_category": native_category,
                "origin_status": status,
                "origin_category": category,
                "unmapped_symbol_class": unmapped_symbol_class,
                "source_assembly_line": source_line,
                "assembly_block": origin.get("block") if status == "MAPPED" else None,
                "assembly_instruction_indexes": (
                    origin.get("assembly_instruction_indexes") if status == "MAPPED" else None
                ),
                "assembly_opcodes": origin.get("assembly_opcodes") if status == "MAPPED" else None,
            }
        )
    return instructions, counts_by_function


def _text_byte_attribution(
    instructions: list[dict[str, object]], text_size: int, text_address: int
) -> dict[str, int]:
    """Account for decoded .text instruction byte ranges without filling gaps."""
    covered = bytearray(text_size)
    attributed = 0
    unmapped = 0
    for instruction in instructions:
        start = int(instruction["address"]) - text_address
        end = start + int(instruction["instruction_size_bytes"])
        if start < 0 or end > text_size:
            raise ValueError("disassembled instruction bytes exceed the .text section")
        if any(covered[start:end]):
            raise ValueError("disassembled instruction byte ranges overlap")
        covered[start:end] = b"\x01" * (end - start)
        if instruction["origin_status"] == "MAPPED":
            attributed += end - start
        else:
            unmapped += end - start
    decoded = attributed + unmapped
    if decoded > text_size:
        raise ValueError("decoded instruction byte total exceeds .text size")
    return {
        "text_section_bytes": text_size,
        "decoded_instruction_text_bytes": decoded,
        "attributed_text_bytes": attributed,
        "unmapped_text_bytes": unmapped,
        "undecoded_text_bytes": text_size - decoded,
    }


def _line_origin_map(report: dict[str, Any]) -> dict[int, dict[str, object]]:
    output: dict[int, dict[str, object]] = {}
    for function in report["functions"]:
        for block in function["blocks"]:
            for span in block["assembly_to_native_origin_spans"]:
                line_range = span.get("native_assembly_line_range")
                if span.get("mapping_status") != "MAPPED" or not isinstance(line_range, list):
                    continue
                for line_number in range(int(line_range[0]), int(line_range[1]) + 1):
                    if line_number in output:
                        raise ValueError("codegen report has overlapping assembly-origin line ranges")
                    output[line_number] = span
    return output


def _git_value(*args: str) -> str | None:
    try:
        return _run(["git", *args], cwd=ROOT).strip()
    except (OSError, RuntimeError, subprocess.TimeoutExpired):
        return None


def analyze(
    source_path: Path,
    output_dir: Path,
    *,
    optimization: str = "1",
    source_syntax: str = "0.6",
    max_frames: int = 64,
    max_instructions: int = 1_000_000,
) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("native observatory requires Linux x86-64")
    if source_syntax not in {"0.5", "0.6"}:
        raise ValueError("source syntax must be 0.5 or 0.6")
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    readelf = shutil.which("readelf")
    objdump = shutil.which("objdump")
    if not compiler or not readelf or not objdump:
        raise RuntimeError("native observatory requires a compiler, readelf, and objdump")
    if max_frames < 1 or max_instructions < 1:
        raise ValueError("resource limits must be positive")

    source_path = source_path.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    source_bytes = source_path.read_bytes()
    source = source_bytes.decode("utf-8")
    level = OptimizationLevel.parse(optimization)
    mode = SyntaxMode.V0_5 if source_syntax == "0.5" else SyntaxMode.V0_6
    compilation = compile_source(source, optimization=level, mode=mode)
    _ir, program = compilation.require_ordinary_artifacts()
    native_text = generate_native_assembly(
        program,
        max_frames=max_frames,
        max_instructions=max_instructions,
        native_policy=NativeCodegenPolicy.BASELINE,
    )
    emitter = X8664Emitter(
        program,
        max_frames=max_frames,
        max_instructions=max_instructions,
        register_allocation=True,
        instruction_budget_mode=InstructionBudgetMode.PER_INSTRUCTION,
    )
    mapped_text, native_origins = emitter.emit_with_origins()
    if mapped_text != native_text:
        raise RuntimeError("collecting native provenance changed emitted assembly")
    codegen = build_codegen_report(
        program,
        native_text,
        native_origins=native_origins,
        source_sha256=canonical_source_sha256(source_bytes),
        optimization=level.value,
        max_frames=max_frames,
        max_instructions=max_instructions,
    )

    plain_assembly = output_dir / "program.s"
    observed_assembly = output_dir / "program-observed.s"
    plain_object = output_dir / "program.o"
    observed_object = output_dir / "program-observed.o"
    plain_assembly.write_text(native_text, encoding="utf-8", newline="\n")
    observed_assembly.write_text(_add_dwarf_line_locations(native_text), encoding="utf-8", newline="\n")
    _run([compiler, "-x", "assembler", "-c", str(plain_assembly), "-o", str(plain_object)], cwd=output_dir)
    _run([compiler, "-g", "-x", "assembler", "-c", str(observed_assembly), "-o", str(observed_object)], cwd=output_dir)

    plain_bytes = plain_object.read_bytes()
    object_bytes = observed_object.read_bytes()
    sections = _elf_sections(object_bytes)
    plain_sections = _elf_sections(plain_bytes)
    text_bytes = _text_payload(object_bytes, sections)
    plain_text_bytes = _text_payload(plain_bytes, plain_sections)
    text_identical = text_bytes == plain_text_bytes
    if not text_identical:
        raise RuntimeError("DWARF line instrumentation changed .text bytes")
    functions = _function_symbols(object_bytes, sections)
    symbol_names = {function_symbol(function): function.name for function in program.functions if not function.external}
    line_rows = _decoded_line_rows(_run([objdump, "--dwarf=decodedline", str(observed_object)], cwd=output_dir))
    if not line_rows:
        raise RuntimeError("objdump produced no decoded DWARF line records")
    line_origins = _line_origin_map(codegen)
    disassembly = _run(
        [objdump, "-d", "-M", "intel", "--insn-width=16", "-j", ".text", str(observed_object)],
        cwd=output_dir,
    )
    native_instructions, per_function = _parse_disassembly(disassembly, line_rows, line_origins, symbol_names)
    if not native_instructions:
        raise RuntimeError("objdump produced no machine instructions for .text")

    text_section = next(item for item in sections if item["name"] == ".text")
    text_attribution = _text_byte_attribution(
        native_instructions,
        len(text_bytes),
        int(text_section["address"]),
    )

    categories = Counter(item["origin_category"] for item in native_instructions)
    unmapped_symbol_classes = Counter(
        item["unmapped_symbol_class"]
        for item in native_instructions
        if item["unmapped_symbol_class"] is not None
    )
    mapped_count = sum(item["origin_status"] == "MAPPED" for item in native_instructions)
    section_sizes = {
        str(item["name"]): int(item["size"])
        for item in sections
        if item["name"] in {".text", ".rodata", ".data", ".bss"}
    }
    readelf_header = _run([readelf, "-hW", str(observed_object)], cwd=output_dir)
    if not re.search(r"^\s*Class:\s+ELF64\s*$", readelf_header, re.MULTILINE) or not re.search(
        r"^\s*Machine:\s+Advanced Micro Devices X86-64\s*$", readelf_header, re.MULTILINE
    ):
        raise ValueError("readelf disagrees with parsed ELF64 x86-64 identity")
    compiler_version = _run([compiler, "--version"], cwd=output_dir).splitlines()[0]
    objdump_version = _run([objdump, "--version"], cwd=output_dir).splitlines()[0]
    readelf_version = _run([readelf, "--version"], cwd=output_dir).splitlines()[0]
    head = _git_value("rev-parse", "HEAD")
    tree = _git_value("rev-parse", "HEAD^{tree}")
    dirty_text = _git_value("status", "--porcelain")
    try:
        source_identity_path = source_path.relative_to(ROOT).as_posix()
    except ValueError:
        source_identity_path = str(source_path)
    codegen_bytes = json.dumps(codegen, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    report: dict[str, object] = {
        "schema_version": "1.1.0",
        "report_kind": "S3_X86_64_ELF_NATIVE_OBSERVATORY_EXPERIMENTAL",
        "provenance": {
            "git_head": head,
            "git_tree": tree,
            "git_worktree_dirty": bool(dirty_text) if dirty_text is not None else None,
            "source_path": source_identity_path,
            "source_sha256": canonical_source_sha256(source_bytes),
            "observatory_tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "generated_assembly_sha256": hashlib.sha256(native_text.encode("utf-8")).hexdigest(),
            "codegen_report_sha256": hashlib.sha256(codegen_bytes).hexdigest(),
        },
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python_version": sys.version.split()[0],
        },
        "configuration": {
            "target": "linux-x86_64",
            "optimization": level.value,
            "source_syntax": source_syntax,
            "register_allocation": True,
            "native_policy": "baseline",
            "instruction_budget_mode": "per-instruction",
            "max_frames": max_frames,
            "max_instructions": max_instructions,
            "plain_assembler_flags": ["-x", "assembler", "-c"],
            "observed_assembler_flags": ["-g", "-x", "assembler", "-c"],
        },
        "toolchain": {
            "compiler": compiler,
            "compiler_version": compiler_version,
            "readelf": readelf,
            "readelf_version": readelf_version,
            "objdump": objdump,
            "objdump_version": objdump_version,
        },
        "object": {
            "format": "ELF64-REL-x86_64",
            "elf_object_sha256": hashlib.sha256(object_bytes).hexdigest(),
            "plain_object_sha256": hashlib.sha256(plain_bytes).hexdigest(),
            "elf_object_bytes": len(object_bytes),
            "text_section_bytes": len(text_bytes),
            "text_section_sha256": hashlib.sha256(text_bytes).hexdigest(),
            "plain_text_section_sha256": hashlib.sha256(plain_text_bytes).hexdigest(),
            "text_identical_after_debug_instrumentation": text_identical,
            "section_sizes": dict(sorted(section_sizes.items())),
            "function_count": len(functions),
            "function_symbols": functions,
        },
        "summary": {
            "native_instruction_count": len(native_instructions),
            "native_memory_instruction_count": sum("[" in str(item["operands"]) for item in native_instructions),
            "native_branch_count": sum(str(item["mnemonic"]).startswith("j") or item["mnemonic"] in {"ret", "retq"} for item in native_instructions),
            "native_call_count": sum(item["mnemonic"] in {"call", "callq"} for item in native_instructions),
            "attributed_native_instructions": mapped_count,
            "unmapped_native_instructions": len(native_instructions) - mapped_count,
            "native_origin_attribution_fraction": round(mapped_count / len(native_instructions), 6),
            "attributed_text_bytes": text_attribution["attributed_text_bytes"],
            "unmapped_text_bytes": text_attribution["unmapped_text_bytes"],
            "undecoded_text_bytes": text_attribution["undecoded_text_bytes"],
            "decoded_instruction_text_bytes": text_attribution["decoded_instruction_text_bytes"],
            "origin_category_counts": dict(sorted(categories.items())),
            "unmapped_symbol_class_counts": dict(sorted(unmapped_symbol_classes.items())),
            "codegen_origin_mapped_instructions": codegen["summary"].get("native_origin_attributed_instructions"),
            "native_category_counts": dict(sorted(Counter(item["native_category"] for item in native_instructions).items())),
        },
        "functions": [
            {
                **item,
                "instruction_metrics": dict(sorted(per_function.get(str(item["name"]), Counter()).items())),
            }
            for item in codegen["functions"]
        ],
        "native_instructions": native_instructions,
        "origin_model": {
            "mapping": "GNU assembler DWARF line table from synthetic line locations on generated assembly instructions",
            "origin_source": "S3 Assembly operation and block sidecar",
            "unknown_policy": "instructions without an exact generated-line origin or matching function remain UNMAPPED",
            "text_byte_accounting": "raw objdump instruction encodings are attributed by instruction origin; undecoded .text gaps remain separate",
            "debug_instrumentation_changes_text": False,
            "dynamic_execution_counts": "NOT_MEASURED",
            "hardware_counters": "NOT_MEASURED",
        },
    }
    report_path = output_dir / "native-observatory-v1.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("-O", choices=("0", "1"), default="1")
    parser.add_argument("--source-syntax", choices=("0.5", "0.6"), default="0.6")
    parser.add_argument("--max-frames", type=int, default=64)
    parser.add_argument("--max-instructions", type=int, default=1_000_000)
    args = parser.parse_args()
    report = analyze(
        args.source,
        args.output_dir,
        optimization=args.O,
        source_syntax=args.source_syntax,
        max_frames=args.max_frames,
        max_instructions=args.max_instructions,
    )
    summary = report["summary"]
    obj = report["object"]
    print(
        "S3_NATIVE_OBSERVATORY=PASS "
        f"instructions={summary['native_instruction_count']} "
        f"text_bytes={obj['text_section_bytes']} "
        f"attributed={summary['attributed_native_instructions']} "
        f"unmapped={summary['unmapped_native_instructions']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
