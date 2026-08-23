"""M2.57 canonical compiler debug serialization contracts."""

from __future__ import annotations

import math

import pytest

from bootstrap.s3.canonical_serialization import (
    CanonicalSerializationError,
    serialize_canonical,
    serialize_debug,
)


def test_canonical_serialization_is_ordered_utf8_and_newline_terminated() -> None:
    first = serialize_canonical({"z": "ação", "a": [2, 1]})
    second = serialize_canonical({"a": [2, 1], "z": "ação"})
    assert first == second
    assert first == '{"a":[2,1],"z":"ação"}\n'
    assert first.endswith("\n")
    assert "\\u" not in first


def test_debug_serialization_has_a_versioned_canonical_envelope() -> None:
    rendered = serialize_debug(
        {"nodes": (2, 1)},
        schema="s3-compiler-debug",
        version="1.0.0",
    )
    assert rendered == (
        '{"schema":"s3-compiler-debug","value":{"nodes":[2,1]},'
        '"version":"1.0.0"}\n'
    )


def test_canonical_serialization_rejects_ambiguous_values() -> None:
    with pytest.raises(CanonicalSerializationError, match="keys must be strings"):
        serialize_canonical({1: "bad"})
    with pytest.raises(CanonicalSerializationError, match="unsupported type"):
        serialize_canonical({"items": {"bad"}})
    with pytest.raises(CanonicalSerializationError, match="non-finite"):
        serialize_canonical(math.nan)


def test_canonical_serialization_fails_closed_before_exceeding_bound() -> None:
    with pytest.raises(CanonicalSerializationError, match="byte limit"):
        serialize_canonical({"message": "é"}, max_bytes=10)
    with pytest.raises(ValueError):
        serialize_debug({}, schema="", version="1.0.0")

