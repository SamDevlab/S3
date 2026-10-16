"""Runtime transport for the native S3C-NG source-set compiler."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import struct
import subprocess
import tempfile
import time
from collections.abc import Mapping
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Protocol

from .diagnostics import DiagnosticCategory, DiagnosticCode, DiagnosticPhase, S3Error
from .compiler_ng_ir_bridge import NG_IR_FORMAT_VERSION


_INPUT_MAGIC = b"S3NGIN01"
_OUTPUT_MAGIC = b"S3NGOUT1"
_OUTPUT_V2_MAGIC = b"S3NGOUT2"
_MAX_DYNAMIC_BYTES = 64 * 1024 * 1024
_MAX_SOURCE_UNITS = 4096
_OUTPUT_HEADER_SIZE = 32
_OUTPUT_V2_HEADER_SIZE = 40
_DIAGNOSTIC_RECORD_I64S = 7
_MAX_DIAGNOSTIC_RECORDS = 256
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class NativeS3CTransportError(S3Error):
    category = "native compiler transport error"
    diagnostic_category = DiagnosticCategory.TOOLCHAIN
    diagnostic_code = DiagnosticCode.TOOLCHAIN_FAILED
    diagnostic_phase = DiagnosticPhase.TOOLCHAIN


@dataclass(frozen=True, slots=True)
class NativeS3CExecutable:
    executable: Path
    entry_symbol: str


class NativeDiagnosticCategory(IntEnum):
    SEMANTIC = 1


class NativeDiagnosticPhase(IntEnum):
    SEMANTIC = 1


class NativeDiagnosticCode(IntEnum):
    MODULE_NOT_FOUND = 1
    MODULE_CYCLE = 2
    IMPORT_UNKNOWN_SYMBOL = 3
    IMPORT_PRIVATE_SYMBOL = 4


class _ExecutableArtifact(Protocol):
    executable: Path
    entry_symbol: str


@dataclass(frozen=True, slots=True)
class NativeDiagnosticRecord:
    category_id: int
    phase_id: int
    code_id: int
    source_unit_index: int
    start_byte: int
    end_byte: int
    message_id: int


@dataclass(frozen=True, slots=True)
class NativeSourceSetResult:
    status: int
    source: bytes
    events: tuple[int, ...]
    returncode: int
    stdout: bytes
    stderr: bytes
    output_envelope_sha256: str
    output_envelope_bytes: int
    elapsed_seconds: float
    diagnostics: tuple[NativeDiagnosticRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class S3CNgAvailability:
    executable: Path
    available: bool
    reason: str | None = None


def default_s3c_ng_path() -> Path:
    """Return an explicit override, pinned installation, or development candidate."""

    override = os.environ.get("S3C_NG_BOOTSTRAP_EXECUTABLE")
    if override:
        return Path(override).expanduser().resolve()
    from .s3c_ng_distribution import pinned_install_path

    installed = pinned_install_path()
    if installed is not None:
        return installed

    repository = Path(__file__).resolve().parents[2]
    return repository / "build" / "s3c-ng"


def inspect_s3c_ng_executable(path: Path | None = None) -> S3CNgAvailability:
    try:
        executable = default_s3c_ng_path() if path is None else Path(path).expanduser().resolve()
    except S3Error as error:
        return S3CNgAvailability(Path(), False, str(error))
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        return S3CNgAvailability(
            executable,
            False,
            "S3C-NG native executable requires Linux x86-64",
        )
    if not executable.is_file():
        return S3CNgAvailability(
            executable,
            False,
            f"S3C-NG executable not found: {executable}",
        )
    try:
        with executable.open("rb") as stream:
            header = stream.read(20)
    except OSError as error:
        return S3CNgAvailability(executable, False, str(error))
    if (
        len(header) < 20
        or header[:4] != b"\x7fELF"
        or header[4] != 2
        or header[5] != 1
        or struct.unpack_from("<H", header, 18)[0] != 62
    ):
        return S3CNgAvailability(
            executable,
            False,
            "S3C-NG compiler artifact is not a little-endian x86-64 ELF",
        )
    manifest_path = executable.with_suffix(".manifest.json")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifact_sha256 = _sha256_file(executable)
        artifact_bytes = executable.stat().st_size
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return S3CNgAvailability(
            executable,
            False,
            f"S3C-NG artifact manifest is unavailable or invalid: {error}",
        )
    if not isinstance(manifest, dict):
        return S3CNgAvailability(executable, False, "S3C-NG artifact manifest must be an object")
    entry_symbol = manifest.get("entry_symbol")
    if (
        manifest.get("schema_version") != 2
        or manifest.get("target") != "linux-x86_64"
        or manifest.get("ng_ir_format_version") != NG_IR_FORMAT_VERSION
        or manifest.get("artifact_sha256") != artifact_sha256
        or manifest.get("artifact_bytes") != artifact_bytes
        or not isinstance(manifest.get("source_commit"), str)
        or _GIT_SHA_PATTERN.fullmatch(manifest["source_commit"]) is None
        or not isinstance(manifest.get("source_graph_sha256"), str)
        or _SHA256_PATTERN.fullmatch(manifest["source_graph_sha256"]) is None
        or not isinstance(manifest.get("compiler_ir_sha256"), str)
        or _SHA256_PATTERN.fullmatch(manifest["compiler_ir_sha256"]) is None
        or not isinstance(manifest.get("assembly_sha256"), str)
        or _SHA256_PATTERN.fullmatch(manifest["assembly_sha256"]) is None
        or not isinstance(manifest.get("object_sha256"), str)
        or _SHA256_PATTERN.fullmatch(manifest["object_sha256"]) is None
        or manifest.get("entry_module") != "app"
        or manifest.get("optimization_mode") != "O0"
        or not isinstance(manifest.get("toolchain"), dict)
        or not isinstance(manifest["toolchain"].get("compiler"), str)
        or not isinstance(manifest["toolchain"].get("version"), str)
        or not isinstance(manifest.get("bootstrap_parent"), dict)
        or manifest["bootstrap_parent"].get("kind") != "python-reference-stage0"
        or not isinstance(manifest["bootstrap_parent"].get("canonical_ir_sha256"), str)
        or _SHA256_PATTERN.fullmatch(
            manifest["bootstrap_parent"]["canonical_ir_sha256"]
        ) is None
        or manifest["bootstrap_parent"]["canonical_ir_sha256"]
        != manifest.get("compiler_ir_sha256")
        or not isinstance(entry_symbol, str)
        or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", entry_symbol) is None
    ):
        return S3CNgAvailability(
            executable,
            False,
            "S3C-NG artifact manifest does not match the executable or supported contract",
        )
    from .s3c_ng_distribution import verify_default_artifact

    pinned_error = verify_default_artifact(executable)
    if pinned_error:
        return S3CNgAvailability(executable, False, pinned_error)
    return S3CNgAvailability(executable, True)


def require_s3c_ng_executable(path: Path | None = None) -> NativeS3CExecutable:
    availability = inspect_s3c_ng_executable(path)
    if not availability.available:
        raise NativeS3CTransportError(
            availability.reason or "S3C-NG executable is unavailable"
        )
    manifest = json.loads(availability.executable.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    return NativeS3CExecutable(availability.executable, manifest["entry_symbol"])


def run_native_source_set(
    artifact: _ExecutableArtifact,
    sources: Mapping[str, str | bytes],
    *,
    entry_module: str,
    timeout: float = 120.0,
) -> NativeSourceSetResult:
    """Run S3C-NG on source bytes; this layer performs transport only."""

    if not sources or len(sources) > _MAX_SOURCE_UNITS:
        raise NativeS3CTransportError("source manifest has an unsupported unit count")
    executable = Path(artifact.executable)
    if not executable.is_file():
        raise NativeS3CTransportError(f"S3C-NG executable not found: {executable}")
    with tempfile.TemporaryDirectory(prefix="s3-ng-run-") as temporary:
        work_directory = Path(temporary)
        manifest_path = work_directory / "sources.s3ng"
        output_path = work_directory / "result.s3ng"
        manifest_path.write_bytes(encode_source_manifest(sources, entry_module))
        started = time.perf_counter()
        try:
            completed = subprocess.run(
                [str(executable), artifact.entry_symbol, str(manifest_path), str(output_path)],
                cwd=work_directory,
                capture_output=True,
                check=False,
                timeout=timeout,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise NativeS3CTransportError(f"native compiler process failed: {error}") from error
        elapsed_seconds = time.perf_counter() - started
        if completed.returncode != 0:
            detail = f"exit={completed.returncode}"
            stderr = completed.stderr.decode(errors="replace").strip()
            stdout = completed.stdout.decode(errors="replace").strip()
            if stderr:
                detail += f"; stderr={stderr}"
            if stdout:
                detail += f"; stdout={stdout}"
            raise NativeS3CTransportError(
                f"native compiler process failed before envelope decoding; {detail}"
            )
        if not output_path.is_file():
            raise NativeS3CTransportError(
                "native compiler produced no output envelope; "
                f"exit={completed.returncode}; stderr={completed.stderr.decode(errors='replace')}"
            )
        encoded_output = output_path.read_bytes()
        if encoded_output[:8] == _OUTPUT_MAGIC:
            status, source, events = decode_output_envelope(encoded_output)
            diagnostics: tuple[NativeDiagnosticRecord, ...] = ()
        elif encoded_output[:8] == _OUTPUT_V2_MAGIC:
            status, source, events, diagnostics = decode_output_envelope_v2(encoded_output)
        else:
            raise NativeS3CTransportError("native compiler output envelope has an unsupported version")
        return NativeSourceSetResult(
            status=status,
            source=source,
            events=events,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            output_envelope_sha256=hashlib.sha256(encoded_output).hexdigest(),
            output_envelope_bytes=len(encoded_output),
            elapsed_seconds=elapsed_seconds,
            diagnostics=diagnostics,
        )


def encode_source_manifest(
    sources: Mapping[str, str | bytes],
    entry_module: str,
) -> bytes:
    """Encode source-unit bytes in deterministic path order."""

    entry = entry_module.encode("utf-8")
    if len(entry) > 0xFFFFFFFF:
        raise NativeS3CTransportError("entry module name exceeds transport bounds")
    result = bytearray(_INPUT_MAGIC)
    result.extend(struct.pack("<II", len(entry), len(sources)))
    result.extend(entry)
    for path, value in sorted(sources.items()):
        path_bytes = path.encode("utf-8")
        source_bytes = value.encode("utf-8") if isinstance(value, str) else bytes(value)
        if len(path_bytes) > 0xFFFFFFFF or len(source_bytes) > _MAX_DYNAMIC_BYTES:
            raise NativeS3CTransportError("source unit exceeds transport bounds")
        result.extend(struct.pack("<IQ", len(path_bytes), len(source_bytes)))
        result.extend(path_bytes)
        result.extend(source_bytes)
    return bytes(result)


def decode_output_envelope(encoded: bytes) -> tuple[int, bytes, tuple[int, ...]]:
    """Decode the fixed transport envelope without interpreting IR semantics."""

    if len(encoded) < _OUTPUT_HEADER_SIZE or encoded[:8] != _OUTPUT_MAGIC:
        raise NativeS3CTransportError("native compiler output envelope has an invalid header")
    status, source_length, event_count = struct.unpack_from("<qQQ", encoded, 8)
    expected_length = _OUTPUT_HEADER_SIZE + source_length + event_count * 8
    if expected_length != len(encoded):
        raise NativeS3CTransportError("native compiler output envelope has inconsistent lengths")
    source_end = _OUTPUT_HEADER_SIZE + source_length
    source = encoded[_OUTPUT_HEADER_SIZE:source_end]
    events = (
        struct.unpack_from(f"<{event_count}q", encoded, source_end)
        if event_count
        else ()
    )
    return status, source, tuple(events)


def decode_output_envelope_v2(
    encoded: bytes,
) -> tuple[int, bytes, tuple[int, ...], tuple[NativeDiagnosticRecord, ...]]:
    """Decode S3NGOUT2, including its separate bounded diagnostic records."""

    if len(encoded) < _OUTPUT_V2_HEADER_SIZE or encoded[:8] != _OUTPUT_V2_MAGIC:
        raise NativeS3CTransportError("native compiler v2 output envelope has an invalid header")
    status, source_length, event_count, diagnostic_count = struct.unpack_from(
        "<qQQQ", encoded, 8
    )
    if (
        source_length > _MAX_DYNAMIC_BYTES
        or diagnostic_count > _MAX_DIAGNOSTIC_RECORDS
        or event_count > _MAX_DYNAMIC_BYTES // 8
    ):
        raise NativeS3CTransportError("native compiler v2 output envelope exceeds transport bounds")
    source_end = _OUTPUT_V2_HEADER_SIZE + source_length
    events_end = source_end + event_count * 8
    expected_length = events_end + diagnostic_count * _DIAGNOSTIC_RECORD_I64S * 8
    if expected_length != len(encoded):
        raise NativeS3CTransportError(
            "native compiler v2 output envelope has inconsistent lengths"
        )
    source = encoded[_OUTPUT_V2_HEADER_SIZE:source_end]
    events = (
        struct.unpack_from(f"<{event_count}q", encoded, source_end)
        if event_count
        else ()
    )
    records: list[NativeDiagnosticRecord] = []
    for index in range(diagnostic_count):
        values = struct.unpack_from(
            f"<{_DIAGNOSTIC_RECORD_I64S}q",
            encoded,
            events_end + index * _DIAGNOSTIC_RECORD_I64S * 8,
        )
        record = NativeDiagnosticRecord(*values)
        unlocated_cycle = (
            record.code_id == NativeDiagnosticCode.MODULE_CYCLE
            and record.source_unit_index == -1
            and record.start_byte == -1
            and record.end_byte == -1
        )
        if (
            record.category_id != NativeDiagnosticCategory.SEMANTIC
            or record.phase_id != NativeDiagnosticPhase.SEMANTIC
            or record.code_id not in {code.value for code in NativeDiagnosticCode}
            or record.message_id != record.code_id
            or not unlocated_cycle
            and (
                record.source_unit_index < 0
                or record.start_byte < 0
                or record.end_byte < record.start_byte
            )
        ):
            raise NativeS3CTransportError(
                f"native compiler v2 diagnostic record {index} is invalid or unsupported"
            )
        records.append(record)
    if status == 0 and records:
        raise NativeS3CTransportError(
            "native compiler v2 output attached diagnostics to a successful result"
        )
    return status, source, tuple(events), tuple(records)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
