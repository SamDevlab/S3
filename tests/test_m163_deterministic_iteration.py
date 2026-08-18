from __future__ import annotations

import pytest

from bootstrap.s3.dynamic import DynamicMap, DynamicSet, DynamicVector
from bootstrap.s3.iteration import I64Range, deterministic_range


def test_i64_ranges_are_half_open_checked_and_deterministic() -> None:
    assert list(I64Range(0, 6, 2)) == [0, 2, 4]
    assert list(deterministic_range(5, -1, -2)) == [5, 3, 1]
    assert list(I64Range(4, 4)) == []
    with pytest.raises(ValueError, match="step cannot be zero"):
        I64Range(0, 1, 0)


def test_dynamic_vector_and_borrowed_view_iterate_in_storage_order() -> None:
    values = DynamicVector("i64", 4, _data=(4, 5, 6))
    assert list(values) == [4, 5, 6]
    view = values.borrow_range(1, 3)
    assert list(view) == [5, 6]
    view.close()


def test_map_and_set_iteration_preserve_existing_order_contracts() -> None:
    mapping = DynamicMap(3)
    mapping.put(7, 70)
    mapping.put(8, 80)
    mapping.put(7, 77)
    assert list(mapping) == [(7, 77), (8, 80)]

    values = DynamicSet(3)
    values.add(8)
    values.add(7)
    values.add(8)
    assert list(values) == [8, 7]
