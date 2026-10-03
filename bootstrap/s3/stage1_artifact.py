"""Build and invoke the experimental Stage1 compiler as a verified IR artifact.

The build operation uses the trusted Python compiler. The compile operation
loads only the serialized IR artifact and hosted IR runtime; it does not import
or invoke the Python source compiler.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from enum import Enum
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from .assembly import AssemblyError, parse_assembly
from .assembly_verifier import AssemblyVerifier
from .diagnostics import S3Error
from .dynamic import DynamicVector, i64_vector_new
from .ir import IRType
from .ir_emulator import IRExecutionError, execute_ir
from .ir_serialization import deserialize_ir, serialize_ir


ARTIFACT_FORMAT = "s3-stage1-compiler"
ARTIFACT_VERSION = "1.0.0"
IR_FILENAME = "stage1.ir.json"
ASSEMBLY_FILENAME = "stage1-build.assembly-structure-summary.json"
MANIFEST_FILENAME = "manifest.json"
HASHES_FILENAME = "hashes.json"
PROVENANCE_FILENAME = "provenance.json"
ENTRY_FUNCTION = "stage1_compile_entry"
MAX_SOURCE_BYTES = 4096

_STAGE1_SOURCES = (
    "selfhost/substrate/generic_lexer_state.s3",
    "selfhost/substrate/verifier_kernel.s3",
    "selfhost/substrate/output_sink.s3",
    "selfhost/compiler/stage1_compiler_v1.s3",
)

_ENTRY_SOURCE = """\
module stage1_entry
from selfhost.compiler.stage1_compiler_v1 import Stage1CompileResult
from selfhost.compiler.stage1_compiler_v1 import stage1_compile
fn main() -> i64:
    return 0
export fn stage1_compile_entry(source: vector<i64>) -> vector<i64>:
    mut result: Stage1CompileResult = stage1_compile(source)
    mut envelope: vector<i64> = vector_new<i64>(result.output_length + 4)
    discard vector_push<i64>(&mut envelope, result.status)
    discard vector_push<i64>(&mut envelope, result.phase)
    discard vector_push<i64>(&mut envelope, result.error_code)
    discard vector_push<i64>(&mut envelope, result.output_length)
    mut output_index: i64 = 0
    while output_index < result.output_length:
        discard vector_push<i64>(&mut envelope, vector_get<i64>(&result.output, output_index))
        output_index = output_index + 1
    return envelope
"""


class Stage1ArtifactError(RuntimeError):
    """The persisted Stage1 artifact is absent, corrupt, or incompatible."""


class Stage1VerificationError(Stage1ArtifactError):
    """The persisted IR or Stage1-emitted Assembly failed independent checks."""


class Stage1Rejected(RuntimeError):
    def __init__(self, phase: int, error_code: int) -> None:
        self.phase = phase
        self.error_code = error_code
        super().__init__(f"Stage1 rejected source at phase {phase} (code {error_code})")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("ascii")


def _assembly_structure_bytes(program: object) -> bytes:
    def encode(value: object) -> str:
        if isinstance(value, Enum):
            return str(value.value)
        raise TypeError(f"unsupported Assembly metadata value: {type(value).__name__}")

    return (json.dumps(asdict(program), default=encode, ensure_ascii=True, indent=2, sort_keys=True) + "\n").encode("ascii")


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _bootstrap_source_tree_sha256(repository_root: Path) -> str:
    digest = hashlib.sha256()
    package_root = repository_root / "bootstrap" / "s3"
    for path in sorted(package_root.rglob("*.py"), key=lambda item: item.relative_to(repository_root).as_posix()):
        relative = path.relative_to(repository_root).as_posix().encode("utf-8")
        content_digest = hashlib.sha256(path.read_bytes()).digest()
        digest.update(relative + b"\0" + content_digest + b"\n")
    return digest.hexdigest()


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def build_stage1_artifact(
    output_directory: Path,
    *,
    repository_root: Path | None = None,
) -> dict[str, object]:
    """Build the reusable Stage1 IR artifact and deterministic metadata."""

    from .pipeline import compile_sources

    root = (repository_root or _repository_root()).resolve()
    sources: dict[str, str] = {}
    source_metadata: list[dict[str, object]] = []
    for relative in _STAGE1_SOURCES:
        raw = (root / relative).read_bytes()
        try:
            sources[relative] = raw.decode("utf-8")
        except UnicodeDecodeError as error:
            raise Stage1ArtifactError("Stage1 source is not valid UTF-8") from error
        source_metadata.append(
            {"path": relative, "bytes": len(raw), "sha256": _sha256(raw)}
        )
    entry_bytes = _ENTRY_SOURCE.encode("utf-8")
    sources["stage1_entry.s3"] = _ENTRY_SOURCE
    source_metadata.append(
        {"path": "stage1_entry.s3", "bytes": len(entry_bytes), "sha256": _sha256(entry_bytes)}
    )

    compilation = compile_sources(sources, entry_module="stage1_entry")
    if compilation.ir is None or compilation.assembly is None:
        raise Stage1ArtifactError("bootstrap did not produce ordinary IR and Assembly")

    entry_candidates = [
        function
        for function in compilation.ir.functions
        if function.name.endswith(f"__{ENTRY_FUNCTION}")
        and len(function.parameters) == 1
        and function.parameters[0].type is IRType.VECTOR
        and function.return_type is IRType.VECTOR
    ]
    if len(entry_candidates) != 1:
        raise Stage1ArtifactError("bootstrap did not produce one compatible Stage1 entry")
    entry_symbol = entry_candidates[0].name

    ir_data = serialize_ir(compilation.ir).encode("utf-8")
    round_trip = deserialize_ir(ir_data.decode("utf-8"))
    if serialize_ir(round_trip).encode("utf-8") != ir_data:
        raise Stage1ArtifactError("serialized Stage1 IR did not round-trip canonically")
    assembly_structure = _assembly_structure_bytes(compilation.assembly)
    assembly_data = _json_bytes(
        {
            "canonical_structure_bytes": len(assembly_structure),
            "canonical_structure_sha256": _sha256(assembly_structure),
            "format": "s3-assembly-program-structure-summary",
        }
    )
    try:
        AssemblyVerifier().validate(compilation.assembly)
    except AssemblyError as error:
        raise Stage1ArtifactError("bootstrap Assembly failed independent validation") from error

    output = output_directory.resolve()
    hashes = {
        "assembly_program_structure": {
            "bytes": len(assembly_structure),
            "sha256": _sha256(assembly_structure),
        },
        IR_FILENAME: {"bytes": len(ir_data), "sha256": _sha256(ir_data)},
    }
    provenance = {
        "bootstrap_compiler": "bootstrap.s3.pipeline.compile_sources",
        "bootstrap_source_tree_sha256": _bootstrap_source_tree_sha256(root),
        "build_contract": "Python reference compiler compiles canonical Stage1 S3 modules into verified S3 IR",
        "runtime_contract": "serialized IR is executed by bootstrap.s3.ir_emulator; Stage1 source is not recompiled",
        "stage1_implementation_language": "S3",
    }
    manifest: dict[str, object] = {
        "artifact": {"bytes": len(ir_data), "file": IR_FILENAME, "format": "s3-ir", "sha256": _sha256(ir_data)},
        "artifact_format": ARTIFACT_FORMAT,
        "artifact_version": ARTIFACT_VERSION,
        "assembly_validation": "PASS",
        "entry_function": ENTRY_FUNCTION,
        "entry_signature": {"parameters": ["vector<i64>"], "returns": "vector<i64>"},
        "ir_entry_symbol": entry_symbol,
        "runtime": "python -m bootstrap.s3.stage1_artifact compile",
        "runtime_compiles_source": False,
        "sources": source_metadata,
        "trusted_bootstrap": provenance["bootstrap_compiler"],
    }

    _atomic_write(output / IR_FILENAME, ir_data)
    _atomic_write(output / ASSEMBLY_FILENAME, assembly_data)
    _atomic_write(output / HASHES_FILENAME, _json_bytes(hashes))
    _atomic_write(output / PROVENANCE_FILENAME, _json_bytes(provenance))
    _atomic_write(output / MANIFEST_FILENAME, _json_bytes(manifest))
    return manifest


def _load_stage1_ir(artifact_directory: Path):
    try:
        manifest = json.loads((artifact_directory / MANIFEST_FILENAME).read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise Stage1ArtifactError("invalid Stage1 artifact manifest")
        if manifest.get("artifact_format") != ARTIFACT_FORMAT or manifest.get("artifact_version") != ARTIFACT_VERSION:
            raise Stage1ArtifactError("unsupported Stage1 artifact manifest")
        if (
            manifest.get("entry_function") != ENTRY_FUNCTION
            or manifest.get("entry_signature")
            != {"parameters": ["vector<i64>"], "returns": "vector<i64>"}
            or manifest.get("runtime_compiles_source") is not False
        ):
            raise Stage1ArtifactError("invalid Stage1 entry or runtime contract")
        artifact = manifest.get("artifact")
        if not isinstance(artifact, dict) or artifact.get("file") != IR_FILENAME or artifact.get("format") != "s3-ir":
            raise Stage1ArtifactError("invalid Stage1 artifact descriptor")
        if (
            type(artifact.get("bytes")) is not int
            or not isinstance(artifact.get("sha256"), str)
            or len(artifact["sha256"]) != 64
            or any(character not in "0123456789abcdef" for character in artifact["sha256"])
        ):
            raise Stage1ArtifactError("invalid Stage1 artifact identity")
        entry_symbol = manifest.get("ir_entry_symbol")
        if not isinstance(entry_symbol, str) or not entry_symbol:
            raise Stage1ArtifactError("invalid Stage1 entry symbol")
        data = (artifact_directory / IR_FILENAME).read_bytes()
    except Stage1ArtifactError:
        raise
    except (OSError, json.JSONDecodeError) as error:
        raise Stage1ArtifactError("unable to read Stage1 artifact metadata or IR") from error
    if len(data) != artifact.get("bytes") or _sha256(data) != artifact.get("sha256"):
        raise Stage1ArtifactError("Stage1 IR does not match its manifest identity")
    try:
        module = deserialize_ir(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, S3Error) as error:
        raise Stage1VerificationError("Stage1 IR failed independent verification") from error
    function = next((item for item in module.functions if item.name == entry_symbol), None)
    if (
        function is None
        or len(function.parameters) != 1
        or function.parameters[0].type is not IRType.VECTOR
        or function.return_type is not IRType.VECTOR
    ):
        raise Stage1ArtifactError("Stage1 IR entry signature is incompatible")
    return module, function.name


def compile_stage1_bytes(artifact_directory: Path, source: bytes) -> bytes:
    """Compile bytes with a persisted Stage1 artifact, never the source compiler."""

    if not isinstance(source, bytes):
        raise TypeError("source must be bytes")
    if len(source) > MAX_SOURCE_BYTES:
        raise Stage1Rejected(1, 1)
    module, entry = _load_stage1_ir(artifact_directory)
    source_vector = i64_vector_new(len(source))
    for byte in source:
        source_vector.push(byte)
    try:
        envelope = execute_ir(module, entry, arguments=(source_vector,))
    except IRExecutionError as error:
        raise Stage1ArtifactError("Stage1 artifact execution failed") from error
    if not isinstance(envelope, DynamicVector) or envelope.element_type != "i64" or envelope.length < 4:
        raise Stage1ArtifactError("Stage1 artifact returned an invalid result envelope")
    status, phase, error_code, output_length = (int(envelope.get(index)) for index in range(4))
    if status != 1:
        raise Stage1Rejected(phase, error_code)
    if output_length < 0 or envelope.length != output_length + 4:
        raise Stage1ArtifactError("Stage1 artifact returned an inconsistent output length")
    try:
        output = bytes(int(envelope.get(index)) for index in range(4, envelope.length))
        assembly = parse_assembly(output.decode("ascii"))
        AssemblyVerifier().validate(assembly)
    except (ValueError, UnicodeDecodeError, AssemblyError) as error:
        raise Stage1VerificationError("Stage1 emitted Assembly failed independent validation") from error
    return output


def compile_stage1_file(artifact_directory: Path, source_path: Path, output_path: Path) -> bytes:
    try:
        with source_path.open("rb") as stream:
            source = stream.read(MAX_SOURCE_BYTES + 1)
    except OSError as error:
        raise OSError("unable to read Stage1 input") from error
    output = compile_stage1_bytes(artifact_directory, source)
    try:
        _atomic_write(output_path.resolve(), output)
    except OSError as error:
        raise OSError("unable to write Stage1 output") from error
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="s3-stage1")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="build the canonical Stage1 IR artifact")
    build.add_argument("--output-dir", type=Path, default=Path("build/stage1"))
    invoke = commands.add_parser("compile", help="compile a source file with a built Stage1 artifact")
    invoke.add_argument("artifact_dir", type=Path)
    invoke.add_argument("source", type=Path)
    invoke.add_argument("-o", "--output", type=Path, required=True)
    return parser


def _phase_name(phase: int) -> str:
    return {
        1: "input-validation",
        2: "lexing",
        3: "parsing-or-registration",
        4: "lowering",
        5: "native-ir-verification",
        6: "assembly-emission",
    }.get(phase, "unknown")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            manifest = build_stage1_artifact(args.output_dir)
            print(f"STAGE1_BUILD=PASS IR_SHA256={manifest['artifact']['sha256']}")
            return 0
        output = compile_stage1_file(args.artifact_dir, args.source, args.output)
        print(f"STAGE1_COMPILE=PASS OUTPUT_BYTES={len(output)}")
        return 0
    except Stage1Rejected as error:
        print(
            f"S3E_STAGE1_REJECTED phase={_phase_name(error.phase)} "
            f"phase_id={error.phase} error_code={error.error_code}",
            file=sys.stderr,
        )
        return 1
    except OSError as error:
        code = "S3E_STAGE1_INPUT_IO" if str(error) == "unable to read Stage1 input" else "S3E_STAGE1_OUTPUT_IO"
        print(code, file=sys.stderr)
        return 2
    except Stage1VerificationError as error:
        print(f"S3E_STAGE1_VERIFY: {error}", file=sys.stderr)
        return 2
    except (Stage1ArtifactError, AssemblyError) as error:
        print(f"S3E_STAGE1_ARTIFACT: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
