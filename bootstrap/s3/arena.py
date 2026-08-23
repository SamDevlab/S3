"""Explicit-lifetime bounded storage for compiler-owned temporary state.

The arena is deliberately a hosted reference boundary: capacity is fixed at
construction, allocations are monotonic until an explicit mark rewind, and a
rewound block cannot be observed again through a retained handle. It does not
replace the dynamic-value allocator or claim a native heap ABI.
"""

from __future__ import annotations

from dataclasses import dataclass


MAX_ARENA_BYTES = 2_147_483_647


class ArenaError(RuntimeError):
    """Base class for deterministic arena lifetime and capacity failures."""


class ArenaCapacityError(ArenaError):
    """Raised when an arena cannot satisfy a bounded allocation."""


class ArenaBoundsError(ArenaError):
    """Raised when a block operation does not match its fixed extent."""


class ArenaLifetimeError(ArenaError):
    """Raised when a block is accessed after its region was rewound."""


@dataclass(frozen=True, slots=True)
class ArenaMark:
    """An arena-owned cursor checkpoint suitable for explicit rewind."""

    _owner: object
    offset: int


class ArenaBlock:
    """A checked fixed-size handle into one arena allocation."""

    __slots__ = ("_arena", "_offset", "_size", "_live")

    def __init__(self, arena: Arena, offset: int, size: int) -> None:
        self._arena = arena
        self._offset = offset
        self._size = size
        self._live = True

    @property
    def offset(self) -> int:
        return self._offset

    @property
    def size(self) -> int:
        return self._size

    def read(self) -> bytes:
        self._require_live()
        return bytes(self._arena._storage[self._offset : self._offset + self._size])

    def write(self, value: bytes | bytearray | memoryview) -> None:
        self._require_live()
        try:
            data = bytes(value)
        except (TypeError, ValueError) as exc:
            raise ArenaBoundsError("arena block data must be bytes-like") from exc
        if len(data) != self._size:
            raise ArenaBoundsError(
                f"arena block requires exactly {self._size} bytes"
            )
        self._arena._storage[self._offset : self._offset + self._size] = data

    def _require_live(self) -> None:
        if not self._live:
            raise ArenaLifetimeError("arena block is no longer live")


class Arena:
    """A fixed-capacity monotonic region with explicit mark/rewind lifetime."""

    def __init__(self, capacity: int) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int):
            raise TypeError("arena capacity must be an integer")
        if not 0 < capacity <= MAX_ARENA_BYTES:
            raise ValueError("arena capacity must be within the logical arena limit")
        self.capacity = capacity
        self._storage = bytearray(capacity)
        self._cursor = 0
        self._owner = object()
        self._blocks: list[ArenaBlock] = []

    @property
    def used(self) -> int:
        return self._cursor

    @property
    def remaining(self) -> int:
        return self.capacity - self._cursor

    def mark(self) -> ArenaMark:
        return ArenaMark(self._owner, self._cursor)

    def allocate(self, size: int, *, alignment: int = 1) -> ArenaBlock:
        if isinstance(size, bool) or not isinstance(size, int):
            raise TypeError("arena allocation size must be an integer")
        if size <= 0:
            raise ArenaCapacityError("arena allocation size must be positive")
        if isinstance(alignment, bool) or not isinstance(alignment, int):
            raise TypeError("arena alignment must be an integer")
        if alignment <= 0:
            raise ValueError("arena alignment must be positive")
        offset = ((self._cursor + alignment - 1) // alignment) * alignment
        end = offset + size
        if end > self.capacity:
            raise ArenaCapacityError(
                f"arena allocation {size} with alignment {alignment} exceeds remaining capacity"
            )
        block = ArenaBlock(self, offset, size)
        self._blocks.append(block)
        self._cursor = end
        return block

    def rewind(self, mark: ArenaMark) -> None:
        if not isinstance(mark, ArenaMark) or mark._owner is not self._owner:
            raise ArenaLifetimeError("arena mark belongs to another arena")
        if not 0 <= mark.offset <= self._cursor:
            raise ArenaLifetimeError("arena mark is outside the active region")
        for block in self._blocks:
            if block.offset >= mark.offset:
                block._live = False
        self._cursor = mark.offset

    def reset(self) -> None:
        self.rewind(ArenaMark(self._owner, 0))
