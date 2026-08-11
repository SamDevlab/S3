"""Explicit, injectable host-service contracts for M1.36."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import subprocess
from typing import Sequence
from typing import Callable

from .dynamic import DynamicValue


class HostServiceError(RuntimeError):
    """Raised for an unavailable or incorrectly invoked host service."""


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
