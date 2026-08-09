"""Small self-validation for the public test capability vocabulary."""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.s3_fast


EXPECTED_MARKERS = {
    "s3_fast",
    "s3_contract",
    "s3_differential",
    "s3_native",
    "s3_slow",
    "s3_benchmark",
}


def test_capability_markers_are_registered(pytestconfig: pytest.Config) -> None:
    configured = {line.split(":", 1)[0] for line in pytestconfig.getini("markers")}
    assert EXPECTED_MARKERS <= configured


def test_fast_gate_marker_is_not_empty() -> None:
    assert EXPECTED_MARKERS
