"""Bounded AArch64 object/link contracts for M1.97.

This module owns the deterministic object and link boundary.  It validates the
target, symbol table, supported relocation set, entry symbol, and artifact
size before handing native assembly/linking to an injected platform provider.
The structural bytes are an auditable ELF-identity envelope plus a canonical
manifest; they are not presented as native execution evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Iterable

from .aarch64_toolchain import AArch64NativeBuildPlan, AArch64Relocation
from .backends.aarch64 import AARCH64_ELF_MACHINE, ELF64_CLASS, ELF_LITTLE_ENDIAN


MAX_OBJECT_BYTES = 64 * 1024 * 1024
MAX_SYMBOLS = 100_000
MAX_RELOCATIONS = 100_000
SUPPORTED_RELOCATIONS = ("call26",)
_SYMBOL = re.compile(r"^[A-Za-z_.$][A-Za-z0-9_.$]*$")


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
    """Build deterministic object/link envelopes without invoking a host linker."""

    def __init__(
        self,
        *,
        max_object_bytes: int = MAX_OBJECT_BYTES,
        max_symbols: int = MAX_SYMBOLS,
        max_relocations: int = MAX_RELOCATIONS,
    ) -> None:
        _positive_limit(max_object_bytes, "max_object_bytes")
        _positive_limit(max_symbols, "max_symbols")
        _positive_limit(max_relocations, "max_relocations")
        self.max_object_bytes = max_object_bytes
        self.max_symbols = max_symbols
        self.max_relocations = max_relocations

    def build_object(self, plan: AArch64NativeBuildPlan) -> AArch64ObjectArtifact:
        if not isinstance(plan, AArch64NativeBuildPlan):
            raise AArch64ObjectLinkError("object build requires an AArch64 build plan")
        if plan.target != "linux-aarch64":
            raise AArch64ObjectLinkError("M1.97 object/link contract requires linux-aarch64")
        if not plan.structurally_complete:
            raise AArch64ObjectLinkError("AArch64 build plan is structurally incomplete")
        if not plan.defined_symbols or plan.entry_symbol not in plan.defined_symbols:
            raise AArch64ObjectLinkError("entry symbol is not defined by the object")
        for relocation in plan.relocations:
            _validate_relocation(relocation)
        symbols = _symbols(plan)
        object_bytes = _envelope(
            _elf_header(file_type=1),
            _manifest(
                kind="relocatable",
                target=plan.target,
                entry_symbol=plan.entry_symbol,
                text=plan.assembly_text,
                symbols=_symbol_records(symbols),
                relocations=_relocation_records(plan.relocations),
            ),
        )
        artifact = AArch64ObjectArtifact(
            plan.target,
            "ELF64-REL-AARCH64",
            plan.entry_symbol,
            plan.assembly_text,
            symbols,
            plan.relocations,
            object_bytes,
        )
        validate_object_artifact(artifact, max_object_bytes=self.max_object_bytes, max_symbols=self.max_symbols, max_relocations=self.max_relocations)
        return artifact

    def link(
        self,
        artifact: AArch64ObjectArtifact,
        *,
        resolved_symbols: Iterable[str] = (),
    ) -> AArch64LinkedArtifact:
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
        linked_bytes = _envelope(
            _elf_header(file_type=2, entrypoint=entrypoint),
            _manifest(
                kind="linked",
                target=artifact.target,
                entry_symbol=artifact.entry_symbol,
                entrypoint=entrypoint,
                resolved_symbols=resolved,
                relocations=_relocation_records(artifact.relocations),
            ),
        )
        linked = AArch64LinkedArtifact(
            artifact.target,
            "ELF64-EXEC-AARCH64",
            artifact.entry_symbol,
            entrypoint,
            resolved,
            artifact.relocations,
            linked_bytes,
        )
        validate_linked_artifact(linked, max_object_bytes=self.max_object_bytes)
        return linked


def validate_object_artifact(
    artifact: AArch64ObjectArtifact,
    *,
    max_object_bytes: int = MAX_OBJECT_BYTES,
    max_symbols: int = MAX_SYMBOLS,
    max_relocations: int = MAX_RELOCATIONS,
) -> None:
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
    names = [symbol.name for symbol in artifact.symbols]
    if len(names) != len(set(names)) or artifact.entry_symbol not in names:
        raise AArch64ObjectLinkError("object symbols are not unique or entry is absent")
    for symbol in artifact.symbols:
        if not _SYMBOL.fullmatch(symbol.name) or symbol.offset < 0:
            raise AArch64ObjectLinkError("object symbol is invalid")
        if symbol.defined != (symbol.section == ".text"):
            raise AArch64ObjectLinkError("object symbol section does not match definition")
    for relocation in artifact.relocations:
        _validate_relocation(relocation)
        if relocation.symbol not in names:
            raise AArch64ObjectLinkError("relocation references an absent symbol")


def validate_linked_artifact(
    artifact: AArch64LinkedArtifact,
    *,
    max_object_bytes: int = MAX_OBJECT_BYTES,
) -> None:
    if not isinstance(artifact, AArch64LinkedArtifact) or artifact.target != "linux-aarch64":
        raise AArch64ObjectLinkError("invalid Linux AArch64 linked artifact")
    if artifact.format != "ELF64-EXEC-AARCH64" or artifact.entrypoint < 0x1000:
        raise AArch64ObjectLinkError("linked artifact format or entrypoint is invalid")
    _validate_header(artifact.bytes, file_type=2, entrypoint=artifact.entrypoint)
    if len(artifact.bytes) > max_object_bytes:
        raise AArch64ObjectLinkError("linked artifact exceeds bounded size")
    if not _SYMBOL.fullmatch(artifact.entry_symbol) or artifact.entry_symbol not in artifact.resolved_symbols:
        raise AArch64ObjectLinkError("linked entry symbol is invalid")
    for relocation in artifact.relocations_applied:
        _validate_relocation(relocation)


def _symbols(plan: AArch64NativeBuildPlan) -> tuple[AArch64ObjectSymbol, ...]:
    defined = tuple(
        AArch64ObjectSymbol(name, True, ".text", index)
        for index, name in enumerate(plan.defined_symbols)
    )
    defined_names = set(plan.defined_symbols)
    runtime = tuple(
        AArch64ObjectSymbol(name, False, None, 0)
        for name in plan.runtime_symbols
        if name not in defined_names
    )
    return tuple(sorted((*defined, *runtime), key=lambda symbol: symbol.name))


def _symbol_records(symbols: Iterable[AArch64ObjectSymbol]) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "name": symbol.name,
            "defined": symbol.defined,
            "section": symbol.section,
            "offset": symbol.offset,
        }
        for symbol in symbols
    )


def _relocation_records(relocations: Iterable[AArch64Relocation]) -> tuple[dict[str, object], ...]:
    return tuple(
        {"symbol": relocation.symbol, "kind": relocation.kind, "offset": relocation.offset}
        for relocation in relocations
    )


def _validate_relocation(relocation: AArch64Relocation) -> None:
    if not isinstance(relocation, AArch64Relocation) or relocation.kind not in SUPPORTED_RELOCATIONS:
        raise AArch64ObjectLinkError("unsupported AArch64 relocation")
    if not _SYMBOL.fullmatch(relocation.symbol) or relocation.offset < 0:
        raise AArch64ObjectLinkError("invalid AArch64 relocation")


def _manifest(**payload: object) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _envelope(header: bytes, manifest: bytes) -> bytes:
    return header + len(manifest).to_bytes(8, "little") + manifest


def _elf_header(*, file_type: int, entrypoint: int = 0) -> bytes:
    header = bytearray(64)
    header[:4] = b"\x7fELF"
    header[4] = ELF64_CLASS
    header[5] = ELF_LITTLE_ENDIAN
    header[6] = 1
    header[16:18] = int(file_type).to_bytes(2, "little")
    header[18:20] = AARCH64_ELF_MACHINE.to_bytes(2, "little")
    header[20:24] = (1).to_bytes(4, "little")
    header[24:32] = int(entrypoint).to_bytes(8, "little")
    return bytes(header)


def _validate_header(payload: bytes, *, file_type: int, entrypoint: int | None = None) -> None:
    if len(payload) < 72 or payload[:4] != b"\x7fELF" or payload[4] != ELF64_CLASS or payload[5] != ELF_LITTLE_ENDIAN:
        raise AArch64ObjectLinkError("artifact lacks ELF64 little-endian identity")
    if int.from_bytes(payload[16:18], "little") != file_type or int.from_bytes(payload[18:20], "little") != AARCH64_ELF_MACHINE:
        raise AArch64ObjectLinkError("artifact ELF type or machine is invalid")
    if entrypoint is not None and int.from_bytes(payload[24:32], "little") != entrypoint:
        raise AArch64ObjectLinkError("linked entrypoint is not encoded in ELF identity")


def _positive_limit(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise AArch64ObjectLinkError(f"{name} must be positive")
