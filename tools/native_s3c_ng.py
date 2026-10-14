"""Mechanical Linux launcher for the native S3C-NG source-set entrypoint."""

from __future__ import annotations

import hashlib
import json
import platform
import struct
import subprocess
from dataclasses import dataclass
from pathlib import Path

from bootstrap.s3.assembly import AssemblyProgram
from bootstrap.s3.backends.x86_64 import NativeToolchain, generate_ffi_assembly
from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.compiler_ng_ir_bridge import NG_IR_FORMAT_VERSION
from bootstrap.s3.ir import IRModule
from bootstrap.s3.ir_serialization import serialize_ir
from bootstrap.s3.native_compiler import (
    NativeS3CTransportError,
    NativeSourceSetResult,
    decode_output_envelope,
    encode_source_manifest,
    run_native_source_set,
)
from bootstrap.s3.pipeline import compile_sources
from bootstrap.s3.verifier import verify_ir


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


def compiler_source_set(repository: Path) -> dict[str, str]:
    """Return the dependency-closed S3C-NG graph with an ordinary app entry."""

    sources = {
        "app.s3": "module app\nfn main() -> i64:\n    return 0\n",
    }
    module_root = repository / "selfhost" / "compiler_ng"
    for name in _SOURCE_MODULES:
        sources[f"{name}.s3"] = (module_root / f"{name}.s3").read_text(encoding="utf-8")
    return sources


def compiler_source_graph_sha256(sources: dict[str, str]) -> str:
    """Hash source paths and bytes using an unambiguous deterministic framing."""

    digest = hashlib.sha256(b"S3C-NG-SOURCE-GRAPH-V1\0")
    for logical_path, source in sorted(sources.items()):
        path_bytes = logical_path.replace("\\", "/").encode("utf-8")
        source_bytes = source.encode("utf-8")
        digest.update(struct.pack("<Q", len(path_bytes)))
        digest.update(path_bytes)
        digest.update(struct.pack("<Q", len(source_bytes)))
        digest.update(source_bytes)
    return digest.hexdigest()


def write_s3c_ng_candidate_manifest(
    artifact: NativeS3CArtifact,
    path: Path,
    *,
    source_commit: str,
    source_graph_sha256: str,
    toolchain_version: str,
    bootstrap_parent_ir_sha256: str,
) -> Path:
    """Write deterministic provenance for an explicitly reference-seeded candidate."""

    manifest = {
        "schema_version": 2,
        "target": "linux-x86_64",
        "ng_ir_format_version": NG_IR_FORMAT_VERSION,
        "entry_module": "app",
        "entry_symbol": artifact.entry_symbol,
        "optimization_mode": "O0",
        "artifact_sha256": artifact.executable_sha256,
        "artifact_bytes": artifact.executable_bytes,
        "source_commit": source_commit,
        "source_graph_sha256": source_graph_sha256,
        "compiler_ir_sha256": artifact.compiler_ir_sha256,
        "assembly_sha256": artifact.assembly_sha256,
        "object_sha256": artifact.object_sha256,
        "toolchain": {
            "compiler": artifact.toolchain.compiler,
            "version": toolchain_version,
            "assembler": artifact.toolchain.assembler,
            "linker": artifact.toolchain.linker,
        },
        "bootstrap_parent": {
            "kind": "python-reference-stage0",
            "canonical_ir_sha256": bootstrap_parent_ir_sha256,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return path


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
