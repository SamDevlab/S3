"""Canonical source-manifest and Git blob authority for self-hosting gates."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from tools.selfhost_contract_authority import require_authoritative_contract


class SourceAuthorityError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_authoritative_source_manifest(
    candidate: Path,
    *,
    authoritative: Path,
    root: Path,
) -> tuple[Path, bytes, dict[str, Any], dict[str, Any]]:
    """Require the exact committed canonical manifest and validate its source."""

    document, generic_binding = require_authoritative_contract(
        candidate,
        authoritative=authoritative,
        expected_schema="s3.compiler.sources.v1",
        label="canonical compiler source manifest",
    )
    sources = document.get("sources")
    if not isinstance(sources, list) or len(sources) != 1:
        raise SourceAuthorityError(
            "canonical compiler source manifest must contain exactly one source"
        )
    if document.get("source_count") != 1:
        raise SourceAuthorityError("canonical compiler source_count must be exactly 1")
    entry = sources[0]
    if not isinstance(entry, dict):
        raise SourceAuthorityError("canonical compiler source entry must be an object")
    relative = entry.get("path")
    expected_sha = entry.get("sha256")
    if not isinstance(relative, str) or not relative:
        raise SourceAuthorityError("canonical compiler source entry lacks path")
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        raise SourceAuthorityError("canonical compiler source entry lacks valid SHA256")
    if entry.get("role") != "canonical_stage1_compiler":
        raise SourceAuthorityError("canonical compiler source role mismatch")
    if entry.get("ordering") != 0:
        raise SourceAuthorityError("canonical compiler source ordering must be zero")

    root_resolved = root.resolve()
    source_path = (root_resolved / relative).resolve()
    try:
        source_path.relative_to(root_resolved)
    except ValueError as error:
        raise SourceAuthorityError("canonical compiler source path escapes repository root") from error
    try:
        source = source_path.read_bytes()
    except OSError as error:
        raise SourceAuthorityError(
            f"canonical compiler source is unavailable: {source_path}"
        ) from error
    actual_sha = _sha256(source)
    if actual_sha != expected_sha:
        raise SourceAuthorityError(
            f"canonical compiler source SHA mismatch: manifest={expected_sha} actual={actual_sha}"
        )
    if document.get("total_bytes") != len(source):
        raise SourceAuthorityError("canonical compiler source byte count differs from manifest")

    binding = {
        **generic_binding,
        "status": "PASS_CANONICAL_SOURCE_MANIFEST_AUTHORITY",
        "source": {
            "path": relative,
            "resolved_path": str(source_path),
            "sha256": actual_sha,
            "bytes": len(source),
            "role": entry["role"],
            "ordering": entry["ordering"],
        },
    }
    return source_path, source, document, binding


def _run_git(root: Path, args: list[str]) -> bytes:
    completed = subprocess.run(
        ["git", *args],
        cwd=str(root.resolve()),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise SourceAuthorityError(
            f"git {' '.join(args)} failed with {completed.returncode}: {detail}"
        )
    return completed.stdout


def verify_git_commit_source_binding(
    *,
    commit: str,
    source_path: Path,
    source: bytes,
    root: Path,
) -> dict[str, Any]:
    """Re-open the exact source blob from an actual Git commit and compare bytes."""

    if len(commit) != 40 or any(char not in "0123456789abcdefABCDEF" for char in commit):
        raise SourceAuthorityError("canonical source commit must be a 40-digit hexadecimal Git SHA")
    root_resolved = root.resolve()
    source_resolved = source_path.resolve()
    try:
        relative = source_resolved.relative_to(root_resolved).as_posix()
    except ValueError as error:
        raise SourceAuthorityError("canonical source path escapes repository root") from error

    object_type = _run_git(root_resolved, ["cat-file", "-t", commit]).decode(
        "ascii", errors="strict"
    ).strip()
    if object_type != "commit":
        raise SourceAuthorityError(
            f"canonical source Git object must be a commit, got {object_type!r}"
        )
    committed_source = _run_git(root_resolved, ["show", f"{commit}:{relative}"])
    if committed_source != source:
        raise SourceAuthorityError(
            "canonical source bytes differ from the blob stored at the declared Git commit"
        )
    return {
        "status": "PASS_CANONICAL_SOURCE_GIT_COMMIT_BINDING",
        "commit": commit.lower(),
        "path": relative,
        "sha256": _sha256(source),
        "bytes": len(source),
        "git_object_type": object_type,
        "commit_blob_bytes_equal": True,
    }
