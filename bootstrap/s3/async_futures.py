"""First-class move-only Futures and async module identities for M1.82."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Generic, TypeVar

from .async_core import AsyncError, AsyncErrorCode, AsyncFuture, AsyncState, Poll
from .module_graph import ModuleId
from .results import Result


T = TypeVar("T")

_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_MAX_TYPE_ARGUMENTS = 8


class FutureErrorCode(Enum):
    OWNERSHIP = "ownership"
    INVALID_STATE = "invalid_state"
    DUPLICATE_IDENTITY = "duplicate_identity"
    UNKNOWN_FUNCTION = "unknown_function"
    INVALID_TYPE_ARGUMENT = "invalid_type_argument"
    TYPE_ARGUMENT_LIMIT = "type_argument_limit"
    POLL_LIMIT = "poll_limit"


@dataclass(frozen=True, slots=True)
class FutureError:
    code: FutureErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, order=True, slots=True)
class AsyncFunctionIdentity:
    module: ModuleId
    name: str
    type_arguments: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not _IDENTIFIER.fullmatch(self.name):
            raise ValueError(f"invalid async function name: {self.name!r}")
        if len(self.type_arguments) > _MAX_TYPE_ARGUMENTS:
            raise ValueError("async generic type argument limit exceeded")
        if any(not _closed_type_name(item) for item in self.type_arguments):
            raise ValueError("async function identity requires closed type arguments")

    @property
    def qualified_name(self) -> str:
        suffix = "" if not self.type_arguments else "[" + ",".join(self.type_arguments) + "]"
        return f"{self.module}.{self.name}{suffix}"


@dataclass(frozen=True, slots=True)
class AsyncFunctionSpec(Generic[T]):
    identity: AsyncFunctionIdentity
    factory: Callable[[], AsyncFuture[T]]

    def instantiate(self) -> AsyncFuture[T]:
        future = self.factory()
        if not isinstance(future, AsyncFuture):
            raise TypeError("async function factory must return AsyncFuture")
        return future


class MoveOnlyFuture(Generic[T]):
    """One owner for one async future; move transfers ownership exactly once."""

    def __init__(self, future: AsyncFuture[T]) -> None:
        if not isinstance(future, AsyncFuture):
            raise TypeError("MoveOnlyFuture requires AsyncFuture")
        self._future: AsyncFuture[T] | None = future

    def __copy__(self) -> MoveOnlyFuture[T]:
        raise TypeError("move-only Future cannot be copied")

    def __deepcopy__(self, _memo: dict[int, object]) -> MoveOnlyFuture[T]:
        raise TypeError("move-only Future cannot be deep-copied")

    @property
    def moved(self) -> bool:
        return self._future is None

    @property
    def state(self) -> AsyncState:
        future = self._future
        return AsyncState.CANCELLED if future is None else future.state

    def move(self) -> Result[MoveOnlyFuture[T], FutureError]:
        future = self._future
        if future is None:
            return Result.err(FutureError(FutureErrorCode.OWNERSHIP, "move", "Future owner was already moved"))
        self._future = None
        return Result.ok(MoveOnlyFuture(future))

    def poll(self) -> Result[Poll[T], FutureError]:
        future = self._owned("poll")
        if future.is_err:
            return Result.err(future.error_or(None))
        return Result.ok(future.value_or(None).poll())

    def await_once(self, *, max_polls: int = 64) -> Result[T, FutureError]:
        if isinstance(max_polls, bool) or not isinstance(max_polls, int) or max_polls <= 0:
            return Result.err(FutureError(FutureErrorCode.POLL_LIMIT, "await_once", "poll budget must be positive"))
        for _ in range(max_polls):
            polled = self.poll()
            if polled.is_err:
                return Result.err(polled.error_or(None))
            result = polled.value_or(None)
            if result.kind.value == "ready":
                return Result.ok(result.value)
            if result.kind.value == "failed":
                return Result.err(FutureError(FutureErrorCode.INVALID_STATE, "await_once", result.error.detail if result.error else "future failed"))
        return Result.err(FutureError(FutureErrorCode.POLL_LIMIT, "await_once", "future did not become ready within poll budget"))

    def cancel(self) -> Result[None, FutureError]:
        future = self._owned("cancel")
        if future.is_err:
            return Result.err(future.error_or(None))
        result = future.value_or(None).cancel()
        if result.is_err:
            error = result.error_or(None)
            return Result.err(FutureError(FutureErrorCode.INVALID_STATE, "cancel", error.detail if isinstance(error, AsyncError) else "future cancellation failed"))
        return Result.ok(None)

    def _owned(self, operation: str) -> Result[AsyncFuture[T], FutureError]:
        if self._future is None:
            return Result.err(FutureError(FutureErrorCode.OWNERSHIP, operation, "Future owner was already moved"))
        return Result.ok(self._future)


class AsyncModuleRegistry:
    """Bounded registry of module-qualified async function declarations."""

    def __init__(self, *, max_functions: int = 256) -> None:
        if isinstance(max_functions, bool) or not isinstance(max_functions, int) or max_functions <= 0:
            raise ValueError("max_functions must be a positive integer")
        self._max_functions = max_functions
        self._functions: dict[AsyncFunctionIdentity, AsyncFunctionSpec[object]] = {}

    @property
    def identities(self) -> tuple[AsyncFunctionIdentity, ...]:
        return tuple(sorted(self._functions))

    def register(self, spec: AsyncFunctionSpec[T]) -> Result[None, FutureError]:
        identity = spec.identity
        if identity in self._functions:
            return Result.err(FutureError(FutureErrorCode.DUPLICATE_IDENTITY, "register", identity.qualified_name))
        if len(self._functions) >= self._max_functions:
            return Result.err(FutureError(FutureErrorCode.TYPE_ARGUMENT_LIMIT, "register", "async module function limit exceeded"))
        self._functions[identity] = spec  # type: ignore[assignment]
        return Result.ok(None)

    def instantiate(self, identity: AsyncFunctionIdentity) -> Result[MoveOnlyFuture[object], FutureError]:
        spec = self._functions.get(identity)
        if spec is None:
            return Result.err(FutureError(FutureErrorCode.UNKNOWN_FUNCTION, "instantiate", identity.qualified_name))
        return Result.ok(MoveOnlyFuture(spec.instantiate()))


@dataclass(frozen=True, slots=True)
class AsyncGenericDeclaration:
    module: ModuleId
    name: str
    constraints: tuple[str, ...]
    factory: Callable[[tuple[str, ...]], AsyncFuture[object]]

    def specialize(self, type_arguments: tuple[str, ...]) -> Result[AsyncFunctionSpec[object], FutureError]:
        if len(type_arguments) != len(self.constraints):
            return Result.err(FutureError(FutureErrorCode.INVALID_TYPE_ARGUMENT, "specialize", "generic arity mismatch"))
        if len(type_arguments) > _MAX_TYPE_ARGUMENTS:
            return Result.err(FutureError(FutureErrorCode.TYPE_ARGUMENT_LIMIT, "specialize", "generic type argument limit exceeded"))
        for argument, constraint in zip(type_arguments, self.constraints):
            if not _closed_type_name(argument) or not _satisfies(argument, constraint):
                return Result.err(FutureError(FutureErrorCode.INVALID_TYPE_ARGUMENT, "specialize", f"{argument!r} does not satisfy {constraint!r}"))
        identity = AsyncFunctionIdentity(self.module, self.name, type_arguments)
        return Result.ok(AsyncFunctionSpec(identity, lambda: self.factory(type_arguments)))


class AsyncGenericRegistry:
    def __init__(self, *, max_declarations: int = 128) -> None:
        if isinstance(max_declarations, bool) or not isinstance(max_declarations, int) or max_declarations <= 0:
            raise ValueError("max_declarations must be a positive integer")
        self._max_declarations = max_declarations
        self._declarations: dict[tuple[ModuleId, str], AsyncGenericDeclaration] = {}

    def register(self, declaration: AsyncGenericDeclaration) -> Result[None, FutureError]:
        key = (declaration.module, declaration.name)
        if key in self._declarations:
            return Result.err(FutureError(FutureErrorCode.DUPLICATE_IDENTITY, "register", f"{declaration.module}.{declaration.name}"))
        if len(self._declarations) >= self._max_declarations:
            return Result.err(FutureError(FutureErrorCode.TYPE_ARGUMENT_LIMIT, "register", "generic async declaration limit exceeded"))
        self._declarations[key] = declaration
        return Result.ok(None)

    def specialize(self, module: ModuleId, name: str, type_arguments: tuple[str, ...]) -> Result[AsyncFunctionSpec[object], FutureError]:
        declaration = self._declarations.get((module, name))
        if declaration is None:
            return Result.err(FutureError(FutureErrorCode.UNKNOWN_FUNCTION, "specialize", f"{module}.{name}"))
        return declaration.specialize(type_arguments)


def _closed_type_name(value: str) -> bool:
    return bool(value) and len(value) <= 64 and bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_<>, ]*", value)) and "?" not in value


def _satisfies(type_name: str, constraint: str) -> bool:
    if constraint == "scalar":
        return type_name in {"tryte", "i64", "f64", "bool"}
    if constraint == "owned":
        return type_name in {"tryte", "i64", "f64", "bool", "text", "bytes"} or type_name.startswith(("vector<", "map<", "set<"))
    if constraint == "send":
        return _satisfies(type_name, "owned")
    return False
