"""Frozen R0 contract helpers for S3 Reliability Lab v2.

This module intentionally contains no compiler execution logic. R1 owns process
isolation and worker execution.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Any

CASE_RESULT_SCHEMA = "s3.reliability.case-result.v2"
CAMPAIGN_REPORT_SCHEMA = "s3.reliability.report.v2"
REPLAY_SCHEMA = "s3.reliability.replay.v2"
WORKER_REQUEST_SCHEMA = "s3.reliability.worker-request.v1"
WORKER_RESPONSE_SCHEMA = "s3.reliability.worker-response.v1"
GENERATOR_PROTOCOL = "s3.reliability.generator.v2"

UINT64_MAX = (1 << 64) - 1
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

OUTCOMES = (
    "PASS",
    "EXPECTED_REJECTION",
    "UNEXPECTED_REJECTION",
    "UNEXPECTED_ACCEPT",
    "MISCOMPILE",
    "CRASH",
    "TIMEOUT",
    "NONDETERMINISM",
    "RESOURCE_LIMIT",
    "HARNESS_ERROR",
)

NON_FAILURE_OUTCOMES = frozenset({"PASS", "EXPECTED_REJECTION"})


@dataclass(frozen=True)
class ResourcePolicy:
    hosted_case_wall_ms: int = 5_000
    native_case_wall_ms: int = 20_000
    kill_grace_ms: int = 250
    stdout_max_bytes: int = 1_048_576
    stderr_max_bytes: int = 1_048_576
    source_max_bytes: int = 32_768
    campaign_max_cases: int = 10_000
    campaign_wall_ms: int = 3_600_000
    max_parallel_children: int = 1
    replay_bundle_max_bytes: int = 4_194_304
    minimizer_max_evaluations: int = 10_000

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


DEFAULT_RESOURCE_POLICY = ResourcePolicy()


def _require_uint64(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < 0 or value > UINT64_MAX:
        raise ValueError(f"{name} must be in [0, 2^64-1]")


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_payload(value: Any) -> bytes:
    """Return canonical JSON bytes without the final newline."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_json_document(value: Any) -> bytes:
    """Return canonical JSON bytes with the required final newline."""
    return canonical_json_payload(value) + b"\n"


def derive_case_seed(
    campaign_seed: int,
    case_index: int,
    generator_version: str,
    case_kind: str,
) -> int:
    _require_uint64(campaign_seed, "campaign_seed")
    if isinstance(case_index, bool) or not isinstance(case_index, int):
        raise TypeError("case_index must be an integer")
    if case_index < 0:
        raise ValueError("case_index must be non-negative")
    if not generator_version:
        raise ValueError("generator_version must not be empty")
    if not case_kind:
        raise ValueError("case_kind must not be empty")

    material = (
        str(campaign_seed).encode("ascii")
        + b"\0"
        + str(case_index).encode("ascii")
        + b"\0"
        + generator_version.encode("utf-8")
        + b"\0"
        + case_kind.encode("utf-8")
    )
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big", signed=False)


def make_case_id(
    campaign_id: str,
    case_index: int,
    case_seed: int,
    generator_version: str,
    case_kind: str,
    source_sha256: str,
) -> str:
    if not campaign_id:
        raise ValueError("campaign_id must not be empty")
    if isinstance(case_index, bool) or not isinstance(case_index, int):
        raise TypeError("case_index must be an integer")
    if case_index < 0:
        raise ValueError("case_index must be non-negative")
    _require_uint64(case_seed, "case_seed")
    if not generator_version:
        raise ValueError("generator_version must not be empty")
    if not case_kind:
        raise ValueError("case_kind must not be empty")
    if not SHA256_RE.fullmatch(source_sha256):
        raise ValueError("source_sha256 must be lowercase SHA-256 hex")

    material = (
        campaign_id.encode("utf-8")
        + b"\0"
        + str(case_index).encode("ascii")
        + b"\0"
        + str(case_seed).encode("ascii")
        + b"\0"
        + generator_version.encode("utf-8")
        + b"\0"
        + case_kind.encode("utf-8")
        + b"\0"
        + source_sha256.encode("ascii")
    )
    return sha256_hex(material)


def encode_source(source: bytes) -> tuple[str, str, int]:
    if len(source) > DEFAULT_RESOURCE_POLICY.source_max_bytes:
        raise ValueError("source exceeds frozen source_max_bytes")
    return (
        base64.b64encode(source).decode("ascii"),
        sha256_hex(source),
        len(source),
    )


def decode_and_verify_source(
    source_b64: str,
    source_sha256: str,
    source_bytes: int,
) -> bytes:
    if not SHA256_RE.fullmatch(source_sha256):
        raise ValueError("source_sha256 must be lowercase SHA-256 hex")
    try:
        decoded = base64.b64decode(source_b64.encode("ascii"), validate=True)
    except Exception as exc:
        raise ValueError("source_b64 is not valid Base64") from exc
    if len(decoded) != source_bytes:
        raise ValueError("source byte count does not match")
    if len(decoded) > DEFAULT_RESOURCE_POLICY.source_max_bytes:
        raise ValueError("source exceeds frozen source_max_bytes")
    if sha256_hex(decoded) != source_sha256:
        raise ValueError("source SHA-256 does not match")
    return decoded


def validate_failure_signature(outcome: str, signature: str | None) -> None:
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown reliability outcome: {outcome}")
    if outcome in NON_FAILURE_OUTCOMES:
        if signature is not None:
            raise ValueError(f"{outcome} must not carry failure_signature")
        return
    if not signature:
        raise ValueError(f"{outcome} requires failure_signature")
    if len(signature) > 512:
        raise ValueError("failure_signature exceeds 512 characters")
    if any(ord(ch) < 32 or ord(ch) > 126 for ch in signature):
        raise ValueError("failure_signature must use printable ASCII only")


def is_relative_bundle_path(path: str) -> bool:
    if not path or "\\" in path:
        return False
    if re.match(r"^[A-Za-z]:", path) or path.startswith("/"):
        return False
    candidate = PurePosixPath(path)
    if candidate.is_absolute() or path == ".":
        return False
    if ".." in candidate.parts:
        return False
    return candidate.as_posix() == path


def validate_relative_bundle_path(path: str) -> None:
    if not is_relative_bundle_path(path):
        raise ValueError("bundle path must be a normalized relative POSIX path")
