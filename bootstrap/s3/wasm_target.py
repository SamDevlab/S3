"""Structural wasm32-wasip1-s3 target contract for M1.49.

The module encoder is deliberately small and deterministic. Runtime
certification belongs to Wasmtime/wasm-tools and is not simulated here.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from .targets import TargetSpec


class WasmTargetError(ValueError):
    """Raised when a structural WASI target contract is invalid."""


WASM32_WASIP1_S3_TARGET = TargetSpec(
    name="wasm32-wasip1-s3",
    architecture="wasm32",
    environment="wasi-preview1",
)
WASI_MODULE = "wasi_snapshot_preview1"
WASI_MEMORY_LIMIT_BYTES = 64 * 1024 * 1024
WASI_MEMORY_LIMIT_PAGES = WASI_MEMORY_LIMIT_BYTES // 65536
LOGICAL_S3_INSTRUCTION_LIMIT = 100_000
_EXPORT_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_HASH = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class WASIImport:
    name: str
    capability: str


WASI_IMPORTS = (
    WASIImport("args_sizes_get", "argv"),
    WASIImport("args_get", "argv"),
    WASIImport("environ_sizes_get", "environment.read"),
    WASIImport("environ_get", "environment.read"),
    WASIImport("fd_read", "filesystem.read"),
    WASIImport("fd_write", "filesystem.write"),
    WASIImport("fd_close", "filesystem.read/write"),
    WASIImport("fd_seek", "filesystem.read/write"),
    WASIImport("path_open", "filesystem.read/write"),
    WASIImport("path_filestat_get", "filesystem.read"),
    WASIImport("proc_exit", "process.exit"),
)
WASI_FORBIDDEN_IMPORTS = (
    "clock_time_get",
    "random_get",
    "poll_oneoff",
    "sock_accept",
    "sock_recv",
    "sock_send",
    "sock_shutdown",
    "path_create_directory",
    "path_remove_directory",
)


@dataclass(frozen=True, slots=True)
class WASIImportManifest:
    """Closed import namespace and capability mapping."""

    module: str = WASI_MODULE
    imports: tuple[WASIImport, ...] = WASI_IMPORTS
    forbidden: tuple[str, ...] = WASI_FORBIDDEN_IMPORTS

    def validate(self, used_imports: Iterable[str]) -> tuple[str, ...]:
        used = tuple(used_imports)
        if any(not isinstance(item, str) or not item for item in used):
            raise WasmTargetError("WASI import names must be non-empty strings")
        if len(set(used)) != len(used):
            raise WasmTargetError("WASI imports must not be duplicated")
        allowed = {item.name for item in self.imports}
        forbidden = set(self.forbidden)
        denied = sorted(set(used) & forbidden)
        if denied:
            raise WasmTargetError(f"forbidden WASI import {denied[0]!r}")
        unknown = sorted(set(used) - allowed)
        if unknown:
            raise WasmTargetError(f"unsupported WASI import {unknown[0]!r}")
        return tuple(item.name for item in self.imports if item.name in used)

    def imports_for_capabilities(self, capabilities: Iterable[str]) -> tuple[str, ...]:
        requested = tuple(capabilities)
        if len(set(requested)) != len(requested):
            raise WasmTargetError("capabilities must not be duplicated")
        known = {item.capability for item in self.imports}
        known.add("network.tcp")
        unknown = sorted(set(requested) - known)
        if unknown:
            raise WasmTargetError(f"unsupported WASI capability {unknown[0]!r}")
        if "network.tcp" in requested:
            raise WasmTargetError("network.tcp requires an exact provider adapter")
        return tuple(
            item.name
            for item in self.imports
            if item.capability in requested
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "schema_version": "s3.wasi-preview1-imports.v1",
            "module": self.module,
            "imports": [
                {"name": item.name, "capability": item.capability}
                for item in self.imports
            ],
            "forbidden": list(self.forbidden),
            "tcp": "M1.48 adapter only; no Preview 1 socket imports are whitelisted",
        }

    def as_json(self) -> str:
        return json.dumps(self.as_dict(), separators=(",", ":"))


WASI_IMPORT_MANIFEST = WASIImportManifest()


@dataclass(frozen=True, slots=True)
class WasmArtifact:
    """Deterministic structural artifact with no runtime claim."""

    target: TargetSpec
    profile: str
    module_bytes: bytes
    identity: str
    source_sha256: str
    lock_sha256: str

    @property
    def artifact_sha256(self) -> str:
        return hashlib.sha256(self.module_bytes).hexdigest()


def _validate_hash(value: str, *, field: str) -> str:
    if not isinstance(value, str) or _HASH.fullmatch(value) is None:
        raise WasmTargetError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def artifact_identity(
    *,
    source_sha256: str,
    lock_sha256: str,
    target: TargetSpec = WASM32_WASIP1_S3_TARGET,
    profile: str = "wasi-preview1-core-v1",
    compiler_version: str = "s3-bootstrap-1.1.0",
    encoder_version: str = "s3-wasm-encoder-v1",
) -> str:
    """Hash only canonical inputs; never absolute paths or environment data."""

    source_sha256 = _validate_hash(source_sha256, field="source_sha256")
    lock_sha256 = _validate_hash(lock_sha256, field="lock_sha256")
    values = {
        "compiler_version": compiler_version,
        "encoder_version": encoder_version,
        "lock_sha256": lock_sha256,
        "profile": profile,
        "source_sha256": source_sha256,
        "target": target.name,
    }
    if any(not isinstance(value, str) or not value for value in values.values()):
        raise WasmTargetError("artifact identity fields must be non-empty strings")
    payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _uleb(value: int) -> bytes:
    if value < 0:
        raise WasmTargetError("unsigned LEB128 cannot encode a negative value")
    result = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        result.append(byte | 0x80 if value else byte)
        if not value:
            return bytes(result)


def _sleb32(value: int) -> bytes:
    if not -(2**31) <= value <= 2**31 - 1:
        raise WasmTargetError("i32 fixture result is outside signed i32")
    result = bytearray()
    more = True
    while more:
        byte = value & 0x7F
        value >>= 7
        sign = byte & 0x40
        more = not ((value == 0 and not sign) or (value == -1 and sign))
        result.append(byte | 0x80 if more else byte)
    return bytes(result)


def _name(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return _uleb(len(encoded)) + encoded


def _section(identifier: int, payload: bytes) -> bytes:
    return bytes((identifier,)) + _uleb(len(payload)) + payload


def render_i32_fixture(value: int, *, export_name: str = "s3_main") -> bytes:
    """Render a minimal no-host core module returning one i32 constant."""

    if isinstance(value, bool) or not isinstance(value, int):
        raise WasmTargetError("portable fixture value must be an integer")
    if _EXPORT_NAME.fullmatch(export_name) is None:
        raise WasmTargetError("invalid portable fixture export name")
    type_section = _section(1, b"\x01\x60\x00\x01\x7f")
    function_section = _section(3, b"\x01\x00")
    memory_limits = b"\x01\x01" + _uleb(1) + _uleb(WASI_MEMORY_LIMIT_PAGES)
    memory_section = _section(5, memory_limits)
    exports = (
        b"\x02"
        + _name(export_name)
        + b"\x00\x00"
        + _name("memory")
        + b"\x02\x00"
    )
    export_section = _section(7, exports)
    body = b"\x00\x41" + _sleb32(value) + b"\x0b"
    code_section = _section(10, b"\x01" + _uleb(len(body)) + body)
    return b"\x00asm\x01\x00\x00\x00" + type_section + function_section + memory_section + export_section + code_section


def validate_core_module(module_bytes: bytes) -> tuple[int, ...]:
    """Validate canonical header and monotonically ordered non-custom sections."""

    if not isinstance(module_bytes, bytes) or not module_bytes.startswith(b"\x00asm\x01\x00\x00\x00"):
        raise WasmTargetError("invalid WebAssembly core module header")
    index = 8
    section_ids: list[int] = []
    previous = 0
    while index < len(module_bytes):
        identifier = module_bytes[index]
        index += 1
        if identifier == 0 or identifier <= previous:
            raise WasmTargetError("module sections must be ordered and non-custom")
        previous = identifier
        section_ids.append(identifier)
        length, width = _read_uleb(module_bytes, index)
        index += width
        end = index + length
        if end > len(module_bytes):
            raise WasmTargetError("module section exceeds artifact length")
        index = end
    if index != len(module_bytes):
        raise WasmTargetError("module has trailing bytes")
    return tuple(section_ids)


def _read_uleb(payload: bytes, index: int) -> tuple[int, int]:
    value = 0
    shift = 0
    start = index
    while index < len(payload):
        byte = payload[index]
        index += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return value, index - start
        shift += 7
        if shift > 35:
            break
    raise WasmTargetError("invalid unsigned LEB128 section length")


def build_i32_fixture(
    value: int,
    *,
    source: bytes = b"",
    lockfile: bytes = b"",
    profile: str = "wasi-preview1-core-v1",
) -> WasmArtifact:
    """Build a reproducible structural artifact without executing it."""

    source_hash = hashlib.sha256(source).hexdigest()
    lock_hash = hashlib.sha256(lockfile).hexdigest()
    module = render_i32_fixture(value)
    validate_core_module(module)
    return WasmArtifact(
        WASM32_WASIP1_S3_TARGET,
        profile,
        module,
        artifact_identity(
            source_sha256=source_hash,
            lock_sha256=lock_hash,
            profile=profile,
        ),
        source_hash,
        lock_hash,
    )
