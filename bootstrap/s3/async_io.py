"""Bounded async filesystem and shell-free process I/O for M1.84."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import subprocess
from typing import Sequence

from .async_core import AsyncErrorCode, AsyncFuture, complete, fail
from .async_futures import MoveOnlyFuture


class AsyncIOErrorCode(Enum):
    INVALID_PATH = "invalid_path"
    NOT_FOUND = "not_found"
    ACCESS_DENIED = "access_denied"
    IO = "io"
    PROCESS_START = "process_start"
    TIMEOUT = "timeout"
    OUTPUT_LIMIT = "output_limit"
    SHELL_FORBIDDEN = "shell_forbidden"
    INVALID_ARGUMENT = "invalid_argument"


@dataclass(frozen=True, slots=True)
class AsyncIOError:
    code: AsyncIOErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class AsyncIOLimits:
    max_bytes: int = 1 << 20
    max_args: int = 64
    max_timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if isinstance(self.max_bytes, bool) or not isinstance(self.max_bytes, int) or self.max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")
        if isinstance(self.max_args, bool) or not isinstance(self.max_args, int) or self.max_args <= 0:
            raise ValueError("max_args must be a positive integer")
        if isinstance(self.max_timeout_seconds, bool) or not isinstance(self.max_timeout_seconds, (int, float)) or not 0 < self.max_timeout_seconds <= 300:
            raise ValueError("max_timeout_seconds must be within (0, 300]")


@dataclass(frozen=True, slots=True)
class AsyncProcessOutput:
    argv: tuple[str, ...]
    stdout: bytes
    stderr: bytes
    returncode: int


class AsyncIOService:
    """Root-confined, bounded, shell-free async I/O service."""

    def __init__(self, *, root: Path, limits: AsyncIOLimits | None = None) -> None:
        self.root = Path(root).resolve()
        self.limits = limits or AsyncIOLimits()

    def read_file(self, path: str) -> MoveOnlyFuture[bytes]:
        def operation():
            resolved = self._resolve(path, "read_file")
            if isinstance(resolved, AsyncIOError):
                return _failure(resolved)
            try:
                if resolved.stat().st_size > self.limits.max_bytes:
                    return _failure(AsyncIOError(AsyncIOErrorCode.OUTPUT_LIMIT, "read_file", "file exceeds byte budget"))
                return complete(resolved.read_bytes())
            except FileNotFoundError:
                return _failure(AsyncIOError(AsyncIOErrorCode.NOT_FOUND, "read_file", str(resolved)))
            except PermissionError:
                return _failure(AsyncIOError(AsyncIOErrorCode.ACCESS_DENIED, "read_file", str(resolved)))
            except OSError as error:
                return _failure(AsyncIOError(AsyncIOErrorCode.IO, "read_file", str(error)))
        return MoveOnlyFuture(AsyncFuture(lambda _frame: operation()))

    def write_file(self, path: str, content: bytes) -> MoveOnlyFuture[None]:
        def operation():
            resolved = self._resolve(path, "write_file")
            if isinstance(resolved, AsyncIOError):
                return _failure(resolved)
            if not isinstance(content, bytes) or len(content) > self.limits.max_bytes:
                return _failure(AsyncIOError(AsyncIOErrorCode.OUTPUT_LIMIT, "write_file", "content exceeds byte budget"))
            try:
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_bytes(content)
                return complete(None)
            except PermissionError:
                return _failure(AsyncIOError(AsyncIOErrorCode.ACCESS_DENIED, "write_file", str(resolved)))
            except OSError as error:
                return _failure(AsyncIOError(AsyncIOErrorCode.IO, "write_file", str(error)))
        return MoveOnlyFuture(AsyncFuture(lambda _frame: operation()))

    def run_process(
        self,
        command: str,
        args: Sequence[str] = (),
        *,
        stdin: bytes = b"",
        timeout: float = 30.0,
        shell: bool = False,
    ) -> MoveOnlyFuture[AsyncProcessOutput]:
        normalized = tuple(args) if not isinstance(args, str) else ()

        def operation():
            if shell:
                return _failure(AsyncIOError(AsyncIOErrorCode.SHELL_FORBIDDEN, "run_process", "shell execution is disabled"))
            if not isinstance(command, str) or not command or "\x00" in command or len(normalized) > self.limits.max_args:
                return _failure(AsyncIOError(AsyncIOErrorCode.INVALID_ARGUMENT, "run_process", "invalid command or argument count"))
            if not isinstance(stdin, bytes) or len(stdin) > self.limits.max_bytes:
                return _failure(AsyncIOError(AsyncIOErrorCode.OUTPUT_LIMIT, "run_process", "stdin exceeds byte budget"))
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= self.limits.max_timeout_seconds:
                return _failure(AsyncIOError(AsyncIOErrorCode.TIMEOUT, "run_process", "timeout exceeds service budget"))
            if any(not isinstance(value, str) or "\x00" in value for value in normalized):
                return _failure(AsyncIOError(AsyncIOErrorCode.INVALID_ARGUMENT, "run_process", "invalid process argument"))
            argv = (command, *normalized)
            try:
                completed = subprocess.run(
                    list(argv),
                    cwd=self.root,
                    input=stdin,
                    capture_output=True,
                    shell=False,
                    check=False,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                return _failure(AsyncIOError(AsyncIOErrorCode.TIMEOUT, "run_process", "process timed out"))
            except OSError as error:
                return _failure(AsyncIOError(AsyncIOErrorCode.PROCESS_START, "run_process", str(error)))
            if len(completed.stdout) > self.limits.max_bytes or len(completed.stderr) > self.limits.max_bytes:
                return _failure(AsyncIOError(AsyncIOErrorCode.OUTPUT_LIMIT, "run_process", "process output exceeds byte budget"))
            return complete(AsyncProcessOutput(argv, completed.stdout, completed.stderr, completed.returncode))
        return MoveOnlyFuture(AsyncFuture(lambda _frame: operation()))

    def _resolve(self, value: str, operation: str) -> Path | AsyncIOError:
        if not isinstance(value, str) or not value or "\x00" in value:
            return AsyncIOError(AsyncIOErrorCode.INVALID_PATH, operation, "path must be non-empty and NUL-free")
        candidate = Path(value)
        if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
            return AsyncIOError(AsyncIOErrorCode.INVALID_PATH, operation, "path must remain relative to service root")
        resolved = (self.root / candidate).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError:
            return AsyncIOError(AsyncIOErrorCode.INVALID_PATH, operation, "path escapes service root")
        return resolved


def _failure(error: AsyncIOError):
    return fail(AsyncErrorCode.CALLBACK_FAILURE, error.operation, f"{error.code.value}: {error.detail}")
