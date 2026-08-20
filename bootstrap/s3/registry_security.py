"""Shared bounded security helpers for offline registry documents."""

from __future__ import annotations

from pathlib import Path
import re
from urllib.parse import urlsplit


_HOST_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def canonical_https_origin(origin: str) -> str:
    if not isinstance(origin, str) or not origin or any(character.isspace() or ord(character) < 32 for character in origin):
        raise ValueError("registry origin contains whitespace or control characters")
    try:
        parsed = urlsplit(origin)
        port = parsed.port
    except ValueError as error:
        raise ValueError("registry origin has an invalid port") from error
    if parsed.scheme != "https" or parsed.username is not None or parsed.password is not None:
        raise ValueError("registry origin must be HTTPS without userinfo")
    if parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise ValueError("registry origin cannot contain a path, query, or fragment")
    hostname = parsed.hostname
    if hostname is None or hostname != hostname.lower() or "." not in hostname:
        raise ValueError("registry origin hostname must be a lowercase DNS name")
    labels = hostname.split(".")
    if any(not _HOST_LABEL.fullmatch(label) for label in labels):
        raise ValueError("registry origin hostname is not a valid DNS name")
    if port not in {None, 443}:
        raise ValueError("registry origin port must be the HTTPS default")
    if parsed.path == "/":
        raise ValueError("registry origin must not have a trailing slash")
    return f"https://{hostname}"


def read_bounded_bytes(path: Path, limit: int, *, label: str) -> bytes:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError(f"{label} byte limit must be positive")
    try:
        with Path(path).open("rb") as stream:
            body = stream.read(limit + 1)
    except OSError as error:
        raise ValueError(f"{label} cannot be read") from error
    if len(body) > limit:
        raise ValueError(f"{label} exceeds byte limit")
    return body
