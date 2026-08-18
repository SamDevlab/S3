"""Offline content-addressed package registry client for S3 M1.79."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import tarfile
from typing import Iterable


class RegistryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RegistryLock:
    name: str
    version: str
    sha256: str

    def __post_init__(self) -> None:
        if not self.name or not self.version or len(self.sha256) != 64 or any(char not in "0123456789abcdef" for char in self.sha256):
            raise RegistryError("registry lock requires canonical name, version, and lowercase SHA-256")

    @property
    def payload(self) -> dict[str, str]:
        return {"name": self.name, "sha256": self.sha256, "version": self.version}


@dataclass(frozen=True, slots=True)
class RegistryEntry:
    lock: RegistryLock
    object_name: str


@dataclass(frozen=True, slots=True)
class RegistryArtifact:
    lock: RegistryLock
    archive: bytes


class RegistryClient:
    """Read-only local registry with immutable object identity."""

    def __init__(self, root: Path, *, cache: Path | None = None, max_archive_bytes: int = 16 * 1024 * 1024) -> None:
        self.root = Path(root)
        self.cache = Path(cache) if cache is not None else self.root / "cache"
        if isinstance(max_archive_bytes, bool) or not isinstance(max_archive_bytes, int) or max_archive_bytes <= 0:
            raise ValueError("max_archive_bytes must be positive")
        self.max_archive_bytes = max_archive_bytes
        self._entries = self._load_index()

    @property
    def read_only(self) -> bool:
        return True

    def resolve(self, name: str, version: str) -> RegistryLock:
        matches = tuple(entry.lock for entry in self._entries if entry.lock.name == name and entry.lock.version == version)
        if len(matches) != 1:
            raise RegistryError("exact registry identity is missing or ambiguous")
        return matches[0]

    def fetch(self, lock: RegistryLock) -> RegistryArtifact:
        entry = next((item for item in self._entries if item.lock == lock), None)
        if entry is None:
            raise RegistryError("registry lock is not present in the immutable index")
        archive = self._read_cache(lock.sha256)
        if archive is None:
            archive = self._read_object(entry.object_name)
            self._write_cache(lock.sha256, archive)
        self._verify(lock, archive)
        return RegistryArtifact(lock, archive)

    def install(self, artifact: RegistryArtifact, destination: Path, *, max_members: int = 4096) -> tuple[str, ...]:
        self._verify(artifact.lock, artifact.archive)
        if isinstance(max_members, bool) or not isinstance(max_members, int) or max_members <= 0:
            raise RegistryError("max_members must be positive")
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)
        try:
            archive = tarfile.open(fileobj=_BytesReader(artifact.archive), mode="r:*")
        except (tarfile.TarError, OSError) as error:
            raise RegistryError("package archive is invalid") from error
        with archive:
            members = archive.getmembers()
            if len(members) > max_members:
                raise RegistryError("package archive member limit exceeded")
            names = tuple(sorted(member.name for member in members))
            for member in members:
                target = _safe_archive_target(destination, member.name)
                if not member.isfile():
                    raise RegistryError(f"archive member is not a regular file: {member.name!r}")
                source = archive.extractfile(member)
                if source is None:
                    raise RegistryError(f"archive member cannot be read: {member.name!r}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read())
        return names

    def publish(self, _artifact: RegistryArtifact) -> None:
        raise RegistryError("registry client is read-only; publishing is not implemented")

    def _load_index(self) -> tuple[RegistryEntry, ...]:
        try:
            raw = json.loads((self.root / "index.json").read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RegistryError("registry index cannot be read") from error
        if raw.get("format") != "s3.registry.index.v1" or not isinstance(raw.get("packages"), list):
            raise RegistryError("unsupported registry index format")
        entries: list[RegistryEntry] = []
        seen: set[tuple[str, str, str]] = set()
        for item in raw["packages"]:
            if not isinstance(item, dict):
                raise RegistryError("registry package entry must be an object")
            lock = RegistryLock(str(item.get("name", "")), str(item.get("version", "")), str(item.get("sha256", "")))
            object_name = str(item.get("object", ""))
            if not object_name or Path(object_name).is_absolute() or ".." in PurePosixPath(object_name.replace("\\", "/")).parts:
                raise RegistryError("registry object path is unsafe")
            identity = (lock.name, lock.version, lock.sha256)
            if identity in seen:
                raise RegistryError("duplicate registry package identity")
            seen.add(identity)
            entries.append(RegistryEntry(lock, object_name))
        return tuple(sorted(entries, key=lambda item: (item.lock.name, item.lock.version, item.lock.sha256)))

    def _read_object(self, object_name: str) -> bytes:
        path = self.root / object_name
        try:
            data = path.read_bytes()
        except OSError as error:
            raise RegistryError("registry object is missing") from error
        if len(data) > self.max_archive_bytes:
            raise RegistryError("registry object exceeds configured size")
        return data

    def _read_cache(self, sha256: str) -> bytes | None:
        path = self.cache / sha256
        try:
            data = path.read_bytes()
        except OSError:
            return None
        if len(data) > self.max_archive_bytes:
            raise RegistryError("cached registry object exceeds configured size")
        return data

    def _write_cache(self, sha256: str, data: bytes) -> None:
        self.cache.mkdir(parents=True, exist_ok=True)
        (self.cache / sha256).write_bytes(data)

    def _verify(self, lock: RegistryLock, archive: bytes) -> None:
        if hashlib.sha256(archive).hexdigest() != lock.sha256:
            raise RegistryError("registry object SHA-256 does not match immutable lock")


class _BytesReader:
    def __init__(self, data: bytes) -> None:
        self._data = data
        self._position = 0

    def read(self, amount: int = -1) -> bytes:
        if amount < 0:
            amount = len(self._data) - self._position
        start = self._position
        self._position += amount
        return self._data[start:self._position]

    def tell(self) -> int:
        return self._position

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self._position = offset
        elif whence == 1:
            self._position += offset
        elif whence == 2:
            self._position = len(self._data) + offset
        else:
            raise ValueError("unsupported seek mode")
        return self._position


def _safe_archive_target(destination: Path, name: str) -> Path:
    normalized = name.replace("\\", "/")
    relative = PurePosixPath(normalized)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts or ":" in relative.parts[0]:
        raise RegistryError(f"archive path traversal rejected: {name!r}")
    target = (destination / Path(*relative.parts)).resolve()
    root = destination.resolve()
    if target != root and root not in target.parents:
        raise RegistryError(f"archive path escapes destination: {name!r}")
    return target
