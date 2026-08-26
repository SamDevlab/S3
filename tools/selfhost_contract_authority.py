"""Fail-closed authority binding for final self-hosting JSON contracts.

Final certification CLIs may expose a contract path for portability or explicit
invocation, but the path must not become a policy override. This module accepts
an alternate path only when its exact bytes are identical to the repository's
canonical authoritative contract and both documents carry the expected schema.
"""

from __future__ import annotations

import hashlib
import json
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


def require_authoritative_contract(
    candidate: Path,
    *,
    authoritative: Path,
    expected_schema: str,
    label: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the candidate document only when it equals canonical policy bytes."""

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

    return candidate_document, {
        "status": "PASS_CANONICAL_CONTRACT_AUTHORITY",
        "label": label,
        "schema": expected_schema,
        "candidate_path": str(candidate_path),
        "authoritative_path": str(authoritative_path),
        "sha256": authoritative_sha,
        "bytes": len(authoritative_bytes),
        "exact_bytes_equal": True,
    }
