"""Bounded atomic and mutex synchronization providers for M1.70."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import threading
from typing import Generic, TypeVar

from .numeric import I64_MAX, I64_MIN, NumericError, validate_i64
from .results import Result


T = TypeVar("T")


class MemoryOrder(Enum):
    RELAXED = "relaxed"
    ACQUIRE = "acquire"
    RELEASE = "release"
    ACQ_REL = "acq_rel"
    SEQ_CST = "seq_cst"


class SyncErrorCode(Enum):
    INVALID_ORDER = "invalid_order"
    INVALID_VALUE = "invalid_value"
    OVERFLOW = "overflow"
    TIMEOUT = "timeout"
    CLOSED = "closed"
    ORDERING = "ordering"


@dataclass(frozen=True, slots=True)
class SyncError:
    code: SyncErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class AtomicCompareExchange:
    observed: int
    exchanged: bool


def _error(code: SyncErrorCode, operation: str, detail: str) -> SyncError:
    return SyncError(code, operation, detail)


def _is_order(value: object) -> bool:
    return isinstance(value, MemoryOrder)


def _valid_load_order(order: object) -> bool:
    return order in {MemoryOrder.RELAXED, MemoryOrder.ACQUIRE, MemoryOrder.SEQ_CST}


def _valid_store_order(order: object) -> bool:
    return order in {MemoryOrder.RELAXED, MemoryOrder.RELEASE, MemoryOrder.SEQ_CST}


def _valid_rmw_order(order: object) -> bool:
    return _is_order(order)


def _valid_compare_orders(success: object, failure: object) -> bool:
    if not _is_order(success) or not _is_order(failure):
        return False
    if failure in {MemoryOrder.RELEASE, MemoryOrder.ACQ_REL}:
        return False
    allowed_failures = {
        MemoryOrder.RELAXED: {MemoryOrder.RELAXED},
        MemoryOrder.ACQUIRE: {MemoryOrder.RELAXED, MemoryOrder.ACQUIRE},
        MemoryOrder.RELEASE: {MemoryOrder.RELAXED},
        MemoryOrder.ACQ_REL: {MemoryOrder.RELAXED, MemoryOrder.ACQUIRE},
        MemoryOrder.SEQ_CST: {
            MemoryOrder.RELAXED,
            MemoryOrder.ACQUIRE,
            MemoryOrder.SEQ_CST,
        },
    }
    return failure in allowed_failures[success]


class AtomicI64:
    """A bounded i64 atomic contract backed conservatively by a host lock.

    The provider deliberately makes no lock-free claim. The lock is private and
    source users only observe the typed operations below.
    """

    lock_free = False

    def __init__(self, value: int = 0) -> None:
        self._value = validate_i64(value)
        self._lock = threading.Lock()

    def load(self, order: MemoryOrder) -> Result[int, SyncError]:
        if not _valid_load_order(order):
            return Result.err(
                _error(
                    SyncErrorCode.INVALID_ORDER,
                    "load",
                    "load accepts relaxed, acquire, or seq_cst",
                )
            )
        with self._lock:
            return Result.ok(self._value)

    def store(self, value: int, order: MemoryOrder) -> Result[None, SyncError]:
        if not _valid_store_order(order):
            return Result.err(
                _error(
                    SyncErrorCode.INVALID_ORDER,
                    "store",
                    "store accepts relaxed, release, or seq_cst",
                )
            )
        try:
            checked = validate_i64(value)
        except NumericError as error:
            return Result.err(_error(SyncErrorCode.INVALID_VALUE, "store", str(error)))
        with self._lock:
            self._value = checked
        return Result.ok(None)

    def fetch_add(self, delta: int, order: MemoryOrder) -> Result[int, SyncError]:
        if not _valid_rmw_order(order):
            return Result.err(
                _error(
                    SyncErrorCode.INVALID_ORDER,
                    "fetch_add",
                    "read-modify-write accepts every declared order",
                )
            )
        try:
            checked_delta = validate_i64(delta)
        except NumericError as error:
            return Result.err(
                _error(SyncErrorCode.INVALID_VALUE, "fetch_add", str(error))
            )
        with self._lock:
            if not I64_MIN <= self._value + checked_delta <= I64_MAX:
                return Result.err(
                    _error(SyncErrorCode.OVERFLOW, "fetch_add", "i64 addition overflow")
                )
            previous = self._value
            self._value += checked_delta
            return Result.ok(previous)

    def compare_exchange(
        self,
        expected: int,
        desired: int,
        success_order: MemoryOrder,
        failure_order: MemoryOrder,
    ) -> Result[AtomicCompareExchange, SyncError]:
        if not _valid_compare_orders(success_order, failure_order):
            return Result.err(
                _error(
                    SyncErrorCode.ORDERING,
                    "compare_exchange",
                    "failure order is invalid for the selected success order",
                )
            )
        try:
            checked_expected = validate_i64(expected)
            checked_desired = validate_i64(desired)
        except NumericError as error:
            return Result.err(
                _error(SyncErrorCode.INVALID_VALUE, "compare_exchange", str(error))
            )
        with self._lock:
            observed = self._value
            exchanged = observed == checked_expected
            if exchanged:
                self._value = checked_desired
            return Result.ok(AtomicCompareExchange(observed, exchanged))


class Mutex(Generic[T]):
    """A mutex whose protected value is reachable only through a guard."""

    def __init__(self, value: T) -> None:
        self._value = value
        self._lock = threading.Lock()

    def lock(self, timeout_ms: int | None = None) -> Result[MutexGuard[T], SyncError]:
        if timeout_ms is not None and (
            isinstance(timeout_ms, bool) or not isinstance(timeout_ms, int) or timeout_ms < 0
        ):
            return Result.err(
                _error(SyncErrorCode.TIMEOUT, "lock", "timeout must be a non-negative integer")
            )
        acquired = (
            self._lock.acquire()
            if timeout_ms is None
            else self._lock.acquire(timeout=timeout_ms / 1000)
        )
        if not acquired:
            return Result.err(_error(SyncErrorCode.TIMEOUT, "lock", "mutex acquisition timed out"))
        return Result.ok(MutexGuard(self))


class MutexGuard(Generic[T]):
    """Deterministically unlocks its parent mutex exactly once."""

    def __init__(self, mutex: Mutex[T]) -> None:
        self._mutex = mutex
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def value(self) -> Result[T, SyncError]:
        return self.get()

    def get(self) -> Result[T, SyncError]:
        if self._closed:
            return Result.err(_error(SyncErrorCode.CLOSED, "get", "mutex guard is closed"))
        return Result.ok(self._mutex._value)

    def set(self, value: T) -> Result[None, SyncError]:
        if self._closed:
            return Result.err(_error(SyncErrorCode.CLOSED, "set", "mutex guard is closed"))
        self._mutex._value = value
        return Result.ok(None)

    def release(self) -> Result[None, SyncError]:
        if self._closed:
            return Result.ok(None)
        self._closed = True
        self._mutex._lock.release()
        return Result.ok(None)

    def __enter__(self) -> MutexGuard[T]:
        return self

    def __exit__(self, _exc_type: object, _exc: object, _tb: object) -> None:
        self.release()
