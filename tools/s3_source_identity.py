"""Canonical source-byte identity shared by S3 research reports."""

from __future__ import annotations

from hashlib import sha256


def canonical_source_sha256(source_bytes: bytes) -> str:
    """Hash UTF-8 source with Git-style LF line endings on every host."""

    if not isinstance(source_bytes, bytes):
        raise TypeError("source_bytes must be bytes")
    return sha256(source_bytes.replace(b"\r\n", b"\n")).hexdigest()
