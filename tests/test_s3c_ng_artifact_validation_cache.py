from __future__ import annotations

import hashlib
import json
import os
import struct
from pathlib import Path

from bootstrap.s3 import native_compiler
from bootstrap.s3 import s3c_ng_distribution
from bootstrap.s3.compiler_ng_ir_bridge import NG_IR_FORMAT_VERSION


def _write_artifact(directory: Path, payload: bytes | None = None) -> tuple[Path, dict[str, object]]:
    executable = directory / "s3c-ng"
    artifact = bytearray(64) if payload is None else bytearray(payload)
    artifact[:4] = b"\x7fELF"
    artifact[4] = 2
    artifact[5] = 1
    struct.pack_into("<H", artifact, 18, 62)
    executable.write_bytes(artifact)
    digest = hashlib.sha256(artifact).hexdigest()
    manifest: dict[str, object] = {
        "schema_version": 2,
        "target": "linux-x86_64",
        "ng_ir_format_version": NG_IR_FORMAT_VERSION,
        "entry_module": "app",
        "entry_symbol": "ng_emit_source_set_v2",
        "optimization_mode": "O0",
        "artifact_sha256": digest,
        "artifact_bytes": len(artifact),
        "source_commit": "0" * 40,
        "source_graph_sha256": "1" * 64,
        "compiler_ir_sha256": "2" * 64,
        "assembly_sha256": "3" * 64,
        "object_sha256": "4" * 64,
        "toolchain": {"compiler": "cc", "version": "test"},
        "bootstrap_parent": {
            "kind": "python-reference-stage0",
            "canonical_ir_sha256": "2" * 64,
        },
    }
    _write_manifest(executable, manifest)
    return executable, manifest


def _write_manifest(executable: Path, manifest: dict[str, object]) -> None:
    executable.with_suffix(".manifest.json").write_text(
        json.dumps(manifest, sort_keys=True), encoding="utf-8"
    )


def _enable_linux_artifact_inspection(monkeypatch, *, pin_checks: list[Path] | None = None) -> None:
    monkeypatch.setattr(native_compiler.platform, "system", lambda: "Linux")
    monkeypatch.setattr(native_compiler.platform, "machine", lambda: "x86_64")
    if pin_checks is None:
        pin_checks = []
    monkeypatch.setattr(
        s3c_ng_distribution,
        "verify_default_artifact",
        lambda path: pin_checks.append(path) or None,
    )


def _count_raw_hashes(monkeypatch) -> list[Path]:
    original = native_compiler._sha256_file
    calls: list[Path] = []

    def counted(path: Path) -> str:
        calls.append(path)
        return original(path)

    monkeypatch.setattr(native_compiler, "_sha256_file", counted)
    return calls


def test_repeated_validation_reuses_only_the_fully_validated_hash(tmp_path, monkeypatch) -> None:
    executable, _ = _write_artifact(tmp_path)
    pin_checks: list[Path] = []
    hashes = _count_raw_hashes(monkeypatch)
    _enable_linux_artifact_inspection(monkeypatch, pin_checks=pin_checks)

    assert native_compiler.inspect_s3c_ng_executable(executable).available
    assert native_compiler.inspect_s3c_ng_executable(executable).available

    assert hashes == [executable]
    assert pin_checks == [executable.resolve(), executable.resolve()]


def test_executable_replacement_and_manifest_change_invalidate_hash(tmp_path, monkeypatch) -> None:
    executable, manifest = _write_artifact(tmp_path)
    hashes = _count_raw_hashes(monkeypatch)
    _enable_linux_artifact_inspection(monkeypatch)

    assert native_compiler.inspect_s3c_ng_executable(executable).available
    assert native_compiler.inspect_s3c_ng_executable(executable).available
    assert len(hashes) == 1

    replacement = tmp_path / "replacement"
    changed_payload = bytearray(executable.read_bytes())
    changed_payload[-1] ^= 1
    replacement.write_bytes(changed_payload)
    os.replace(replacement, executable)

    stale_manifest = native_compiler.inspect_s3c_ng_executable(executable)
    assert not stale_manifest.available
    assert "manifest" in (stale_manifest.reason or "") or "contract" in (stale_manifest.reason or "")
    assert len(hashes) == 2

    manifest["artifact_sha256"] = hashlib.sha256(executable.read_bytes()).hexdigest()
    _write_manifest(executable, manifest)
    assert native_compiler.inspect_s3c_ng_executable(executable).available
    assert len(hashes) == 3

    manifest["toolchain"] = {"compiler": "cc", "version": "updated"}
    _write_manifest(executable, manifest)
    assert native_compiler.inspect_s3c_ng_executable(executable).available
    assert len(hashes) == 4


def test_initial_sha_mismatch_is_rejected_and_never_cached(tmp_path, monkeypatch) -> None:
    executable, manifest = _write_artifact(tmp_path)
    manifest["artifact_sha256"] = "f" * 64
    _write_manifest(executable, manifest)
    hashes = _count_raw_hashes(monkeypatch)
    _enable_linux_artifact_inspection(monkeypatch)

    first = native_compiler.inspect_s3c_ng_executable(executable)
    second = native_compiler.inspect_s3c_ng_executable(executable)

    assert not first.available
    assert not second.available
    assert "manifest" in (first.reason or "") or "contract" in (first.reason or "")
    assert hashes == [executable, executable]
