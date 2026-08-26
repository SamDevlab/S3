from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

import tools.qualify_stage1_final_self_emit as self_emit
from tools.qualify_stage1_final_self_emit import (
    FinalSelfEmitError,
    validate_semantic_ir_dependency,
)


pytestmark = pytest.mark.s3_fast
ROOT = Path(__file__).resolve().parents[1]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _semantic(source: Path, stage1: Path) -> dict[str, object]:
    return {
        "schema": "s3.selfhost.stage1-final-semantic-ir-verifier.v1",
        "canonical_source": {
            "sha256": _sha(source.read_bytes()),
            "bytes": source.stat().st_size,
        },
        "stage1": {
            "sha256": _sha(stage1.read_bytes()),
            "bytes": stage1.stat().st_size,
        },
        "qualification": {
            "semantic_ir": "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET",
            "verifier_v2": "PASS",
            "general_emitter": "PASS_BOOTSTRAP_REQUIRED_OPCODES",
        },
    }


def _files(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    source = tmp_path / "compiler.s3"
    stage1 = tmp_path / "s3c-stage1"
    semantic = tmp_path / "semantic.json"
    host_io = tmp_path / "host.c"
    source.write_bytes(b"fn main() -> tryte:\n    return 0\n")
    stage1.write_bytes(b"synthetic-stage1")
    stage1.chmod(stage1.stat().st_mode | 0o111)
    semantic.write_text(json.dumps(_semantic(source, stage1)), encoding="utf-8")
    host_io.write_text("/* synthetic */\n", encoding="utf-8")
    return source, stage1, semantic, host_io


def test_semantic_dependency_requires_exact_source_stage1_and_passes(tmp_path: Path) -> None:
    source, stage1, _semantic_path, _host_io = _files(tmp_path)
    document = _semantic(source, stage1)
    validate_semantic_ir_dependency(
        document,
        canonical_sha=_sha(source.read_bytes()),
        canonical_bytes=source.stat().st_size,
        stage1_sha=_sha(stage1.read_bytes()),
        stage1_bytes=stage1.stat().st_size,
    )

    document["qualification"]["general_emitter"] = "BLOCKED"  # type: ignore[index]
    with pytest.raises(FinalSelfEmitError, match="general_emitter"):
        validate_semantic_ir_dependency(
            document,
            canonical_sha=_sha(source.read_bytes()),
            canonical_bytes=source.stat().st_size,
            stage1_sha=_sha(stage1.read_bytes()),
            stage1_bytes=stage1.stat().st_size,
        )


def test_semantic_dependency_rejects_stale_source_or_stage1(tmp_path: Path) -> None:
    source, stage1, _semantic_path, _host_io = _files(tmp_path)
    document = _semantic(source, stage1)
    with pytest.raises(FinalSelfEmitError, match="different canonical source"):
        validate_semantic_ir_dependency(
            document,
            canonical_sha="0" * 64,
            canonical_bytes=source.stat().st_size,
            stage1_sha=_sha(stage1.read_bytes()),
            stage1_bytes=stage1.stat().st_size,
        )
    with pytest.raises(FinalSelfEmitError, match="different Stage1 artifact"):
        validate_semantic_ir_dependency(
            document,
            canonical_sha=_sha(source.read_bytes()),
            canonical_bytes=source.stat().st_size,
            stage1_sha="f" * 64,
            stage1_bytes=stage1.stat().st_size,
        )


def _patch_successful_native_flow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(self_emit.platform, "system", lambda: "Linux")
    monkeypatch.setattr(self_emit.platform, "machine", lambda: "x86_64")
    original_which = self_emit.shutil.which
    monkeypatch.setattr(
        self_emit.shutil,
        "which",
        lambda name: "/usr/bin/" + name if name in {"cc", "strace"} else original_which(name),
    )

    def fake_host(_cc: str, _host_io: Path, workspace: Path) -> Path:
        path = workspace / "host.o"
        path.write_bytes(b"host-object")
        return path

    def assembly_for(source: bytes) -> bytes:
        return b"ASM-CANONICAL\n" if source != self_emit.SMOKE_SOURCE else b"ASM-SMOKE\n"

    def fake_trace(_compiler: Path, source: bytes, *, directory: Path, strace: str):
        del strace
        directory.mkdir(parents=True, exist_ok=True)
        assembly = assembly_for(source)
        return {
            "status": "PASS_STRICT_PROCESS_AND_FILE_TRACE",
            "returncode": 0,
            "stdout_sha256": _sha(assembly),
            "stdout_bytes": len(assembly),
            "stderr_sha256": _sha(b""),
            "stderr_bytes": 0,
            "execve_count": 1,
            "execve_lines": ["execve(s3c)"],
            "python_exec_seen": False,
            "forbidden_checkout_or_python_reads": [],
            "trace_path": str(directory / "trace"),
        }

    def fake_replay(_compiler: Path, source: bytes, *, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        return subprocess.CompletedProcess(
            ["synthetic-compiler"], 0, stdout=assembly_for(source), stderr=b""
        )

    def fake_link(
        assembly: bytes,
        *,
        cc: str,
        host_object: Path,
        directory: Path,
        output_name: str,
    ) -> Path:
        del cc, host_object
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / output_name
        # The two canonical self-emits must link to exact bytes. The smoke
        # program may differ but is only required to execute with exit 7.
        payload = b"STAGE2-ELF" if assembly == b"ASM-CANONICAL\n" else b"SMOKE-ELF"
        path.write_bytes(payload)
        path.chmod(path.stat().st_mode | 0o111)
        return path

    def fake_audit(path: Path):
        return {
            "schema": "s3.selfhost.freestanding-elf-audit.v1",
            "status": "PASS_FREESTANDING_STATIC_ELF",
            "artifact": {
                "path": str(path),
                "sha256": _sha(path.read_bytes()),
                "bytes": path.stat().st_size,
            },
        }

    monkeypatch.setattr(self_emit, "_compile_host_object", fake_host)
    monkeypatch.setattr(self_emit, "trace_compiler_sandbox", fake_trace)
    monkeypatch.setattr(self_emit, "_direct_replay", fake_replay)
    monkeypatch.setattr(self_emit, "_assemble_link", fake_link)
    monkeypatch.setattr(self_emit, "audit_elf", fake_audit)
    monkeypatch.setattr(
        self_emit,
        "_run_program",
        lambda path: subprocess.CompletedProcess([str(path)], 7, stdout=b"", stderr=b""),
    )


def test_complete_self_emit_flow_creates_stage2_candidate_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, stage1, semantic, host_io = _files(tmp_path)
    _patch_successful_native_flow(monkeypatch, tmp_path)
    report = tmp_path / "final-self-emit.json"
    result = self_emit.qualify(
        stage1=stage1,
        source=source,
        semantic_ir_report_path=semantic,
        contract_path=ROOT / "reports" / "selfhost" / "stage1" / "final-self-emit-contract.json",
        host_io=host_io,
        report=report,
        workspace=tmp_path / "workspace",
    )
    assert result["schema"] == "s3.selfhost.stage1-final-self-emit.v1"
    assert result["self_emit"]["assembly_bytes_equal"] is True
    assert result["stage2"]["elf_bytes_equal"] is True
    assert result["stage2_smoke"]["status"] == "PASS"
    assert result["stage2_smoke"]["program_exit"] == 7
    assert result["qualification"]["self_emit"] == "PASS"
    assert result["qualification"]["stage1_certified_candidate"] is True
    assert result["qualification"]["stage2_artifact_created"] is True
    assert result["qualification"]["stage2_certified"] is False
    assert result["qualification"]["stage3_started"] is False
    assert result["qualification"]["full_self_hosting"] is False
    assert report.is_file()


def test_nondeterministic_self_emit_assembly_blocks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, stage1, semantic, host_io = _files(tmp_path)
    _patch_successful_native_flow(monkeypatch, tmp_path)
    calls = 0

    def nondeterministic_replay(_compiler: Path, source_bytes: bytes, *, directory: Path):
        nonlocal calls
        directory.mkdir(parents=True, exist_ok=True)
        calls += 1
        if source_bytes == self_emit.SMOKE_SOURCE:
            output = b"ASM-SMOKE\n"
        else:
            output = b"ASM-CANONICAL\n" if calls == 1 else b"ASM-CANONICAL-DIFFERENT\n"
        return subprocess.CompletedProcess(["synthetic-compiler"], 0, stdout=output, stderr=b"")

    # The second replay no longer matches its strict-trace output, so the gate
    # must fail before linking any divergent Stage2 artifact.
    monkeypatch.setattr(self_emit, "_direct_replay", nondeterministic_replay)
    with pytest.raises(FinalSelfEmitError, match="trace/replay assembly"):
        self_emit.qualify(
            stage1=stage1,
            source=source,
            semantic_ir_report_path=semantic,
            contract_path=ROOT / "reports" / "selfhost" / "stage1" / "final-self-emit-contract.json",
            host_io=host_io,
            report=tmp_path / "final-self-emit.json",
            workspace=tmp_path / "workspace",
        )


def test_stage2_smoke_must_execute_expected_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, stage1, semantic, host_io = _files(tmp_path)
    _patch_successful_native_flow(monkeypatch, tmp_path)
    monkeypatch.setattr(
        self_emit,
        "_run_program",
        lambda path: subprocess.CompletedProcess([str(path)], 6, stdout=b"", stderr=b""),
    )
    with pytest.raises(FinalSelfEmitError, match="expected 7"):
        self_emit.qualify(
            stage1=stage1,
            source=source,
            semantic_ir_report_path=semantic,
            contract_path=ROOT / "reports" / "selfhost" / "stage1" / "final-self-emit-contract.json",
            host_io=host_io,
            report=tmp_path / "final-self-emit.json",
            workspace=tmp_path / "workspace",
        )
