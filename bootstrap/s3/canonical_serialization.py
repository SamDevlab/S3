"""Bounded canonical JSON for hosted compiler debug representations."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping


class CanonicalSerializationError(ValueError):
    """Raised when a debug value cannot have a stable canonical encoding."""


def serialize_canonical(value: object, *, max_bytes: int = 16_777_216) -> str:
    """Serialize JSON-shaped compiler data with stable UTF-8 bytes."""

    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int):
        raise TypeError("max_bytes must be an integer")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    _validate_value(value, "value")
    try:
        rendered = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise CanonicalSerializationError("value is not canonically serializable") from exc
    result = rendered + "\n"
    if len(result.encode("utf-8")) > max_bytes:
        raise CanonicalSerializationError("canonical serialization byte limit reached")
    return result


def serialize_debug(
    value: object,
    *,
    schema: str,
    version: str,
    max_bytes: int = 16_777_216,
) -> str:
    """Wrap a debug value in a deterministic, versioned envelope."""

    if not isinstance(schema, str) or not schema:
        raise ValueError("debug schema must be a non-empty string")
    if not isinstance(version, str) or not version:
        raise ValueError("debug version must be a non-empty string")
    return serialize_canonical(
        {"schema": schema, "value": value, "version": version},
        max_bytes=max_bytes,
    )


def _validate_value(value: object, path: str) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        if isinstance(value, int) and not isinstance(value, bool):
            return
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalSerializationError(f"{path} contains a non-finite number")
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CanonicalSerializationError(f"{path} keys must be strings")
            _validate_value(child, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_value(child, f"{path}[{index}]")
        return
    raise CanonicalSerializationError(f"{path} has unsupported type {type(value).__name__}")
