"""Explicit hosted Result and Option contracts for M1.64."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar


T = TypeVar("T")
U = TypeVar("U")
E = TypeVar("E")
F = TypeVar("F")
R = TypeVar("R")


@dataclass(frozen=True, slots=True)
class Result(Generic[T, E]):
    """A closed success/error value with explicit, branch-local handling."""

    _success: bool
    _payload: T | E

    @classmethod
    def ok(cls, value: T) -> Result[T, E]:
        return cls(True, value)

    @classmethod
    def err(cls, error: E) -> Result[T, E]:
        return cls(False, error)

    @property
    def is_ok(self) -> bool:
        return self._success

    @property
    def is_err(self) -> bool:
        return not self._success

    def fold(
        self,
        on_ok: Callable[[T], R],
        on_err: Callable[[E], R],
    ) -> R:
        """Handle both branches explicitly without hidden propagation."""

        if self._success:
            return on_ok(self._payload)  # type: ignore[arg-type]
        return on_err(self._payload)  # type: ignore[arg-type]

    def map(self, function: Callable[[T], U]) -> Result[U, E]:
        if self._success:
            return Result.ok(function(self._payload))  # type: ignore[arg-type]
        return Result.err(self._payload)  # type: ignore[arg-type]

    def map_error(self, function: Callable[[E], F]) -> Result[T, F]:
        if self._success:
            return Result.ok(self._payload)  # type: ignore[arg-type]
        return Result.err(function(self._payload))  # type: ignore[arg-type]

    def bind(self, function: Callable[[T], Result[U, E]]) -> Result[U, E]:
        """Compose an explicit success path and carry an existing error value."""

        if not self._success:
            return Result.err(self._payload)  # type: ignore[arg-type]
        result = function(self._payload)  # type: ignore[arg-type]
        if not isinstance(result, Result):
            raise TypeError("Result.bind callback must return Result")
        return result

    def value_or(self, default: U) -> T | U:
        return self._payload if self._success else default  # type: ignore[return-value]

    def error_or(self, default: F) -> E | F:
        return default if self._success else self._payload  # type: ignore[return-value]


@dataclass(frozen=True, slots=True)
class Option(Generic[T]):
    """A closed present/absent value with no sentinel payload convention."""

    _present: bool
    _payload: T | None = None

    @classmethod
    def some(cls, value: T) -> Option[T]:
        return cls(True, value)

    @classmethod
    def none(cls) -> Option[T]:
        return cls(False)

    @property
    def is_some(self) -> bool:
        return self._present

    @property
    def is_none(self) -> bool:
        return not self._present

    def fold(self, on_some: Callable[[T], R], on_none: Callable[[], R]) -> R:
        if self._present:
            return on_some(self._payload)  # type: ignore[arg-type]
        return on_none()

    def map(self, function: Callable[[T], U]) -> Option[U]:
        if self._present:
            return Option.some(function(self._payload))  # type: ignore[arg-type]
        return Option.none()

    def bind(self, function: Callable[[T], Option[U]]) -> Option[U]:
        if not self._present:
            return Option.none()
        result = function(self._payload)  # type: ignore[arg-type]
        if not isinstance(result, Option):
            raise TypeError("Option.bind callback must return Option")
        return result

    def value_or(self, default: U) -> T | U:
        return self._payload if self._present else default  # type: ignore[return-value]
