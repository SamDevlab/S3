from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

import bootstrap.s3.compiler_provider as compiler_provider
import bootstrap.s3.native_compiler as native_compiler
from bootstrap.s3.compiler_provider import (
    CompilerKind,
    NativeCompilationResult,
    compilation_requires_ir_execution,
    compile_source_set_with_provider,
)
from bootstrap.s3.ir import IRBasicBlock, IRFunction, IRInstruction, IRModule, IROpcode, IRRegister, IRType
from bootstrap.s3.native_compiler import (
    NativeS3CTransportError,
    NativeSourceSetResult,
    encode_source_manifest,
    inspect_s3c_ng_executable,
)
from bootstrap.s3.pipeline import CompilationResult, compile_source
from tools.native_s3c_ng import compiler_source_graph_sha256, write_s3c_ng_candidate_manifest


def test_python_remains_the_initial_default_compiler() -> None:
    result = compiler_provider.compile_with_provider(
        "fn main() -> i64:\n    return 7\n"
    )

    assert compiler_provider.DEFAULT_COMPILER is CompilerKind.PYTHON
    assert isinstance(result, CompilationResult)


def test_s3c_ng_provider_uses_native_ir_without_python_semantic_compilation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = compile_source("fn main() -> i64:\n    return 7\n").ir
    assert expected is not None
    native_result = NativeSourceSetResult(
        status=0,
        source=b"transported source",
        events=(1, 2, 3),
        returncode=0,
        stdout=b"",
        stderr=b"",
        output_envelope_sha256="0" * 64,
        output_envelope_bytes=32,
        elapsed_seconds=0.01,
    )

    monkeypatch.setattr(
        compiler_provider,
        "require_s3c_ng_executable",
        lambda _path: SimpleNamespace(executable=Path("s3c-ng"), entry_symbol="emit"),
    )
    monkeypatch.setattr(
        compiler_provider,
        "run_native_source_set",
        lambda *_args, **_kwargs: native_result,
    )
    monkeypatch.setattr(
        compiler_provider,
        "decode_ng_ir_events",
        lambda source, events: expected
        if source == native_result.source and events == native_result.events
        else pytest.fail("native output was not decoded as returned"),
    )

    def forbidden(*_args, **_kwargs):
        pytest.fail("S3C-NG mode must not invoke Python semantic compilation")

    monkeypatch.setattr(compiler_provider, "compile_source", forbidden)
    monkeypatch.setattr(compiler_provider, "compile_sources", forbidden)

    result = compile_source_set_with_provider(
        {"main.s3": "fn main() -> i64:\n    return 7\n"},
        compiler=CompilerKind.S3C_NG,
    )

    assert result.compiler is CompilerKind.S3C_NG
    assert result.ir == expected
    assert result.assembly.functions


def test_s3c_ng_failure_does_not_fall_back_to_python(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(_path=None):
        raise NativeS3CTransportError("S3C-NG artifact unavailable")

    def forbidden(*_args, **_kwargs):
        pytest.fail("explicit S3C-NG request silently fell back to Python")

    monkeypatch.setattr(compiler_provider, "require_s3c_ng_executable", unavailable)
    monkeypatch.setattr(compiler_provider, "compile_source", forbidden)
    monkeypatch.setattr(compiler_provider, "compile_sources", forbidden)

    with pytest.raises(NativeS3CTransportError, match="artifact unavailable"):
        compile_source_set_with_provider(
            {"main.s3": "fn main() -> i64:\n    return 7\n"},
            compiler="s3c-ng",
        )


def test_s3c_ng_rejects_unsupported_source_syntax_before_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        compiler_provider,
        "require_s3c_ng_executable",
        lambda *_args: pytest.fail("unsupported syntax must fail before artifact lookup"),
    )

    with pytest.raises(NativeS3CTransportError, match="syntax 0.6 only"):
        compile_source_set_with_provider(
            {"main.s3": "fn main() -> tryte { return 0; }"},
            compiler="s3c-ng",
            mode=compiler_provider.SyntaxMode.V0_5,
        )


def test_native_source_manifest_is_independent_of_mapping_insertion_order() -> None:
    first = encode_source_manifest(
        {"z/module.s3": "module z", "a/module.s3": "module a"},
        "a",
    )
    second = encode_source_manifest(
        {"a/module.s3": "module a", "z/module.s3": "module z"},
        "a",
    )

    assert first == second


def test_ir_provider_uses_conservative_optimizer_for_reference_and_dynamic_ir() -> None:
    scalar_ir = compile_source("fn main() -> i64:\n    return 7\n").ir
    assert scalar_ir is not None
    assert not compiler_provider._requires_conservative_optimization(scalar_ir)

    reference_ir = IRModule(
        (
            IRFunction(
                "reference_case",
                (),
                IRType.I64,
                (IRRegister(0, IRType.REFERENCE),),
                (IRBasicBlock("entry", ()),),
            ),
        )
    )
    assert compiler_provider._requires_conservative_optimization(reference_ir)

    dynamic_ir = IRModule(
        (
            IRFunction(
                "dynamic_case",
                (),
                IRType.I64,
                (),
                (
                    IRBasicBlock(
                        "entry",
                        (IRInstruction(IROpcode.CALL, callee="text_new"),),
                    ),
                ),
            ),
        )
    )
    assert compiler_provider._requires_conservative_optimization(dynamic_ir)


def test_hosted_executor_selection_uses_native_ir_value_model() -> None:
    scalar = compile_source("fn main() -> i64:\n    return 7\n")
    assert scalar.ir is not None
    assert not compilation_requires_ir_execution(scalar)

    reference_ir = IRModule(
        (
            IRFunction(
                "reference_case",
                (),
                IRType.I64,
                (IRRegister(0, IRType.REFERENCE),),
                (IRBasicBlock("entry", ()),),
            ),
        )
    )
    native_reference = NativeCompilationResult(
        reference_ir,
        scalar.assembly,
        SimpleNamespace(),
    )
    assert compilation_requires_ir_execution(native_reference)
    native_scalar = NativeCompilationResult(scalar.ir, scalar.assembly, SimpleNamespace())
    assert not compilation_requires_ir_execution(native_scalar)


def test_candidate_manifest_is_deterministic_and_discloses_reference_seed(
    tmp_path: Path,
) -> None:
    sources_a = {"z.s3": "module z", "a.s3": "module a"}
    sources_b = {"a.s3": "module a", "z.s3": "module z"}
    graph_hash = compiler_source_graph_sha256(sources_a)
    artifact = SimpleNamespace(
        entry_symbol="ng_emit_source_set",
        executable_sha256="1" * 64,
        executable_bytes=4096,
        compiler_ir_sha256="2" * 64,
        assembly_sha256="3" * 64,
        object_sha256="4" * 64,
        toolchain=SimpleNamespace(
            compiler="/usr/bin/cc",
            assembler="/usr/bin/as",
            linker="/usr/bin/ld",
        ),
    )
    manifest_path = tmp_path / "s3c-ng.manifest.json"

    write_s3c_ng_candidate_manifest(
        artifact,
        manifest_path,
        source_commit="a" * 40,
        source_graph_sha256=graph_hash,
        toolchain_version="cc test version",
        bootstrap_parent_ir_sha256="2" * 64,
    )
    first = manifest_path.read_bytes()
    write_s3c_ng_candidate_manifest(
        artifact,
        manifest_path,
        source_commit="a" * 40,
        source_graph_sha256=compiler_source_graph_sha256(sources_b),
        toolchain_version="cc test version",
        bootstrap_parent_ir_sha256="2" * 64,
    )

    assert first == manifest_path.read_bytes()
    manifest = json.loads(first)
    assert manifest["bootstrap_parent"]["kind"] == "python-reference-stage0"
    assert manifest["source_graph_sha256"] == graph_hash


def test_native_executable_manifest_is_fail_closed_and_hash_bound(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(native_compiler.platform, "system", lambda: "Linux")
    monkeypatch.setattr(native_compiler.platform, "machine", lambda: "x86_64")
    executable = tmp_path / "s3c-ng"
    header = bytearray(20)
    header[:4] = b"\x7fELF"
    header[4] = 2
    header[5] = 1
    struct.pack_into("<H", header, 18, 62)
    executable.write_bytes(header)
    artifact_sha = hashlib.sha256(header).hexdigest()
    ir_sha = "2" * 64
    manifest = {
        "schema_version": 2,
        "target": "linux-x86_64",
        "ng_ir_format_version": 22,
        "entry_symbol": "ng_emit_source_set",
        "entry_module": "app",
        "optimization_mode": "O0",
        "artifact_sha256": artifact_sha,
        "artifact_bytes": len(header),
        "source_commit": "a" * 40,
        "source_graph_sha256": "1" * 64,
        "compiler_ir_sha256": ir_sha,
        "assembly_sha256": "3" * 64,
        "object_sha256": "4" * 64,
        "toolchain": {"compiler": "cc", "version": "cc version"},
        "bootstrap_parent": {
            "kind": "python-reference-stage0",
            "canonical_ir_sha256": ir_sha,
        },
    }
    manifest_path = executable.with_suffix(".manifest.json")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert inspect_s3c_ng_executable(executable).available

    manifest["artifact_sha256"] = "f" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    unavailable = inspect_s3c_ng_executable(executable)
    assert not unavailable.available
    assert "does not match" in (unavailable.reason or "")
