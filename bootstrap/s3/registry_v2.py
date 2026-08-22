"""Bounded offline package registry v2 resolution for M1.95."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

from .registry_security import BoundedReadError, canonical_https_origin, read_bounded_bytes
from .signed_registry_index import VerifiedRegistryIndex


class RegistryV2Error(ValueError):
    pass


_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_VERSION = re.compile(r"^(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?(?:\.(0|[1-9][0-9]*))?$")
_MAX_VERSION_COMPONENT_DIGITS = 18


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
    dependencies: tuple[RegistryV2Dependency, ...] = ()


@dataclass(frozen=True, slots=True)
class RegistryV2Dependency:
    """A dependency constraint with an optional post-resolution digest pin."""

    name: str
    version_constraint: str
    integrity_sha256: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise RegistryV2Error("registry v2 dependency name is invalid")
        _validate_constraint(self.version_constraint)
        if self.integrity_sha256 is not None and _DIGEST.fullmatch(self.integrity_sha256) is None:
            raise RegistryV2Error("registry v2 dependency integrity pin is invalid")


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

    @classmethod
    def from_verified_index(
        cls,
        root: Path,
        verified_index: VerifiedRegistryIndex,
        *,
        limits: RegistryV2Limits | None = None,
    ) -> "RegistryV2Client":
        """Create a resolver from an index authenticated by signed-index trust.

        The unsigned ``index.json`` file is deliberately not read by this path.
        Callers must obtain ``verified_index`` from ``SignedRegistryIndexTrust``.
        """

        if not isinstance(verified_index, VerifiedRegistryIndex):
            raise RegistryV2Error("registry v2 requires a verified signed index")
        client = cls.__new__(cls)
        client.root = Path(root)
        client.expected_origin = _canonical_origin(verified_index.envelope.origin)
        client.limits = limits or RegistryV2Limits()
        client._entries = client._parse_index(verified_index.document)
        client._cache = OrderedDict()
        client._cache_bytes = 0
        client._resolution_cache = OrderedDict()
        return client

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
            for dependency in sorted(
                entry.dependencies,
                key=lambda item: (item.name, item.version_constraint, item.integrity_sha256 or ""),
            ):
                visit(
                    self._entry(
                        dependency.name,
                        dependency.version_constraint,
                        dependency.integrity_sha256,
                    ),
                    depth + 1,
                )
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
        path = _safe_object_path(self.root, entry.object_name)
        try:
            body = read_bounded_bytes(path, self.limits.max_cache_bytes, label="registry v2 object")
        except BoundedReadError as error:
            raise RegistryV2Error(f"registry v2 object {error.code}: {error}") from error
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
        _validate_constraint(version)
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
        except BoundedReadError as error:
            raise RegistryV2Error(f"registry v2 index {error.code}: {error}") from error
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise RegistryV2Error("registry v2 index cannot be read") from error
        return self._parse_index(raw)

    def _parse_index(self, raw: object) -> tuple[RegistryV2Entry, ...]:
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
            _validate_object_name(object_name)
            raw_dependencies = item.get("dependencies", [])
            if not isinstance(raw_dependencies, list) or len(raw_dependencies) > self.limits.max_packages:
                raise RegistryV2Error("registry v2 dependency list is invalid")
            dependencies: list[RegistryV2Dependency] = []
            for dependency in raw_dependencies:
                if not isinstance(dependency, dict):
                    raise RegistryV2Error("registry v2 dependency must be an object")
                integrity = dependency.get("sha256")
                if integrity is not None and not isinstance(integrity, str):
                    raise RegistryV2Error("registry v2 dependency integrity pin is invalid")
                dependencies.append(
                    RegistryV2Dependency(
                        str(dependency.get("name", "")),
                        str(dependency.get("version", "")),
                        integrity,
                    )
                )
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
    if any(item is not None and len(item) > _MAX_VERSION_COMPONENT_DIGITS for item in match.groups()):
        raise RegistryV2Error("semantic version component exceeds the bounded width")
    numbers = [int(item) if item is not None else 0 for item in match.groups()]
    return _SemVer(*numbers)


def _wildcard_bounds(raw: str, *, caret: bool) -> tuple[_SemVer, _SemVer] | None:
    parts = raw.split(".")
    if not any(part in {"x", "X", "*"} for part in parts):
        return None
    if len(parts) > 3 or any(part in {"x", "X", "*"} for part in parts[:-1]) or parts[-1] not in {"x", "X", "*"}:
        raise RegistryV2Error("wildcard version constraint is invalid")
    if any(not part.isdigit() for part in parts[:-1]):
        raise RegistryV2Error("wildcard version component is invalid")
    numeric = [int(part) for part in parts[:-1]]
    if any(len(part) > _MAX_VERSION_COMPONENT_DIGITS or (len(part) > 1 and part.startswith("0")) for part in parts[:-1]):
        raise RegistryV2Error("wildcard version component is invalid")
    major = numeric[0] if numeric else 0
    minor = numeric[1] if len(numeric) > 1 else 0
    base = _SemVer(major, minor, 0)
    if caret:
        if len(parts) == 1 or (len(parts) == 2 and major == 0):
            upper = _SemVer(major + 1 if major else 1, 0, 0)
        elif major:
            upper = _SemVer(major + 1, 0, 0)
        else:
            upper = _SemVer(0, minor + 1, 0)
    elif len(parts) == 1:
        upper = _SemVer(major + 1, 0, 0)
    else:
        upper = _SemVer(major, minor + 1, 0)
    return base, upper


def _caret_bounds(raw: str) -> tuple[_SemVer, _SemVer]:
    wildcard = _wildcard_bounds(raw, caret=True)
    if wildcard is not None:
        return wildcard
    base = _parse_version(raw)
    if base.major:
        upper = _SemVer(base.major + 1, 0, 0)
    elif base.minor:
        upper = _SemVer(0, base.minor + 1, 0)
    else:
        upper = _SemVer(0, 0, base.patch + 1)
    return base, upper


def _tilde_bounds(raw: str) -> tuple[_SemVer, _SemVer]:
    wildcard = _wildcard_bounds(raw, caret=False)
    if wildcard is not None:
        return wildcard
    base = _parse_version(raw)
    return base, _SemVer(base.major, base.minor + 1, 0)


def _validate_constraint(constraint: str) -> None:
    if not isinstance(constraint, str) or not constraint or any(character.isspace() for character in constraint):
        raise RegistryV2Error("registry version constraint is invalid")
    if constraint in {"*", "x", "X"}:
        return
    if constraint.startswith("^") or constraint.startswith("~"):
        (_caret_bounds if constraint.startswith("^") else _tilde_bounds)(constraint[1:])
        return
    if constraint.startswith((">", "<")) or "," in constraint:
        for part in constraint.split(","):
            if len(part) < 2 or (part[:2] not in {">=", "<=", "=="} and part[0] not in "><"):
                raise RegistryV2Error("registry version comparator is invalid")
            operator = part[:2] if part[:2] in {">=", "<=", "=="} else part[0]
            _parse_version(part[len(operator):])
        return
    if constraint.endswith((".*", ".x", ".X")):
        prefix = constraint.rsplit(".", 1)[0]
        parts = prefix.split(".")
        if len(parts) not in {1, 2} or any(not item.isdigit() or (len(item) > 1 and item.startswith("0")) for item in parts):
            raise RegistryV2Error("registry wildcard constraint is invalid")
        return
    _parse_version(constraint)


def _constraint_matches(version: str, constraint: str) -> bool:
    _validate_constraint(constraint)
    candidate = _parse_version(version)
    if constraint in {"*", "x", "X"}:
        return True
    if constraint.startswith("^"):
        base, upper = _caret_bounds(constraint[1:])
        return base <= candidate < upper
    if constraint.startswith("~"):
        base, upper = _tilde_bounds(constraint[1:])
        return base <= candidate < upper
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


def _validate_object_name(object_name: str) -> None:
    if not isinstance(object_name, str) or not object_name or "\x00" in object_name or "\\" in object_name:
        raise RegistryV2Error("registry v2 object path is unsafe")
    raw_parts = object_name.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise RegistryV2Error("registry v2 object path is unsafe")
    posix = PurePosixPath(object_name)
    windows = PureWindowsPath(object_name)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise RegistryV2Error("registry v2 object path is unsafe")


def _safe_object_path(root: Path, object_name: str) -> Path:
    _validate_object_name(object_name)
    root_resolved = Path(root).resolve()
    candidate = (root_resolved / PurePosixPath(object_name)).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as error:
        raise RegistryV2Error("registry v2 object path escapes registry root") from error
    return candidate
