"""Bounded offline package registry v2 resolution for M1.95."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


class RegistryV2Error(ValueError):
    pass


_DIGEST = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class RegistryV2Limits:
    max_index_bytes: int = 1 << 20
    max_packages: int = 1024
    max_dependency_depth: int = 32
    max_resolved_packages: int = 1024
    max_cache_entries: int = 128
    max_cache_bytes: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        values = (
            self.max_index_bytes,
            self.max_packages,
            self.max_dependency_depth,
            self.max_resolved_packages,
            self.max_cache_entries,
            self.max_cache_bytes,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            raise ValueError("registry v2 limits must be positive integers")


@dataclass(frozen=True, slots=True)
class RegistryV2Lock:
    name: str
    version: str
    sha256: str

    def __post_init__(self) -> None:
        if not self.name or not self.version or _DIGEST.fullmatch(self.sha256) is None:
            raise RegistryV2Error("registry v2 lock requires name, version, and lowercase SHA-256")


@dataclass(frozen=True, slots=True)
class RegistryV2Entry:
    lock: RegistryV2Lock
    object_name: str
    dependencies: tuple[RegistryV2Lock, ...] = ()


@dataclass(frozen=True, slots=True)
class RegistryV2Resolution:
    root: RegistryV2Lock
    packages: tuple[RegistryV2Lock, ...]


class RegistryV2Client:
    """Read-only v2 resolver with exact identity and bounded verification."""

    def __init__(self, root: Path, *, expected_origin: str, limits: RegistryV2Limits | None = None) -> None:
        self.root = Path(root)
        self.expected_origin = _canonical_origin(expected_origin)
        self.limits = limits or RegistryV2Limits()
        self._entries = self._load_index()
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._cache_bytes = 0
        self._resolution_cache: OrderedDict[tuple[str, str], RegistryV2Resolution] = OrderedDict()

    @property
    def read_only(self) -> bool:
        return True

    def resolve(self, name: str, version: str) -> RegistryV2Resolution:
        key = (name, version)
        cached = self._resolution_cache.get(key)
        if cached is not None:
            self._resolution_cache.move_to_end(key)
            return cached
        root = self._entry(name, version, None)
        ordered: list[RegistryV2Lock] = []
        visited: set[tuple[str, str]] = set()
        active: set[tuple[str, str]] = set()

        def visit(entry: RegistryV2Entry, depth: int) -> None:
            identity = (entry.lock.name, entry.lock.version)
            if depth > self.limits.max_dependency_depth:
                raise RegistryV2Error("registry dependency depth limit exceeded")
            if identity in active:
                raise RegistryV2Error("registry dependency cycle detected")
            if identity in visited:
                return
            if len(ordered) >= self.limits.max_resolved_packages:
                raise RegistryV2Error("registry resolved package limit exceeded")
            active.add(identity)
            ordered.append(entry.lock)
            for dependency in sorted(entry.dependencies, key=lambda item: (item.name, item.version, item.sha256)):
                visit(self._entry(dependency.name, dependency.version, dependency.sha256), depth + 1)
            active.remove(identity)
            visited.add(identity)

        visit(root, 0)
        result = RegistryV2Resolution(root.lock, tuple(ordered))
        self._resolution_cache[key] = result
        self._resolution_cache.move_to_end(key)
        while len(self._resolution_cache) > self.limits.max_cache_entries:
            self._resolution_cache.popitem(last=False)
        return result

    def fetch(self, lock: RegistryV2Lock) -> bytes:
        cached = self._cache.get(lock.sha256)
        if cached is not None:
            self._cache.move_to_end(lock.sha256)
            return cached
        entry = self._entry(lock.name, lock.version, lock.sha256)
        path = self.root / entry.object_name
        try:
            body = path.read_bytes()
        except OSError as error:
            raise RegistryV2Error("registry v2 object is missing") from error
        if hashlib.sha256(body).hexdigest() != lock.sha256:
            raise RegistryV2Error("registry v2 object digest mismatch")
        if len(body) > self.limits.max_cache_bytes:
            raise RegistryV2Error("registry v2 object exceeds cache byte budget")
        previous = self._cache.pop(lock.sha256, None)
        if previous is not None:
            self._cache_bytes -= len(previous)
        while self._cache and (len(self._cache) >= self.limits.max_cache_entries or self._cache_bytes + len(body) > self.limits.max_cache_bytes):
            _old_digest, old_body = self._cache.popitem(last=False)
            self._cache_bytes -= len(old_body)
        if len(self._cache) >= self.limits.max_cache_entries or self._cache_bytes + len(body) > self.limits.max_cache_bytes:
            raise RegistryV2Error("registry v2 cache cannot admit verified object")
        self._cache[lock.sha256] = body
        self._cache_bytes += len(body)
        return body

    def publish(self, _body: bytes) -> None:
        raise RegistryV2Error("registry v2 is read-only; publishing is disabled")

    def _entry(self, name: str, version: str, digest: str | None) -> RegistryV2Entry:
        matches = tuple(item for item in self._entries if item.lock.name == name and item.lock.version == version)
        if digest is not None:
            matches = tuple(item for item in matches if item.lock.sha256 == digest)
        if len(matches) != 1:
            raise RegistryV2Error("registry v2 package identity is missing or ambiguous")
        return matches[0]

    def _load_index(self) -> tuple[RegistryV2Entry, ...]:
        path = self.root / "index.json"
        try:
            raw_bytes = path.read_bytes()
            if len(raw_bytes) > self.limits.max_index_bytes:
                raise RegistryV2Error("registry v2 index exceeds byte limit")
            raw = json.loads(raw_bytes.decode("utf-8"))
        except RegistryV2Error:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RegistryV2Error("registry v2 index cannot be read") from error
        if not isinstance(raw, dict) or raw.get("format") != "s3.registry.index.v2" or _canonical_origin(str(raw.get("origin", ""))) != self.expected_origin:
            raise RegistryV2Error("registry v2 index format or origin is invalid")
        packages = raw.get("packages")
        if not isinstance(packages, list) or not packages or len(packages) > self.limits.max_packages:
            raise RegistryV2Error("registry v2 package list is invalid or exceeds limit")
        entries: list[RegistryV2Entry] = []
        seen: set[tuple[str, str]] = set()
        for item in packages:
            if not isinstance(item, dict):
                raise RegistryV2Error("registry v2 package entry must be an object")
            lock = RegistryV2Lock(str(item.get("name", "")), str(item.get("version", "")), str(item.get("sha256", "")))
            identity = (lock.name, lock.version)
            if identity in seen:
                raise RegistryV2Error("duplicate registry v2 package identity")
            seen.add(identity)
            object_name = str(item.get("object", ""))
            if not object_name or Path(object_name).is_absolute() or ".." in PurePosixPath(object_name.replace("\\", "/")).parts:
                raise RegistryV2Error("registry v2 object path is unsafe")
            raw_dependencies = item.get("dependencies", [])
            if not isinstance(raw_dependencies, list) or len(raw_dependencies) > self.limits.max_packages:
                raise RegistryV2Error("registry v2 dependency list is invalid")
            dependencies: list[RegistryV2Lock] = []
            for dependency in raw_dependencies:
                if not isinstance(dependency, dict):
                    raise RegistryV2Error("registry v2 dependency must be an object")
                dependencies.append(RegistryV2Lock(str(dependency.get("name", "")), str(dependency.get("version", "")), str(dependency.get("sha256", ""))))
            entries.append(RegistryV2Entry(lock, object_name, tuple(dependencies)))
        return tuple(sorted(entries, key=lambda item: (item.lock.name, item.lock.version, item.lock.sha256)))


def _canonical_origin(origin: str) -> str:
    if not isinstance(origin, str) or not origin.startswith("https://") or origin.endswith("/") or any(character.isspace() for character in origin):
        raise RegistryV2Error("registry origin must be an HTTPS identity")
    return origin.lower()
