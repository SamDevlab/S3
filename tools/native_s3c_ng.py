"""Mechanical Linux launcher for the native S3C-NG source-set entrypoint."""

from __future__ import annotations

import hashlib
import platform
import struct
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping

from bootstrap.s3.assembly import AssemblyProgram
from bootstrap.s3.backends.x86_64 import NativeToolchain, generate_ffi_assembly
from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.ir import IRModule
from bootstrap.s3.ir_serialization import serialize_ir
from bootstrap.s3.pipeline import compile_sources
from bootstrap.s3.verifier import verify_ir


_INPUT_MAGIC = b"S3NGIN01"
_OUTPUT_MAGIC = b"S3NGOUT1"
_MAX_DYNAMIC_BYTES = 64 * 1024 * 1024
_MAX_SOURCE_UNITS = 4096
_SOURCE_MODULES = (
    "character_classes",
    "lexer",
    "types",
    "parser",
    "semantic",
    "ir",
    "modules",
)


@dataclass(frozen=True, slots=True)
class NativeS3CArtifact:
    compiler_ir: IRModule
    entry_symbol: str
    compiler_ir_sha256: str
    assembly: str
    assembly_sha256: str
    object_path: Path
    object_sha256: str
    executable: Path
    executable_sha256: str
    executable_bytes: int
    toolchain: NativeToolchain


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


class NativeS3CTransportError(RuntimeError):
    pass


def compiler_source_set(repository: Path) -> dict[str, str]:
    """Return the dependency-closed S3C-NG graph with an ordinary app entry."""

    sources = {
        "app.s3": "module app\nfn main() -> i64:\n    return 0\n",
    }
    module_root = repository / "selfhost" / "compiler_ng"
    for name in _SOURCE_MODULES:
        sources[f"{name}.s3"] = (module_root / f"{name}.s3").read_text(encoding="utf-8")
    return sources


def compile_reference_b_ir(repository: Path) -> IRModule:
    """Reconstruct B's canonical structure using the reference frontend.

    The existing hosted self-compile gate proved structural equality between
    this reference IR and the hosted S3C-NG generation B. CI did not retain B's
    raw event artifact, so this function does not claim byte provenance from A.
    """

    result = compile_sources(compiler_source_set(repository), entry_module="app")
    if result.ir is None:
        raise NativeS3CTransportError("compiler source graph did not produce ordinary IR")
    verify_ir(result.ir)
    return result.ir


def build_native_s3c(
    compiler_ir: IRModule,
    output_directory: Path,
    *,
    label: str = "compiler",
) -> NativeS3CArtifact:
    """Lower S3 compiler IR through the production x86-64 FFI/native toolchain."""

    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise NativeS3CTransportError("native S3C-NG build requires Linux x86-64")
    verify_ir(compiler_ir)
    output_directory.mkdir(parents=True, exist_ok=True)
    toolchain = NativeToolchain.detect()
    assembly_program: AssemblyProgram = generate_assembly(compiler_ir)
    entry_symbols = [
        function.name
        for function in compiler_ir.functions
        if function.exported and function.name.endswith("ng_emit_source_set")
    ]
    if len(entry_symbols) != 1:
        raise NativeS3CTransportError(
            "compiler IR must expose exactly one ng_emit_source_set entrypoint"
        )
    entry_symbol = entry_symbols[0]
    assembly = generate_ffi_assembly(
        assembly_program,
        max_frames=4096,
        max_instructions=1_000_000_000,
    )
    assembly_path = output_directory / f"{label}.s"
    object_path = output_directory / f"{label}.o"
    executable_path = output_directory / label
    assembly_path.write_text(assembly, encoding="utf-8", newline="\n")

    _run_tool(
        [toolchain.compiler, "-x", "assembler", "-c", str(assembly_path), "-o", str(object_path)],
        cwd=output_directory,
    )

    driver_source = Path(__file__).with_name("native_selfhost_driver.c")
    _run_tool(
        [
            toolchain.compiler,
            "-std=c11",
            "-O2",
            "-no-pie",
            "-rdynamic",
            str(driver_source),
            str(object_path),
            "-ldl",
            "-o",
            str(executable_path),
        ],
        cwd=output_directory,
    )

    ir_bytes = serialize_ir(compiler_ir).encode("utf-8")
    assembly_bytes = assembly.encode("utf-8")
    return NativeS3CArtifact(
        compiler_ir=compiler_ir,
        entry_symbol=entry_symbol,
        compiler_ir_sha256=hashlib.sha256(ir_bytes).hexdigest(),
        assembly=assembly,
        assembly_sha256=hashlib.sha256(assembly_bytes).hexdigest(),
        object_path=object_path,
        object_sha256=_sha256_file(object_path),
        executable=executable_path,
        executable_sha256=_sha256_file(executable_path),
        executable_bytes=executable_path.stat().st_size,
        toolchain=toolchain,
    )


def run_native_source_set(
    artifact: NativeS3CArtifact,
    sources: Mapping[str, str | bytes],
    *,
    entry_module: str,
    timeout: float = 120.0,
) -> NativeSourceSetResult:
    """Package opaque source bytes, run native S3C-NG, and decode its envelope."""

    if not sources or len(sources) > _MAX_SOURCE_UNITS:
        raise NativeS3CTransportError("source manifest has an unsupported unit count")
    work_directory = artifact.executable.parent
    with tempfile.TemporaryDirectory(prefix="s3-ng-run-", dir=work_directory) as temporary:
        manifest_path = Path(temporary) / "sources.s3ng"
        output_path = Path(temporary) / "result.s3ng"
        manifest_path.write_bytes(encode_source_manifest(sources, entry_module))
        started = time.perf_counter()
        completed = subprocess.run(
            [
                str(artifact.executable),
                artifact.entry_symbol,
                str(manifest_path),
                str(output_path),
            ],
            cwd=work_directory,
            capture_output=True,
            check=False,
            timeout=timeout,
        )
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
        status, source, events = decode_output_envelope(encoded_output)
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
        )


def encode_source_manifest(
    sources: Mapping[str, str | bytes],
    entry_module: str,
) -> bytes:
    """Encode transport fields without interpreting module or S3 semantics."""

    entry = entry_module.encode("utf-8")
    if len(entry) > 0xFFFFFFFF:
        raise NativeS3CTransportError("entry module name exceeds transport bounds")
    result = bytearray(_INPUT_MAGIC)
    result.extend(struct.pack("<II", len(entry), len(sources)))
    result.extend(entry)
    for path, value in sources.items():
        path_bytes = path.encode("utf-8")
        source_bytes = value.encode("utf-8") if isinstance(value, str) else bytes(value)
        if len(path_bytes) > 0xFFFFFFFF or len(source_bytes) > _MAX_DYNAMIC_BYTES:
            raise NativeS3CTransportError("source unit exceeds transport bounds")
        result.extend(struct.pack("<IQ", len(path_bytes), len(source_bytes)))
        result.extend(path_bytes)
        result.extend(source_bytes)
    return bytes(result)


def decode_output_envelope(encoded: bytes) -> tuple[int, bytes, tuple[int, ...]]:
    """Decode the fixed transport envelope; no IR or source semantics are applied."""

    header_size = 32
    if len(encoded) < header_size or encoded[:8] != _OUTPUT_MAGIC:
        raise NativeS3CTransportError("native compiler output envelope has an invalid header")
    status, source_length, event_count = struct.unpack_from("<qQQ", encoded, 8)
    expected_length = header_size + source_length + event_count * 8
    if expected_length != len(encoded):
        raise NativeS3CTransportError("native compiler output envelope has inconsistent lengths")
    source_start = header_size
    source_end = source_start + source_length
    source = encoded[source_start:source_end]
    events = struct.unpack_from(f"<{event_count}q", encoded, source_end) if event_count else ()
    return status, source, tuple(events)


def _run_tool(command: list[str], *, cwd: Path) -> None:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            check=False,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise NativeS3CTransportError(f"native tool invocation failed: {error}") from error
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise NativeS3CTransportError(
            f"native tool exited with {completed.returncode}: {detail}"
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
