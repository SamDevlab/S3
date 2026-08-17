"""Explicit, injectable host-service contracts for M1.36."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
from pathlib import Path
import subprocess
from typing import Sequence
from typing import Callable, Protocol

from .dynamic import DynamicValue


class HostServiceError(RuntimeError):
    """Raised for an unavailable or incorrectly invoked host service."""


class ResourceError(HostServiceError):
    """Base error for the scoped resource boundary."""


class ResourceCapabilityError(ResourceError):
    """Raised when a capability does not authorize a resource operation."""


class ResourceClosedError(ResourceError):
    """Raised when a resource handle is used after close."""


class ResourceLimitError(ResourceError):
    """Raised when the registry cannot admit another active resource."""


class HostService(Enum):
    CLOCK_MONOTONIC = "clock_monotonic"
    DIAGNOSTIC = "diagnostic"


class HostServiceCapability(Enum):
    ARGV = "argv"
    ENVIRONMENT = "environment"
    STDIO = "stdio"
    FILE_READ = "filesystem.read"
    FILE_WRITE = "filesystem.write"
    PROCESS_SPAWN = "process.spawn"


@dataclass(frozen=True, slots=True)
class ProcessResult:
    args: tuple[str, ...]
    stdout: str
    stderr: str
    returncode: int


class LinuxHostServices:
    """Explicit Linux host provider with deterministic, shell-free operations."""

    def __init__(
        self,
        *,
        argv: Sequence[str] = (),
        environment: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> None:
        self._argv = tuple(str(value) for value in argv)
        self._environment = dict(os.environ if environment is None else environment)
        self._cwd = None if cwd is None else Path(cwd)

    def capabilities(self) -> frozenset[HostServiceCapability]:
        return frozenset(HostServiceCapability)

    def argv(self) -> tuple[str, ...]:
        return self._argv

    def environment(self, name: str) -> str | None:
        if not name or "=" in name:
            raise HostServiceError("environment name must be non-empty and contain no '='")
        return self._environment.get(name)

    def read_file(self, path: Path, *, encoding: str = "utf-8") -> str:
        try:
            return Path(path).read_text(encoding=encoding)
        except OSError as error:
            raise HostServiceError(f"file read failed: {path}") from error

    def write_file(self, path: Path, content: str, *, encoding: str = "utf-8") -> None:
        try:
            destination = Path(path)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding=encoding, newline="\n")
        except OSError as error:
            raise HostServiceError(f"file write failed: {path}") from error

    def spawn(
        self,
        command: str,
        args: Sequence[str] = (),
        *,
        env: dict[str, str] | None = None,
        stdin: str = "",
        timeout: float = 30.0,
    ) -> ProcessResult:
        if not command or any("\x00" in value for value in (command, *args)):
            raise HostServiceError("process command and arguments must be valid strings")
        command_line = (command, *(str(value) for value in args))
        merged_env = dict(self._environment)
        if env is not None:
            merged_env.update({str(key): str(value) for key, value in env.items()})
        try:
            completed = subprocess.run(
                list(command_line),
                cwd=self._cwd,
                env=merged_env,
                input=stdin,
                capture_output=True,
                text=True,
                shell=False,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise HostServiceError(f"process timed out after {timeout}s") from error
        except OSError as error:
            raise HostServiceError(f"process spawn failed: {command}") from error
        return ProcessResult(command_line, completed.stdout, completed.stderr, completed.returncode)

    def pipe(
        self,
        producer: tuple[str, Sequence[str]],
        consumer: tuple[str, Sequence[str]],
        *,
        timeout: float = 30.0,
    ) -> ProcessResult:
        first = self.spawn(producer[0], producer[1], timeout=timeout)
        if first.returncode != 0:
            return first
        return self.spawn(consumer[0], consumer[1], stdin=first.stdout, timeout=timeout)


@dataclass(frozen=True, slots=True)
class HostServiceRequest:
    service: HostService
    arguments: tuple[DynamicValue, ...] = ()


HostServiceHandler = Callable[[tuple[DynamicValue, ...]], DynamicValue]


class ResourceKind(Enum):
    FILE = "file"
    PROCESS = "process"
    SOCKET = "socket"


class ResourceProvider(Protocol):
    """Provider contract for one closed resource kind."""

    def open(self) -> object:
        ...

    def invoke(
        self,
        resource: object,
        arguments: tuple[DynamicValue, ...],
    ) -> DynamicValue:
        ...

    def close(self, resource: object) -> None:
        ...


@dataclass(frozen=True, slots=True)
class CapabilityToken:
    """Opaque capability issued by one ResourceRegistry."""

    kind: ResourceKind
    _authority: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class ResourceHandle:
    """Opaque registry handle; slot and generation are not public identity."""

    _registry: ResourceRegistry
    _slot: int
    _generation: int
    _kind: ResourceKind

    @property
    def kind(self) -> ResourceKind:
        return self._kind


@dataclass(slots=True)
class _ActiveResource:
    handle: ResourceHandle
    provider: ResourceProvider
    resource: object


class ResourceRegistry:
    """Explicit capability-scoped resource registry with deterministic slots."""

    def __init__(self, *, max_active: int = 64) -> None:
        if isinstance(max_active, bool) or not isinstance(max_active, int):
            raise ResourceLimitError("max_active must be an integer")
        if max_active <= 0:
            raise ResourceLimitError("max_active must be positive")
        self._max_active = max_active
        self._providers: dict[ResourceKind, ResourceProvider] = {}
        self._authority = object()
        self._active: dict[tuple[int, int], _ActiveResource] = {}
        self._generations: dict[int, int] = {}

    def register(self, kind: ResourceKind, provider: ResourceProvider) -> None:
        if not isinstance(kind, ResourceKind):
            raise ResourceError("resource kind must be a ResourceKind")
        if kind in self._providers:
            raise ResourceError(f"resource provider already registered: {kind.value}")
        for name in ("open", "invoke", "close"):
            if not callable(getattr(provider, name, None)):
                raise ResourceError(f"resource provider is missing '{name}'")
        self._providers[kind] = provider

    def grant(self, kind: ResourceKind) -> CapabilityToken:
        if kind not in self._providers:
            raise ResourceCapabilityError(f"resource capability unavailable: {kind.value}")
        return CapabilityToken(kind, self._authority)

    def open(self, capability: CapabilityToken) -> ResourceHandle:
        if not isinstance(capability, CapabilityToken):
            raise ResourceCapabilityError("resource capability token is invalid")
        if capability._authority is not self._authority:
            raise ResourceCapabilityError("resource capability belongs to another registry")
        provider = self._providers.get(capability.kind)
        if provider is None:
            raise ResourceCapabilityError(f"resource capability unavailable: {capability.kind.value}")
        if len(self._active) >= self._max_active:
            raise ResourceLimitError("active resource limit exceeded")
        slot = 0
        while any(key[0] == slot for key in self._active):
            slot += 1
        generation = self._generations.get(slot, 0) + 1
        self._generations[slot] = generation
        resource = provider.open()
        handle = ResourceHandle(self, slot, generation, capability.kind)
        self._active[(slot, generation)] = _ActiveResource(handle, provider, resource)
        return handle

    def is_open(self, handle: ResourceHandle) -> bool:
        return (
            isinstance(handle, ResourceHandle)
            and handle._registry is self
            and (handle._slot, handle._generation) in self._active
        )

    def invoke(
        self,
        handle: ResourceHandle,
        arguments: tuple[DynamicValue, ...] = (),
    ) -> DynamicValue:
        active = self._require_active(handle)
        result = active.provider.invoke(active.resource, arguments)
        if not isinstance(result, DynamicValue):
            raise ResourceError("resource provider must return DynamicValue")
        return result

    def close(self, handle: ResourceHandle) -> None:
        active = self._require_active(handle)
        active.provider.close(active.resource)
        del self._active[(handle._slot, handle._generation)]

    @property
    def active_count(self) -> int:
        return len(self._active)

    def scope(self) -> ResourceScope:
        return ResourceScope(self)

    def _require_active(self, handle: ResourceHandle) -> _ActiveResource:
        if not isinstance(handle, ResourceHandle) or handle._registry is not self:
            raise ResourceClosedError("resource handle belongs to another registry")
        active = self._active.get((handle._slot, handle._generation))
        if active is None:
            raise ResourceClosedError("resource handle is closed")
        return active


class ResourceScope:
    """Deterministic resource cleanup scope for normal and exceptional exits."""

    def __init__(self, registry: ResourceRegistry) -> None:
        self._registry = registry
        self._handles: list[ResourceHandle] = []

    def __enter__(self) -> ResourceScope:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close_all()
        return False

    def open(self, capability: CapabilityToken) -> ResourceHandle:
        handle = self._registry.open(capability)
        self._handles.append(handle)
        return handle

    def invoke(
        self,
        handle: ResourceHandle,
        arguments: tuple[DynamicValue, ...] = (),
    ) -> DynamicValue:
        return self._registry.invoke(handle, arguments)

    def close(self, handle: ResourceHandle) -> None:
        self._registry.close(handle)

    def close_all(self) -> None:
        first_error: ResourceError | None = None
        for handle in reversed(self._handles):
            if not self._registry.is_open(handle):
                continue
            try:
                self._registry.close(handle)
            except ResourceError as error:
                if first_error is None:
                    first_error = error
        if first_error is not None:
            raise first_error


class SourceResourceRuntime:
    """Deterministic bounded provider used by the source/IR fixture API."""

    _MAX_SLOTS = 3

    def __init__(self) -> None:
        self._generations = [0] * self._MAX_SLOTS
        self._active: dict[int, tuple[int, int, int]] = {}

    def grant(self, kind: object) -> int:
        if isinstance(kind, bool) or not isinstance(kind, int) or not 1 <= kind <= 3:
            raise ResourceCapabilityError("resource capability kind is unavailable")
        return kind

    def open(self, capability: object) -> int:
        kind = self.grant(capability)
        for slot in range(self._MAX_SLOTS):
            if all(active[1] != slot for active in self._active.values()):
                self._generations[slot] += 1
                generation = self._generations[slot]
                handle = (kind << 56) | ((slot + 1) << 48) | generation
                self._active[handle] = (kind, slot, generation)
                return handle
        raise ResourceLimitError("active resource limit exceeded")

    def is_open(self, handle: object) -> int:
        return -1 if handle in self._active else 0

    def kind(self, handle: object) -> int:
        return self._require(handle)[0]

    def invoke(self, handle: object, argument: object) -> int:
        del argument
        self._require(handle)
        return 0

    def close(self, handle: object) -> None:
        self._active.pop(handle, None) or self._raise_closed()

    def _require(self, handle: object) -> tuple[int, int, int]:
        try:
            return self._active[handle]
        except (KeyError, TypeError) as error:
            raise ResourceClosedError("resource handle is closed") from error

    @staticmethod
    def _raise_closed() -> None:
        raise ResourceClosedError("resource handle is closed")


class HostServiceRegistry:
    """A local dependency-injected registry with no implicit host access."""

    def __init__(self) -> None:
        self._handlers: dict[HostService, HostServiceHandler] = {}

    def register(self, service: HostService, handler: HostServiceHandler) -> None:
        if not isinstance(service, HostService):
            raise HostServiceError("service must be a HostService")
        if service in self._handlers:
            raise HostServiceError(f"host service already registered: {service.value}")
        self._handlers[service] = handler

    def invoke(self, request: HostServiceRequest) -> DynamicValue:
        handler = self._handlers.get(request.service)
        if handler is None:
            raise HostServiceError(f"host service unavailable: {request.service.value}")
        result = handler(request.arguments)
        if not isinstance(result, DynamicValue):
            raise HostServiceError("host service handler must return DynamicValue")
        return result
