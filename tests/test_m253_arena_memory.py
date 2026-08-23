"""M2.53 explicit-lifetime arena and region contracts."""

from __future__ import annotations

import pytest

from bootstrap.s3.arena import (
    Arena,
    ArenaBoundsError,
    ArenaCapacityError,
    ArenaLifetimeError,
)


def test_arena_allocates_aligned_fixed_blocks_without_implicit_growth() -> None:
    arena = Arena(16)
    first = arena.allocate(3)
    second = arena.allocate(4, alignment=4)
    assert first.offset == 0
    assert second.offset == 4
    assert arena.used == 8
    assert arena.remaining == 8
    with pytest.raises(ArenaCapacityError):
        arena.allocate(9)
    assert arena.used == 8


def test_arena_blocks_have_exact_checked_storage() -> None:
    block = Arena(4).allocate(4)
    block.write(b"S3!!")
    assert block.read() == b"S3!!"
    with pytest.raises(ArenaBoundsError):
        block.write(b"S3")
    with pytest.raises(ArenaBoundsError):
        block.write("S3!!")  # type: ignore[arg-type]


def test_arena_rewind_invalidates_only_rewound_blocks() -> None:
    arena = Arena(12)
    prefix = arena.allocate(3)
    mark = arena.mark()
    suffix = arena.allocate(4)
    arena.rewind(mark)
    assert prefix.read() == b"\x00\x00\x00"
    with pytest.raises(ArenaLifetimeError):
        suffix.read()
    replacement = arena.allocate(4)
    replacement.write(b"next")
    assert replacement.read() == b"next"


def test_arena_rejects_foreign_marks_and_reset_is_explicit() -> None:
    first = Arena(8)
    second = Arena(8)
    block = first.allocate(2)
    with pytest.raises(ArenaLifetimeError):
        first.rewind(second.mark())
    first.reset()
    with pytest.raises(ArenaLifetimeError):
        block.read()
