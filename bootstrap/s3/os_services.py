"""Bounded cross-platform OS services for M1.66."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import subprocess
from typing import Sequence, TextIO

from .host_services import ProcessResult
from .results import Option, Result


MAX_PROCESS_TIMEOUT_SECONDS = 30.0


class HostErrorCode(Enum):
    INVALID_PATH = "invalid_path"
    NOT_FOUND = "not_found"
    ACCESS_DENIED = "access_denied"
    IO = "io"
    PROCESS_START = "process_start"
    TIMEOUT = "timeout"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class HostOperationError:
    code: HostErrorCode
    operation: str
    detail: str


@dataclass(frozen=True, slots=True)
class HostPath:
    """A portable project-relative path; host resolution is explicit."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value or "\x00" in self.value:
            raise ValueError("host path must be a non-empty string without NUL")
        if Path(self.value).is_absolute():
            raise ValueError("HostPath must be relative; resolve host paths explicitly")

    def child(self, name: str) -> HostPath:
        if not isinstance(name, str) or not name or "/" in name or "\\" in name:
            raise ValueError("child name must be one non-empty path component")
        return HostPath(f"{self.value}/{name}")


@dataclass(frozen=True, slots=True)
class DirectoryEntry:
    name: str
    is_file: bool
    is_directory: bool


class OwnedTextFile:
    """A deterministic owned file handle with explicit close semantics."""

    def __init__(self, file: TextIO) -> None:
        self._file = file
        self._closed = False

    @property
    def closed(self) -> bool:
        return self._closed

    def read(self) -> Result[str, HostOperationError]:
        if self._closed:
            return Result.err(HostOperationError(HostErrorCode.CLOSED, "read", "file is closed"))
        try:
            return Result.ok(self._file.read())
        except OSError as error:
            return Result.err(HostOperationError(HostErrorCode.IO, "read", str(error)))

    def write(self, content: str) -> Result[None, HostOperationError]:
        if self._closed:
            return Result.err(HostOperationError(HostErrorCode.CLOSED, "write", "file is closed"))
        try:
            self._file.write(content)
            self._file.flush()
            return Result.ok(None)
        except OSError as error:
            return Result.err(HostOperationError(HostErrorCode.IO, "write", str(error)))

    def close(self) -> None:
        if not self._closed:
            self._file.close()
            self._closed = True

    def __enter__(self) -> OwnedTextFile:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self.close()
        return False


class CrossPlatformOSServices:
    """Capability-free provider whose root and ambient inputs are explicit."""

    def __init__(
        self,
        *,
        root: Path,
        argv: Sequence[str] = (),
        environment: dict[str, str] | None = None,
    ) -> None:
        self._root = Path(root).resolve()
        self._argv = tuple(str(value) for value in argv)
        self._environment = dict(os.environ if environment is None else environment)

    def argv(self) -> tuple[str, ...]:
        return self._argv

    def environment(self, name: str) -> Option[str]:
        if not isinstance(name, str) or not name or "=" in name:
            return Option.none()
        return Option.some(self._environment[name]) if name in self._environment else Option.none()

    def open_text(
        self,
        path: HostPath,
        mode: str = "r",
        *,
        encoding: str = "utf-8",
    ) -> Result[OwnedTextFile, HostOperationError]:
        resolved = self._resolve(path)
        if isinstance(resolved, HostOperationError):
            return Result.err(resolved)
        if mode not in {"r", "w", "a", "x"}:
            return Result.err(HostOperationError(HostErrorCode.IO, "open", "unsupported text mode"))
        try:
            if mode in {"w", "a", "x"}:
                resolved.parent.mkdir(parents=True, exist_ok=True)
            return Result.ok(OwnedTextFile(resolved.open(mode, encoding=encoding, newline="")))
        except FileNotFoundError as error:
            return Result.err(HostOperationError(HostErrorCode.NOT_FOUND, "open", str(error)))
        except PermissionError as error:
            return Result.err(HostOperationError(HostErrorCode.ACCESS_DENIED, "open", str(error)))
        except OSError as error:
            return Result.err(HostOperationError(HostErrorCode.IO, "open", str(error)))

    def list_directory(
        self,
        path: HostPath,
    ) -> Result[tuple[DirectoryEntry, ...], HostOperationError]:
        resolved = self._resolve(path)
        if isinstance(resolved, HostOperationError):
            return Result.err(resolved)
        try:
            entries = tuple(
                DirectoryEntry(item.name, item.is_file(), item.is_dir())
                for item in sorted(resolved.iterdir(), key=lambda item: item.name)
            )
            return Result.ok(entries)
        except FileNotFoundError as error:
            return Result.err(HostOperationError(HostErrorCode.NOT_FOUND, "list_directory", str(error)))
        except PermissionError as error:
            return Result.err(HostOperationError(HostErrorCode.ACCESS_DENIED, "list_directory", str(error)))
        except OSError as error:
            return Result.err(HostOperationError(HostErrorCode.IO, "list_directory", str(error)))

    def spawn(
        self,
        command: str,
        args: Sequence[str] = (),
        *,
        stdin: str = "",
        timeout: float = 30.0,
    ) -> Result[ProcessResult, HostOperationError]:
        try:
            normalized_args = tuple(args)
        except TypeError:
            normalized_args = None
        if (
            not isinstance(command, str)
            or not command
            or "\x00" in command
            or normalized_args is None
            or any(not isinstance(value, str) or "\x00" in value for value in normalized_args)
        ):
            return Result.err(HostOperationError(HostErrorCode.PROCESS_START, "spawn", "invalid command"))
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not 0 <= timeout <= MAX_PROCESS_TIMEOUT_SECONDS
        ):
            return Result.err(
                HostOperationError(
                    HostErrorCode.TIMEOUT,
                    "spawn",
                    f"timeout must be within [0, {MAX_PROCESS_TIMEOUT_SECONDS}] seconds",
                )
            )
        command_line = (command, *normalized_args)
        try:
            completed = subprocess.run(
                list(command_line),
                cwd=self._root,
                env=dict(self._environment),
                input=stdin,
                capture_output=True,
                text=True,
                shell=False,
                check=False,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as error:
            return Result.err(HostOperationError(HostErrorCode.TIMEOUT, "spawn", str(error)))
        except OSError as error:
            return Result.err(HostOperationError(HostErrorCode.PROCESS_START, "spawn", str(error)))
        return Result.ok(ProcessResult(command_line, completed.stdout, completed.stderr, completed.returncode))

    def _resolve(self, path: HostPath) -> Path | HostOperationError:
        if not isinstance(path, HostPath):
            return HostOperationError(HostErrorCode.INVALID_PATH, "resolve", "path must be HostPath")
        resolved = (self._root / Path(path.value)).resolve()
        try:
            resolved.relative_to(self._root)
        except ValueError:
            return HostOperationError(HostErrorCode.INVALID_PATH, "resolve", "path escapes service root")
        return resolved
