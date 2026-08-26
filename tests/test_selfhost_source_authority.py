from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import tools.selfhost_source_authority as authority
from tools.selfhost_contract_authority import ContractAuthorityError
from tools.selfhost_source_authority import (
    SourceAuthorityError,
    require_authoritative_source_manifest,
    verify_git_commit_source_binding,
)


pytestmark = pytest.mark.s3_fast


def _manifest(path: str, payload: bytes) -> dict[str, object]:
    return {
        "schema": "s3.compiler.sources.v1",
        "source_count": 1,
        "total_bytes": len(payload),
        "sources": [
            {
                "path": path,
                "sha256": hashlib.sha256(payload).hexdigest(),
                "role": "canonical_stage1_compiler",
                "ordering": 0,
            }
        ],
    }


def _write_json(path: Path, document: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def test_canonical_manifest_binds_exact_source_bytes(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source = root / "compiler.s3"
    source.parent.mkdir(parents=True)
    payload = b"fn main() -> tryte:\n    return 7\n"
    source.write_bytes(payload)
    manifest = root / "compiler-sources.json"
    _write_json(manifest, _manifest("compiler.s3", payload))

    path, data, document, binding = require_authoritative_source_manifest(
        manifest,
        authoritative=manifest,
        root=root,
    )
    assert path == source.resolve()
    assert data == payload
    assert document["source_count"] == 1
    assert binding["status"] == "PASS_CANONICAL_SOURCE_MANIFEST_AUTHORITY"
    assert binding["source"]["sha256"] == hashlib.sha256(payload).hexdigest()
    assert binding["source"]["bytes"] == len(payload)


def test_same_schema_but_weakened_or_changed_manifest_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    payload = b"canonical"
    (root / "compiler.s3").write_bytes(payload)
    authoritative = root / "authority.json"
    candidate = root / "candidate.json"
    _write_json(authoritative, _manifest("compiler.s3", payload))
    changed = _manifest("compiler.s3", payload)
    changed["total_bytes"] = len(payload) + 1
    _write_json(candidate, changed)

    with pytest.raises(ContractAuthorityError, match="canonical authoritative policy"):
        require_authoritative_source_manifest(
            candidate,
            authoritative=authoritative,
            root=root,
        )


def test_manifest_source_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    payload = b"canonical"
    (root / "compiler.s3").write_bytes(payload + b"-mutated")
    manifest = root / "manifest.json"
    _write_json(manifest, _manifest("compiler.s3", payload))

    with pytest.raises(SourceAuthorityError, match="source SHA mismatch"):
        require_authoritative_source_manifest(
            manifest,
            authoritative=manifest,
            root=root,
        )


def test_manifest_source_path_cannot_escape_repository(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.s3"
    payload = b"outside"
    outside.write_bytes(payload)
    manifest = root / "manifest.json"
    _write_json(manifest, _manifest("../outside.s3", payload))

    with pytest.raises(SourceAuthorityError, match="escapes repository root"):
        require_authoritative_source_manifest(
            manifest,
            authoritative=manifest,
            root=root,
        )


def test_git_commit_binding_reopens_exact_blob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "compiler.s3"
    payload = b"canonical-source"
    commit = "a" * 40
    calls: list[list[str]] = []

    def fake_run_git(call_root: Path, args: list[str]) -> bytes:
        assert call_root.resolve() == root.resolve()
        calls.append(args)
        if args[:2] == ["cat-file", "-t"]:
            return b"commit\n"
        if args[0] == "show":
            return payload
        raise AssertionError(args)

    monkeypatch.setattr(authority, "_run_git", fake_run_git)
    binding = verify_git_commit_source_binding(
        commit=commit,
        source_path=source,
        source=payload,
        root=root,
    )
    assert binding["status"] == "PASS_CANONICAL_SOURCE_GIT_COMMIT_BINDING"
    assert binding["commit_blob_bytes_equal"] is True
    assert calls == [
        ["cat-file", "-t", commit],
        ["show", f"{commit}:compiler.s3"],
    ]


def test_git_object_must_be_commit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "compiler.s3"
    monkeypatch.setattr(authority, "_run_git", lambda root, args: b"tree\n")
    with pytest.raises(SourceAuthorityError, match="must be a commit"):
        verify_git_commit_source_binding(
            commit="b" * 40,
            source_path=source,
            source=b"canonical",
            root=root,
        )


def test_git_commit_blob_must_equal_certified_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "compiler.s3"

    def fake_run_git(call_root: Path, args: list[str]) -> bytes:
        del call_root
        return b"commit\n" if args[:2] == ["cat-file", "-t"] else b"different"

    monkeypatch.setattr(authority, "_run_git", fake_run_git)
    with pytest.raises(SourceAuthorityError, match="differ from the blob"):
        verify_git_commit_source_binding(
            commit="c" * 40,
            source_path=source,
            source=b"canonical",
            root=root,
        )


def test_git_commit_sha_must_be_full_hex(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    with pytest.raises(SourceAuthorityError, match="40-digit hexadecimal"):
        verify_git_commit_source_binding(
            commit="z" * 40,
            source_path=root / "compiler.s3",
            source=b"canonical",
            root=root,
        )
