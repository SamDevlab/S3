"""Fail-closed authority binding for final self-hosting JSON policies.

Final certification CLIs may expose policy paths for portability or explicit
invocation, but those paths must not become policy overrides. An alternate path
is accepted only when its exact bytes are identical to the repository's
canonical authoritative file and both documents carry the expected schema.

When the canonical authority lives inside a Git checkout, the helper also
requires the working-tree bytes to equal the exact blob stored at the current
HEAD. This prevents an uncommitted policy edit from silently weakening final
certification. Callers may pass ``git_root`` explicitly; otherwise the helper
walks upward from the authoritative file and auto-detects ``.git``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


class ContractAuthorityError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _decode_json_object(data: bytes, *, label: str) -> dict[str, Any]:
    try:
        document = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ContractAuthorityError(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(document, dict):
        raise ContractAuthorityError(f"{label} must be a JSON object")
    return document


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
        raise ContractAuthorityError(
            f"git {' '.join(args)} failed with {completed.returncode}: {detail}"
        )
    return completed.stdout


def _discover_git_root(path: Path) -> Path | None:
    current = path.resolve().parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _git_head_file_binding(path: Path, *, root: Path, label: str) -> dict[str, Any]:
    root_resolved = root.resolve()
    path_resolved = path.resolve()
    try:
        relative = path_resolved.relative_to(root_resolved).as_posix()
    except ValueError as error:
        raise ContractAuthorityError(
            f"authoritative {label} must be inside repository root"
        ) from error

    head = _run_git(root_resolved, ["rev-parse", "HEAD"]).decode(
        "ascii", errors="strict"
    ).strip()
    if len(head) != 40 or any(char not in "0123456789abcdefABCDEF" for char in head):
        raise ContractAuthorityError(f"unexpected Git HEAD for authoritative {label}: {head!r}")
    object_type = _run_git(root_resolved, ["cat-file", "-t", head]).decode(
        "ascii", errors="strict"
    ).strip()
    if object_type != "commit":
        raise ContractAuthorityError(
            f"Git HEAD for authoritative {label} must resolve to a commit"
        )
    committed = _run_git(root_resolved, ["show", f"{head}:{relative}"])
    working = path_resolved.read_bytes()
    if committed != working:
        raise ContractAuthorityError(
            f"authoritative {label} differs from its Git HEAD blob; commit/freeze policy before certification"
        )
    return {
        "status": "PASS_REPOSITORY_FILE_GIT_HEAD_BINDING",
        "commit": head.lower(),
        "path": relative,
        "sha256": _sha256(working),
        "bytes": len(working),
        "git_object_type": object_type,
        "working_tree_equals_head_blob": True,
    }


def require_authoritative_contract(
    candidate: Path,
    *,
    authoritative: Path,
    expected_schema: str,
    label: str,
    git_root: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return candidate policy only when it equals canonical authority bytes."""

    candidate_path = candidate.resolve()
    authoritative_path = authoritative.resolve()
    try:
        authoritative_bytes = authoritative_path.read_bytes()
    except OSError as error:
        raise ContractAuthorityError(
            f"authoritative {label} is unavailable: {authoritative_path}"
        ) from error
    try:
        candidate_bytes = candidate_path.read_bytes()
    except OSError as error:
        raise ContractAuthorityError(f"{label} is unavailable: {candidate_path}") from error

    authoritative_document = _decode_json_object(
        authoritative_bytes,
        label=f"authoritative {label}",
    )
    candidate_document = _decode_json_object(candidate_bytes, label=label)
    if authoritative_document.get("schema") != expected_schema:
        raise ContractAuthorityError(
            f"authoritative {label} schema mismatch: "
            f"expected={expected_schema!r} actual={authoritative_document.get('schema')!r}"
        )
    if candidate_document.get("schema") != expected_schema:
        raise ContractAuthorityError(
            f"{label} schema mismatch: "
            f"expected={expected_schema!r} actual={candidate_document.get('schema')!r}"
        )

    authoritative_sha = _sha256(authoritative_bytes)
    candidate_sha = _sha256(candidate_bytes)
    if candidate_bytes != authoritative_bytes or candidate_sha != authoritative_sha:
        raise ContractAuthorityError(
            f"{label} is not the canonical authoritative policy: "
            f"expected_sha256={authoritative_sha} actual_sha256={candidate_sha}"
        )

    effective_git_root = git_root if git_root is not None else _discover_git_root(authoritative_path)
    git_head_binding = (
        _git_head_file_binding(authoritative_path, root=effective_git_root, label=label)
        if effective_git_root is not None
        else None
    )
    binding = {
        "status": "PASS_CANONICAL_CONTRACT_AUTHORITY",
        "label": label,
        "schema": expected_schema,
        "candidate_path": str(candidate_path),
        "authoritative_path": str(authoritative_path),
        "sha256": authoritative_sha,
        "bytes": len(authoritative_bytes),
        "exact_bytes_equal": True,
    }
    if git_head_binding is not None:
        binding["git_head_binding"] = git_head_binding
    return candidate_document, binding
