"""M2.52 deterministic vector, map, and set semantics."""

from __future__ import annotations

import random

import pytest

from bootstrap.s3.dynamic import DynamicMap, DynamicSet, MovedValueError


def test_map_replay_preserves_insertion_order_across_updates_and_removes() -> None:
    rng = random.Random(252)
    actual = DynamicMap(32)
    expected: list[tuple[int, int]] = []
    for _ in range(128):
        key = rng.randrange(8)
        if rng.randrange(3):
            value = rng.randrange(-100, 101)
            actual.put(key, value)
            for index, item in enumerate(expected):
                if item[0] == key:
                    expected[index] = (key, value)
                    break
            else:
                expected.append((key, value))
        else:
            actual.remove(key)
            expected = [item for item in expected if item[0] != key]
        assert tuple(actual) == tuple(expected)


def test_set_replay_preserves_first_seen_order_and_compaction() -> None:
    rng = random.Random(253)
    actual = DynamicSet(16)
    expected: list[int] = []
    for _ in range(96):
        value = rng.randrange(8)
        if rng.randrange(2):
            actual.add(value)
            if value not in expected:
                expected.append(value)
        else:
            actual.remove(value)
            expected = [item for item in expected if item != value]
        assert tuple(actual) == tuple(expected)


def test_moved_map_index_access_is_rejected() -> None:
    original = DynamicMap(1)
    original.put(7, 70)
    moved = original.move()
    assert moved.key_at(0) == 7
    with pytest.raises(MovedValueError):
        original.key_at(0)
    with pytest.raises(MovedValueError):
        original.value_at(0)

