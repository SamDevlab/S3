"""Provider-neutral async network operations for S3 M1.74."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from .async_core import AsyncFuture, AsyncFrame, complete, fail, pending
from .network import NetworkAddress
from .results import Result


class AsyncNetworkErrorCode(Enum):
    INVALID_ARGUMENT = "invalid_argument"
    CLOSED = "closed"
    RESOURCE_LIMIT = "resource_limit"
    TIMEOUT = "timeout"
    EOF = "eof"
    PROVIDER_FAILURE = "provider_failure"


@dataclass(frozen=True, slots=True)
class AsyncNetworkError:
    code: AsyncNetworkErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class PendingOperation:
    pass


@dataclass(frozen=True, slots=True)
class PendingResource:
    resource: object


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    error: AsyncNetworkError


class AsyncNetworkProvider(Protocol):
    def connect(self, address: NetworkAddress) -> object: ...
    def accept(self, listener: object) -> object: ...
    def read(self, stream: object, amount: int) -> object: ...
    def write(self, stream: object, data: bytes) -> object: ...
    def udp_send(self, socket: object, data: bytes, address: NetworkAddress) -> object: ...
    def udp_receive(self, socket: object) -> object: ...
    def resolve(self, host: str, port: int) -> object: ...
    def close(self, resource: object) -> None: ...


@dataclass(slots=True)
class AsyncNetworkHandle:
    identifier: int
    resource: object
    _service: AsyncNetworkService
    closed: bool = False

    def close(self) -> Result[None, AsyncNetworkError]:
        return self._service.close(self)


class AsyncNetworkService:
    """Bounded owner of asynchronous network resources."""

    def __init__(self, provider: AsyncNetworkProvider, *, max_handles: int = 32) -> None:
        if isinstance(max_handles, bool) or not isinstance(max_handles, int) or max_handles <= 0:
            raise ValueError("max_handles must be a positive integer")
        self.provider = provider
        self.max_handles = max_handles
        self._handles: dict[int, AsyncNetworkHandle] = {}
        self._next_id = 0

    @property
    def active_handles(self) -> int:
        return len(self._handles)

    def connect(self, address: NetworkAddress) -> AsyncFuture[AsyncNetworkHandle]:
        return self._resource_future("connect", lambda: self.provider.connect(address))

    def accept(self, listener: AsyncNetworkHandle) -> AsyncFuture[AsyncNetworkHandle] | AsyncFuture[object]:
        checked = self._check_handle(listener, "accept")
        if checked is not None:
            return AsyncFuture(lambda _frame: fail(checked.code, checked.operation, checked.detail))
        return self._resource_future("accept", lambda: self.provider.accept(listener.resource))

    def read(self, stream: AsyncNetworkHandle, amount: int) -> AsyncFuture[bytes]:
        checked = self._check_handle(stream, "read")
        if checked is not None or isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
            error = checked or AsyncNetworkError(AsyncNetworkErrorCode.INVALID_ARGUMENT, "read", "amount must be positive")
            return AsyncFuture(lambda _frame: fail(error.code, error.operation, error.detail))
        return self._value_future("read", lambda: self.provider.read(stream.resource, amount))

    def write(self, stream: AsyncNetworkHandle, data: bytes) -> AsyncFuture[int]:
        checked = self._check_handle(stream, "write")
        if checked is not None or not isinstance(data, bytes):
            error = checked or AsyncNetworkError(AsyncNetworkErrorCode.INVALID_ARGUMENT, "write", "data must be bytes")
            return AsyncFuture(lambda _frame: fail(error.code, error.operation, error.detail))
        return self._value_future("write", lambda: self.provider.write(stream.resource, data))

    def udp_send(self, socket_handle: AsyncNetworkHandle, data: bytes, address: NetworkAddress) -> AsyncFuture[int]:
        checked = self._check_handle(socket_handle, "udp_send")
        if checked is not None or not isinstance(data, bytes) or not isinstance(address, NetworkAddress):
            error = checked or AsyncNetworkError(AsyncNetworkErrorCode.INVALID_ARGUMENT, "udp_send", "invalid datagram arguments")
            return AsyncFuture(lambda _frame: fail(error.code, error.operation, error.detail))
        return self._value_future("udp_send", lambda: self.provider.udp_send(socket_handle.resource, data, address))

    def udp_receive(self, socket_handle: AsyncNetworkHandle) -> AsyncFuture[object]:
        checked = self._check_handle(socket_handle, "udp_receive")
        if checked is not None:
            return AsyncFuture(lambda _frame: fail(checked.code, checked.operation, checked.detail))
        return self._value_future("udp_receive", lambda: self.provider.udp_receive(socket_handle.resource))

    def resolve(self, host: str, port: int) -> AsyncFuture[tuple[NetworkAddress, ...]]:
        if not isinstance(host, str) or not host or "\x00" in host:
            return AsyncFuture(lambda _frame: fail(AsyncNetworkErrorCode.INVALID_ARGUMENT, "resolve", "host is invalid"))
        return self._value_future("resolve", lambda: self.provider.resolve(host, port))

    def close(self, handle: AsyncNetworkHandle) -> Result[None, AsyncNetworkError]:
        current = self._handles.get(handle.identifier)
        if current is None or current.closed:
            return Result.ok(None)
        current.closed = True
        self._handles.pop(handle.identifier, None)
        self.provider.close(current.resource)
        return Result.ok(None)

    def _resource_future(self, operation: str, call):
        pending_resource: object | None = None

        def step(frame: AsyncFrame):
            nonlocal pending_resource
            outcome = call()
            if isinstance(outcome, PendingOperation):
                return pending()
            if isinstance(outcome, ProviderFailure):
                return fail(outcome.error.code, operation, outcome.error.detail)
            if isinstance(outcome, PendingResource):
                if pending_resource is not None and outcome.resource is not pending_resource:
                    self.provider.close(outcome.resource)
                    return fail(AsyncNetworkErrorCode.PROVIDER_FAILURE, operation, "provider replaced an already pending resource")
                pending_resource = outcome.resource
                if "network-resource" not in frame.slots:
                    if frame.own("network-resource", outcome.resource, self.provider.close).is_err:
                        self.provider.close(outcome.resource)
                        pending_resource = None
                        return fail(AsyncNetworkErrorCode.RESOURCE_LIMIT, operation, "frame resource slot unavailable")
                return pending()

            resource = outcome
            if pending_resource is not None and resource is not pending_resource:
                self.provider.close(resource)
                return fail(AsyncNetworkErrorCode.PROVIDER_FAILURE, operation, "provider completion replaced the frame-owned pending resource")

            if len(self._handles) >= self.max_handles:
                if pending_resource is None:
                    self.provider.close(resource)
                return fail(AsyncNetworkErrorCode.RESOURCE_LIMIT, operation, "network handle limit exceeded")

            if pending_resource is not None:
                moved = frame.move("network-resource")
                if moved.is_err:
                    return fail(AsyncNetworkErrorCode.PROVIDER_FAILURE, operation, "pending resource transfer failed")
                resource = moved.value_or(None)
                pending_resource = None
            else:
                if frame.own("network-resource", resource, self.provider.close).is_err:
                    self.provider.close(resource)
                    return fail(AsyncNetworkErrorCode.RESOURCE_LIMIT, operation, "frame resource slot unavailable")
                moved = frame.move("network-resource")
                if moved.is_err:
                    self.provider.close(resource)
                    return fail(AsyncNetworkErrorCode.PROVIDER_FAILURE, operation, "resource transfer failed")
                resource = moved.value_or(None)

            handle = AsyncNetworkHandle(self._next_id, resource, self)
            self._next_id += 1
            self._handles[handle.identifier] = handle
            return complete(handle)

        return AsyncFuture(step)

    def _value_future(self, operation: str, call):
        def step(_frame: AsyncFrame):
            outcome = call()
            if isinstance(outcome, PendingOperation):
                return pending()
            if isinstance(outcome, ProviderFailure):
                return fail(outcome.error.code, operation, outcome.error.detail)
            return complete(outcome)

        return AsyncFuture(step)

    def _check_handle(self, handle: AsyncNetworkHandle, operation: str) -> AsyncNetworkError | None:
        if not isinstance(handle, AsyncNetworkHandle) or handle._service is not self or handle.closed or handle.identifier not in self._handles:
            return AsyncNetworkError(AsyncNetworkErrorCode.CLOSED, operation, "network handle is closed")
        return None
