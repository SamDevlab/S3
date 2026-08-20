"""Bounded real ELF64 AArch64 object/link contracts for M1.97."""

from __future__ import annotations

from dataclasses import dataclass
import re
import struct
from typing import Iterable

from .aarch64_toolchain import AArch64NativeBuildPlan, AArch64Relocation
from .backends.aarch64 import AARCH64_ELF_MACHINE, ELF64_CLASS, ELF_LITTLE_ENDIAN


MAX_OBJECT_BYTES = 64 * 1024 * 1024
MAX_SYMBOLS = 100_000
MAX_RELOCATIONS = 100_000
SUPPORTED_RELOCATIONS = ("call26",)
_SYMBOL = re.compile(r"^[A-Za-z_.$][A-Za-z0-9_.$]*$")
_R_AARCH64_CALL26 = 283


class AArch64ObjectLinkError(ValueError):
    """Raised when an object/link contract cannot be validated."""


@dataclass(frozen=True, slots=True)
class AArch64ObjectSymbol:
    name: str
    defined: bool
    section: str | None
    offset: int


@dataclass(frozen=True, slots=True)
class AArch64ObjectArtifact:
    target: str
    format: str
    entry_symbol: str
    text: str
    symbols: tuple[AArch64ObjectSymbol, ...]
    relocations: tuple[AArch64Relocation, ...]
    bytes: bytes

    @property
    def structural_valid(self) -> bool:
        try:
            validate_object_artifact(self)
        except AArch64ObjectLinkError:
            return False
        return True


@dataclass(frozen=True, slots=True)
class AArch64LinkedArtifact:
    target: str
    format: str
    entry_symbol: str
    entrypoint: int
    resolved_symbols: tuple[str, ...]
    relocations_applied: tuple[AArch64Relocation, ...]
    bytes: bytes

    @property
    def structural_valid(self) -> bool:
        try:
            validate_linked_artifact(self)
        except AArch64ObjectLinkError:
            return False
        return True


class AArch64ObjectLinker:
    """Build deterministic ELF64 ET_REL and bounded ET_EXEC artifacts."""

    def __init__(self, *, max_object_bytes: int = MAX_OBJECT_BYTES, max_symbols: int = MAX_SYMBOLS, max_relocations: int = MAX_RELOCATIONS) -> None:
        _positive_limit(max_object_bytes, "max_object_bytes")
        _positive_limit(max_symbols, "max_symbols")
        _positive_limit(max_relocations, "max_relocations")
        self.max_object_bytes = max_object_bytes
        self.max_symbols = max_symbols
        self.max_relocations = max_relocations

    def build_object(self, plan: AArch64NativeBuildPlan) -> AArch64ObjectArtifact:
        _validate_plan(plan)
        for relocation in plan.relocations:
            _validate_relocation(relocation)
        text, offsets, relocation_offsets = _machine_text(plan)
        symbols = _symbols(plan, offsets)
        object_bytes = _build_elf(text, symbols, plan.relocations, relocation_offsets, file_type=1)
        artifact = AArch64ObjectArtifact(plan.target, "ELF64-REL-AARCH64", plan.entry_symbol, plan.assembly_text, symbols, plan.relocations, object_bytes)
        validate_object_artifact(artifact, max_object_bytes=self.max_object_bytes, max_symbols=self.max_symbols, max_relocations=self.max_relocations)
        return artifact

    def link(self, artifact: AArch64ObjectArtifact, *, resolved_symbols: Iterable[str] = ()) -> AArch64LinkedArtifact:
        validate_object_artifact(artifact, max_object_bytes=self.max_object_bytes, max_symbols=self.max_symbols, max_relocations=self.max_relocations)
        supplied = tuple(sorted(set(resolved_symbols)))
        if any(not _SYMBOL.fullmatch(symbol) for symbol in supplied):
            raise AArch64ObjectLinkError("resolved symbol name is invalid")
        undefined = {symbol.name for symbol in artifact.symbols if not symbol.defined}
        if not undefined.issubset(supplied):
            missing = ", ".join(sorted(undefined - set(supplied)))
            raise AArch64ObjectLinkError(f"unresolved AArch64 symbols: {missing}")
        entry = next(symbol for symbol in artifact.symbols if symbol.name == artifact.entry_symbol)
        entrypoint = 0x1000 + entry.offset
        resolved = tuple(sorted(set(supplied) | {symbol.name for symbol in artifact.symbols if symbol.defined}))
        linked_bytes = _build_elf(_extract_section(artifact.bytes, ".text"), artifact.symbols, (), {}, file_type=2, entrypoint=entrypoint)
        linked = AArch64LinkedArtifact(artifact.target, "ELF64-EXEC-AARCH64", artifact.entry_symbol, entrypoint, resolved, artifact.relocations, linked_bytes)
        validate_linked_artifact(linked, max_object_bytes=self.max_object_bytes)
        return linked


def _validate_plan(plan: AArch64NativeBuildPlan) -> None:
    if not isinstance(plan, AArch64NativeBuildPlan):
        raise AArch64ObjectLinkError("object build requires an AArch64 build plan")
    if plan.target != "linux-aarch64":
        raise AArch64ObjectLinkError("M1.97 object/link contract requires linux-aarch64")
    if not plan.structurally_complete:
        raise AArch64ObjectLinkError("AArch64 build plan is structurally incomplete")
    if not plan.defined_symbols or plan.entry_symbol not in plan.defined_symbols:
        raise AArch64ObjectLinkError("entry symbol is not defined by the object")


def validate_object_artifact(artifact: AArch64ObjectArtifact, *, max_object_bytes: int = MAX_OBJECT_BYTES, max_symbols: int = MAX_SYMBOLS, max_relocations: int = MAX_RELOCATIONS) -> None:
    if not isinstance(artifact, AArch64ObjectArtifact) or artifact.target != "linux-aarch64":
        raise AArch64ObjectLinkError("invalid Linux AArch64 object artifact")
    if artifact.format != "ELF64-REL-AARCH64" or not artifact.text:
        raise AArch64ObjectLinkError("object format or text section is invalid")
    _validate_header(artifact.bytes, file_type=1)
    if len(artifact.bytes) > max_object_bytes:
        raise AArch64ObjectLinkError("object artifact exceeds bounded size")
    if len(artifact.symbols) > max_symbols:
        raise AArch64ObjectLinkError("object symbol table exceeds bounded size")
    if len(artifact.relocations) > max_relocations:
        raise AArch64ObjectLinkError("object relocation table exceeds bounded size")
    required = {".text", ".rela.text", ".symtab", ".strtab", ".shstrtab"}
    if not required.issubset(_section_names(artifact.bytes)):
        raise AArch64ObjectLinkError("object ELF section table is incomplete")
    text = _extract_section(artifact.bytes, ".text")
    names = [symbol.name for symbol in artifact.symbols]
    if len(names) != len(set(names)) or artifact.entry_symbol not in names:
        raise AArch64ObjectLinkError("object symbols are not unique or entry is absent")
    for symbol in artifact.symbols:
        if not _SYMBOL.fullmatch(symbol.name) or symbol.offset < 0 or symbol.offset >= len(text) or symbol.offset % 4:
            raise AArch64ObjectLinkError("object symbol is invalid")
        if symbol.defined != (symbol.section == ".text"):
            raise AArch64ObjectLinkError("object symbol section does not match definition")
    for relocation in artifact.relocations:
        _validate_relocation(relocation)
        if relocation.symbol not in names:
            raise AArch64ObjectLinkError("relocation references an absent symbol")


def validate_linked_artifact(artifact: AArch64LinkedArtifact, *, max_object_bytes: int = MAX_OBJECT_BYTES) -> None:
    if not isinstance(artifact, AArch64LinkedArtifact) or artifact.target != "linux-aarch64":
        raise AArch64ObjectLinkError("invalid Linux AArch64 linked artifact")
    if artifact.format != "ELF64-EXEC-AARCH64" or artifact.entrypoint < 0x1000:
        raise AArch64ObjectLinkError("linked artifact format or entrypoint is invalid")
    _validate_header(artifact.bytes, file_type=2, entrypoint=artifact.entrypoint)
    if len(artifact.bytes) > max_object_bytes:
        raise AArch64ObjectLinkError("linked artifact exceeds bounded size")
    if not {".text", ".symtab", ".strtab", ".shstrtab"}.issubset(_section_names(artifact.bytes)):
        raise AArch64ObjectLinkError("linked ELF section table is incomplete")
    if not _SYMBOL.fullmatch(artifact.entry_symbol) or artifact.entry_symbol not in artifact.resolved_symbols:
        raise AArch64ObjectLinkError("linked entry symbol is invalid")
    for relocation in artifact.relocations_applied:
        _validate_relocation(relocation)


def _symbols(plan: AArch64NativeBuildPlan, offsets: dict[str, int]) -> tuple[AArch64ObjectSymbol, ...]:
    defined = tuple(AArch64ObjectSymbol(name, True, ".text", offsets.get(name, 0)) for name in plan.defined_symbols)
    defined_names = set(plan.defined_symbols)
    runtime = tuple(AArch64ObjectSymbol(name, False, None, 0) for name in plan.runtime_symbols if name not in defined_names)
    return tuple(sorted((*defined, *runtime), key=lambda symbol: symbol.name))


def _validate_relocation(relocation: AArch64Relocation) -> None:
    if not isinstance(relocation, AArch64Relocation) or relocation.kind not in SUPPORTED_RELOCATIONS:
        raise AArch64ObjectLinkError("unsupported AArch64 relocation")
    if not _SYMBOL.fullmatch(relocation.symbol) or relocation.offset < 0:
        raise AArch64ObjectLinkError("invalid AArch64 relocation")


def _machine_text(plan: AArch64NativeBuildPlan) -> tuple[bytes, dict[str, int], dict[int, int]]:
    nop = 0xD503201F
    call = 0x94000000
    data = bytearray()
    function_offsets: dict[str, int] = {}
    line_offsets: dict[int, int] = {}
    for line_index, raw in enumerate(plan.assembly_text.splitlines()):
        text = raw.strip()
        if not text or text == ".text" or text.startswith(".globl "):
            continue
        if text.endswith(":"):
            name = text[:-1]
            if name in plan.defined_symbols:
                function_offsets[name] = len(data)
            continue
        line_offsets[line_index] = len(data)
        data.extend(struct.pack("<I", call if text.startswith("bl ") else nop))
    if not data:
        raise AArch64ObjectLinkError("AArch64 plan has no encodable text")
    relocation_offsets: dict[int, int] = {}
    for relocation in plan.relocations:
        if relocation.offset not in line_offsets:
            raise AArch64ObjectLinkError("AArch64 relocation does not identify a text instruction")
        relocation_offsets[relocation.offset] = line_offsets[relocation.offset]
    return bytes(data), function_offsets, relocation_offsets


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def _build_elf(text: bytes, symbols: tuple[AArch64ObjectSymbol, ...], relocations: Iterable[AArch64Relocation], relocation_offsets: dict[int, int], *, file_type: int, entrypoint: int = 0) -> bytes:
    if not text or len(text) % 4:
        raise AArch64ObjectLinkError("ELF text must contain aligned AArch64 instructions")
    relocations = tuple(relocations)
    names = [symbol.name for symbol in symbols]
    strbytes = ("\0" + "\0".join(names) + "\0").encode("ascii")
    name_offsets: dict[str, int] = {}
    cursor = 1
    for name in names:
        name_offsets[name] = cursor
        cursor += len(name) + 1
    shstrbytes = b"\0.text\0.rela.text\0.symtab\0.strtab\0.shstrtab\0"
    shstr_names = (".text", ".rela.text", ".symtab", ".strtab", ".shstrtab")
    shstr_offsets = {name: shstrbytes.index(name.encode("ascii")) for name in shstr_names}
    symbol_index = {symbol.name: index for index, symbol in enumerate(symbols, start=1)}
    symtab = bytearray(struct.pack("<IBBHQQ", 0, 0, 0, 0, 0, 0))
    for symbol in symbols:
        info = (1 << 4) | 2 if symbol.defined else (1 << 4)
        section = 1 if symbol.defined else 0
        symtab.extend(struct.pack("<IBBHQQ", name_offsets[symbol.name], info, 0, section, symbol.offset, 0))
    rela = bytearray()
    for relocation in relocations:
        offset = relocation_offsets.get(relocation.offset)
        if offset is None or relocation.symbol not in symbol_index:
            raise AArch64ObjectLinkError("relocation cannot be encoded in ELF")
        rela.extend(struct.pack("<QQq", offset, (symbol_index[relocation.symbol] << 32) | _R_AARCH64_CALL26, 0))
    sections = (
        (0, 0, 0, 0, b"", 0, 0, 1, 0),
        (shstr_offsets[".text"], 1, 6, 0x1000 if file_type == 2 else 0, text, 0, 0, 4, 0),
        (shstr_offsets[".rela.text"], 4, 0, 0, bytes(rela), 3, 1, 8, 24),
        (shstr_offsets[".symtab"], 2, 0, 0, bytes(symtab), 4, 1, 8, 24),
        (shstr_offsets[".strtab"], 3, 0, 0, strbytes, 0, 0, 1, 0),
        (shstr_offsets[".shstrtab"], 3, 0, 0, shstrbytes, 0, 0, 1, 0),
    )
    payload = bytearray(b"\0" * 64)
    data_offsets: list[int] = []
    for _name, _kind, _flags, _addr, body, _link, _info, alignment, _entsize in sections:
        if not body:
            data_offsets.append(0)
            continue
        position = _align(len(payload), alignment)
        payload.extend(b"\0" * (position - len(payload)))
        data_offsets.append(position)
        payload.extend(body)
    shoff = _align(len(payload), 8)
    payload.extend(b"\0" * (shoff - len(payload)))
    for index, (name, kind, flags, addr, body, link, info, alignment, entsize) in enumerate(sections):
        payload.extend(struct.pack("<IIQQQQIIQQ", name, kind, flags, addr, data_offsets[index], len(body), link, info, alignment, entsize))
    header = struct.pack("<16sHHIQQQIHHHHHH", b"\x7fELF" + bytes((ELF64_CLASS, ELF_LITTLE_ENDIAN, 1)) + b"\0" * 9, file_type, AARCH64_ELF_MACHINE, 1, entrypoint, 0, shoff, 0, 64, 0, 0, 64, len(sections), 5)
    payload[:64] = header
    return bytes(payload)


def _section_names(payload: bytes) -> frozenset[str]:
    try:
        shoff = int.from_bytes(payload[40:48], "little")
        shentsize = int.from_bytes(payload[58:60], "little")
        shnum = int.from_bytes(payload[60:62], "little")
        shstrndx = int.from_bytes(payload[62:64], "little")
        if shentsize != 64 or not shnum or shstrndx >= shnum or shoff + shentsize * shnum > len(payload):
            return frozenset()
        shstr = payload[shoff + shstrndx * shentsize : shoff + (shstrndx + 1) * shentsize]
        start = int.from_bytes(shstr[24:32], "little")
        names = payload[start : start + int.from_bytes(shstr[32:40], "little")]
        result: set[str] = set()
        for index in range(shnum):
            section = payload[shoff + index * shentsize : shoff + (index + 1) * shentsize]
            name_start = int.from_bytes(section[:4], "little")
            end = names.find(b"\0", name_start)
            if 0 <= name_start < len(names) and end >= 0:
                result.add(names[name_start:end].decode("ascii"))
        return frozenset(result)
    except (IndexError, UnicodeError):
        return frozenset()


def _extract_section(payload: bytes, wanted: str) -> bytes:
    shoff = int.from_bytes(payload[40:48], "little")
    shentsize = int.from_bytes(payload[58:60], "little")
    shnum = int.from_bytes(payload[60:62], "little")
    shstrndx = int.from_bytes(payload[62:64], "little")
    if shentsize != 64 or shstrndx >= shnum:
        raise AArch64ObjectLinkError("ELF section table is invalid")
    shstr = payload[shoff + shstrndx * shentsize : shoff + (shstrndx + 1) * shentsize]
    start = int.from_bytes(shstr[24:32], "little")
    names = payload[start : start + int.from_bytes(shstr[32:40], "little")]
    for index in range(shnum):
        section = payload[shoff + index * shentsize : shoff + (index + 1) * shentsize]
        name_start = int.from_bytes(section[:4], "little")
        end = names.find(b"\0", name_start)
        if name_start < len(names) and end >= 0 and names[name_start:end].decode("ascii") == wanted:
            data_start = int.from_bytes(section[24:32], "little")
            return payload[data_start : data_start + int.from_bytes(section[32:40], "little")]
    raise AArch64ObjectLinkError(f"ELF section {wanted!r} is missing")


def _validate_header(payload: bytes, *, file_type: int, entrypoint: int | None = None) -> None:
    if len(payload) < 64 or payload[:4] != b"\x7fELF" or payload[4] != ELF64_CLASS or payload[5] != ELF_LITTLE_ENDIAN:
        raise AArch64ObjectLinkError("artifact lacks ELF64 little-endian identity")
    if int.from_bytes(payload[16:18], "little") != file_type or int.from_bytes(payload[18:20], "little") != AARCH64_ELF_MACHINE:
        raise AArch64ObjectLinkError("artifact ELF type or machine is invalid")
    if entrypoint is not None and int.from_bytes(payload[24:32], "little") != entrypoint:
        raise AArch64ObjectLinkError("linked entrypoint is not encoded in ELF identity")


def _positive_limit(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AArch64ObjectLinkError(f"{name} must be positive")
