"""Bounded offline package registry v2 resolution for M1.95."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from .registry_security import canonical_https_origin, read_bounded_bytes


class RegistryV2Error(ValueError):
    pass


_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?(?:\.(0|[1-9][0-9]*))?$")


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


@dataclass(frozen=True, order=True, slots=True)
class _SemVer:
    major: int
    minor: int
    patch: int


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
        selected: dict[str, RegistryV2Entry] = {}
        active: set[tuple[str, str]] = set()

        def visit(entry: RegistryV2Entry, depth: int) -> None:
            identity = (entry.lock.name, entry.lock.version)
            if depth > self.limits.max_dependency_depth:
                raise RegistryV2Error("registry dependency depth limit exceeded")
            if identity in active:
                raise RegistryV2Error("registry dependency cycle detected")
            previous = selected.get(entry.lock.name)
            if previous is not None and previous.lock.version != entry.lock.version:
                raise RegistryV2Error("registry dependency version conflict")
            if previous is not None:
                return
            if len(ordered) >= self.limits.max_resolved_packages:
                raise RegistryV2Error("registry resolved package limit exceeded")
            active.add(identity)
            selected[entry.lock.name] = entry
            ordered.append(entry.lock)
            for dependency in sorted(entry.dependencies, key=lambda item: (item.name, item.version, item.sha256)):
                visit(self._entry(dependency.name, dependency.version, dependency.sha256), depth + 1)
            active.remove(identity)

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
            body = read_bounded_bytes(path, self.limits.max_cache_bytes, label="registry v2 object")
        except ValueError as error:
            raise RegistryV2Error(str(error)) from error
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
        if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
            raise RegistryV2Error("registry v2 package constraint is invalid")
        matches = tuple(
            item
            for item in self._entries
            if item.lock.name == name and _constraint_matches(item.lock.version, version)
        )
        if digest is not None:
            matches = tuple(item for item in matches if item.lock.sha256 == digest)
        if len(matches) != 1:
            if not matches:
                raise RegistryV2Error("registry v2 package identity or compatible version is missing")
            # A range may select one highest compatible version only.  Equal
            # versions remain impossible because index identities are unique.
            ordered = sorted(matches, key=lambda item: (_parse_version(item.lock.version), item.lock.sha256), reverse=True)
            if len(ordered) > 1 and _parse_version(ordered[0].lock.version) == _parse_version(ordered[1].lock.version):
                raise RegistryV2Error("registry v2 package identity is ambiguous")
            return ordered[0]
        return matches[0]

    def _load_index(self) -> tuple[RegistryV2Entry, ...]:
        path = self.root / "index.json"
        try:
            raw_bytes = read_bounded_bytes(path, self.limits.max_index_bytes, label="registry v2 index")
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
    try:
        return canonical_https_origin(origin)
    except ValueError as error:
        raise RegistryV2Error("registry origin must be a canonical HTTPS identity") from error


def _parse_version(value: str) -> _SemVer:
    match = _VERSION.fullmatch(value)
    if match is None:
        raise RegistryV2Error(f"invalid semantic version or constraint: {value!r}")
    numbers = [int(item) if item is not None else 0 for item in match.groups()]
    return _SemVer(*numbers)


def _constraint_matches(version: str, constraint: str) -> bool:
    if not isinstance(constraint, str) or not constraint or any(character.isspace() for character in constraint):
        raise RegistryV2Error("registry version constraint is invalid")
    candidate = _parse_version(version)
    if constraint in {"*", "x", "X"}:
        return True
    if constraint.startswith("^"):
        base = _parse_version(constraint[1:])
        upper = _SemVer(base.major + 1, 0, 0) if base.major else _SemVer(0, base.minor + 1, 0)
        return base <= candidate < upper
    if constraint.startswith("~"):
        base = _parse_version(constraint[1:])
        return base <= candidate < _SemVer(base.major, base.minor + 1, 0)
    if constraint.startswith((">", "<")) or "," in constraint:
        for part in constraint.split(","):
            if len(part) < 2 or part[:2] not in {">=", "<=", "=="} and part[0] not in "><":
                raise RegistryV2Error("registry version comparator is invalid")
            operator = part[:2] if part[:2] in {">=", "<=", "=="} else part[0]
            target = _parse_version(part[len(operator):])
            if operator == ">=" and not candidate >= target:
                return False
            if operator == "<=" and not candidate <= target:
                return False
            if operator == "==" and not candidate == target:
                return False
            if operator == ">" and not candidate > target:
                return False
            if operator == "<" and not candidate < target:
                return False
        return True
    if constraint.endswith((".*", ".x", ".X")):
        prefix = constraint.rsplit(".", 1)[0]
        parts = prefix.split(".")
        if len(parts) not in {1, 2} or any(not item.isdigit() for item in parts):
            raise RegistryV2Error("registry wildcard constraint is invalid")
        return candidate.major == int(parts[0]) and (len(parts) == 1 or candidate.minor == int(parts[1]))
    return candidate == _parse_version(constraint)
