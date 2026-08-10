from __future__ import annotations

import pytest

from bootstrap.s3.dynamic import DynamicError, DynamicKind, DynamicValue


def test_dynamic_value_preserves_scalar_tag_and_value() -> None:
    value = DynamicValue.f64(0.25)
    assert value.kind is DynamicKind.F64
    assert value.require(DynamicKind.F64) == 0.25


def test_dynamic_value_rejects_implicit_numeric_conversion() -> None:
    value = DynamicValue.i64(4)
    with pytest.raises(DynamicError, match="expected f64"):
        value.require(DynamicKind.F64)


def test_dynamic_value_validates_closed_scalar_domains() -> None:
    with pytest.raises(DynamicError, match="trit"):
        DynamicValue.trit(2)
    with pytest.raises(DynamicError, match="must be an integer"):
        DynamicValue.tryte(1.0)  # type: ignore[arg-type]
