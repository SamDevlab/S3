"""Offline content-addressed package registry client for S3 M1.79."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import tarfile


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


@dataclass(frozen=True, slots=True)
class _ValidatedMember:
    member: tarfile.TarInfo
    canonical_name: str
    target: Path


class RegistryClient:
    """Read-only local registry with immutable identity and bounded extraction."""

    def __init__(
        self,
        root: Path,
        *,
        cache: Path | None = None,
        max_archive_bytes: int = 16 * 1024 * 1024,
        max_member_bytes: int = 16 * 1024 * 1024,
        max_extracted_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        self.root = Path(root)
        self.cache = Path(cache) if cache is not None else self.root / "cache"
        for name, value in (
            ("max_archive_bytes", max_archive_bytes),
            ("max_member_bytes", max_member_bytes),
            ("max_extracted_bytes", max_extracted_bytes),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be positive")
        self.max_archive_bytes = max_archive_bytes
        self.max_member_bytes = max_member_bytes
        self.max_extracted_bytes = max_extracted_bytes
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
        try:
            archive = tarfile.open(fileobj=_BytesReader(artifact.archive), mode="r:*")
        except (tarfile.TarError, OSError) as error:
            raise RegistryError("package archive is invalid") from error
        with archive:
            members = archive.getmembers()
            if len(members) > max_members:
                raise RegistryError("package archive member limit exceeded")
            validated = self._validate_members(destination, members)
            destination.mkdir(parents=True, exist_ok=True)
            actual_total = 0
            for item in validated:
                source = archive.extractfile(item.member)
                if source is None:
                    raise RegistryError(f"archive member cannot be read: {item.canonical_name!r}")
                data = source.read(item.member.size + 1)
                if len(data) != item.member.size:
                    raise RegistryError(f"archive member size mismatch: {item.canonical_name!r}")
                actual_total += len(data)
                if actual_total > self.max_extracted_bytes:
                    raise RegistryError("package extracted byte limit exceeded")
                item.target.parent.mkdir(parents=True, exist_ok=True)
                item.target.write_bytes(data)
        return tuple(sorted(item.canonical_name for item in validated))

    def publish(self, _artifact: RegistryArtifact) -> None:
        raise RegistryError("registry client is read-only; publishing is not implemented")

    def _validate_members(self, destination: Path, members: list[tarfile.TarInfo]) -> tuple[_ValidatedMember, ...]:
        validated: list[_ValidatedMember] = []
        canonical_paths: set[str] = set()
        total = 0
        for member in members:
            if not member.isfile():
                raise RegistryError(f"archive member is not a regular file: {member.name!r}")
            if isinstance(member.size, bool) or not isinstance(member.size, int) or member.size < 0:
                raise RegistryError(f"archive member has invalid size: {member.name!r}")
            if member.size > self.max_member_bytes:
                raise RegistryError(f"archive member exceeds configured size: {member.name!r}")
            total += member.size
            if total > self.max_extracted_bytes:
                raise RegistryError("package extracted byte limit exceeded")
            canonical_name = _canonical_archive_name(member.name)
            if canonical_name in canonical_paths:
                raise RegistryError(f"duplicate canonical archive path: {canonical_name!r}")
            canonical_paths.add(canonical_name)
            validated.append(_ValidatedMember(member, canonical_name, _safe_archive_target(destination, canonical_name)))
        return tuple(validated)

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


def _canonical_archive_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    relative = PurePosixPath(normalized)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts or ":" in relative.parts[0]:
        raise RegistryError(f"archive path traversal rejected: {name!r}")
    parts = tuple(part for part in relative.parts if part not in {"", "."})
    if not parts:
        raise RegistryError(f"archive path is empty: {name!r}")
    return "/".join(parts)


def _safe_archive_target(destination: Path, name: str) -> Path:
    canonical = _canonical_archive_name(name)
    relative = PurePosixPath(canonical)
    target = (destination / Path(*relative.parts)).resolve()
    root = destination.resolve()
    if target != root and root not in target.parents:
        raise RegistryError(f"archive path escapes destination: {name!r}")
    return target
