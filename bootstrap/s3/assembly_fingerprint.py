"""Deterministic structural fingerprints for Assembly programs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import fields, is_dataclass
from enum import Enum


def _canonical_assembly_value(value: object) -> object:
    if isinstance(value, Enum):
        return {"enum": type(value).__qualname__, "value": value.value}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _canonical_assembly_value(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, float):
        return {"float_hex": value.hex()}
    if isinstance(value, (tuple, list)):
        return [_canonical_assembly_value(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _canonical_assembly_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if value is None or type(value) in {bool, int, str}:
        return value
    raise TypeError(
        "unsupported AssemblyProgram fingerprint value: "
        f"{type(value)!r}"
    )


def assembly_program_sha256(program: object) -> str:
    """Hash the complete ordered Assembly object graph without text rendering."""
    payload = json.dumps(
        _canonical_assembly_value(program),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
