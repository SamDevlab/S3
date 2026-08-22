from __future__ import annotations

import pytest

from bootstrap.s3.debug_info import DebugInfo, DebugInfoError, DebugRange, DebugSymbol


def test_debug_info_is_backend_neutral_and_deterministic() -> None:
    mapping = DebugRange("main.s3", 2, 5, 10, 12, 100, 108)
    symbol = DebugSymbol("main", "main", "main.s3", 1, 4)
    info = DebugInfo((mapping,), (symbol,))
    assert info.payload["format"] == "s3.debug-info.v1"
    assert info.digest == DebugInfo((mapping,), (symbol,)).digest
    assert "native_start" in info.text


def test_debug_info_rejects_partial_or_noncanonical_ranges() -> None:
    with pytest.raises(DebugInfoError, match="native range"):
        DebugRange("main.s3", 1, 1, 0, 1, 4, None)
    first = DebugRange("b.s3", 1, 1, 0, 1)
    second = DebugRange("a.s3", 1, 1, 1, 2)
    with pytest.raises(DebugInfoError, match="canonical"):
        DebugInfo((first, second))
