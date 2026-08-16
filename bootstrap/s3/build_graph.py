"""Deterministic local build graph and lockfile model for M1.45."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from dataclasses import dataclass, field
from heapq import heapify, heappop, heappush
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .optimizer import OptimizationLevel
from .targets import builtin_target_catalog


class BuildGraphError(ValueError):
    """Raised when a local build graph cannot be resolved deterministically."""


_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")
_LOCKFILE_FORMAT = 1


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _sha256(value: bytes | str) -> str:
    payload = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(payload).hexdigest()


def _sorted_unique(values: object, *, field: str) -> tuple[str, ...]:
    if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values):
        raise BuildGraphError(f"{field} must be a list of non-empty strings")
    result = tuple(sorted(values))
    if len(set(result)) != len(result):
        raise BuildGraphError(f"{field} must not contain duplicates")
    return result


def _relative_path(value: object, *, field: str, allow_dot: bool = False) -> str:
    if not isinstance(value, str) or not value:
        raise BuildGraphError(f"{field} must be a non-empty relative path")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts:
        raise BuildGraphError(f"{field} must stay inside the project root")
    if normalized == "." and allow_dot:
        return "."
    if normalized == "." or not path.parts:
        raise BuildGraphError(f"{field} must name a relative path")
    return "/".join(path.parts)


def _name(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _NAME.fullmatch(value) is None:
        raise BuildGraphError(f"invalid {field} {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class ForeignLibrary:
    name: str
    target: str
    kind: str = "system"
    path: str | None = None

    def __post_init__(self) -> None:
        _name(self.name, field="foreign library name")
        if not self.target:
            raise BuildGraphError("foreign library target must be non-empty")
        if self.kind not in {"system", "static", "shared"}:
            raise BuildGraphError(f"unsupported foreign library kind {self.kind!r}")
        if self.path is not None:
            object.__setattr__(
                self,
                "path",
                _relative_path(self.path, field="foreign library path"),
            )


@dataclass(frozen=True, slots=True)
class BuildUnit:
    name: str
    path: str
    sources: tuple[str, ...]
    dependencies: tuple[str, ...] = ()
    foreign_libraries: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _name(self.name, field="unit name")
        object.__setattr__(
            self,
            "path",
            _relative_path(self.path, field=f"unit {self.name} path", allow_dot=True),
        )
        if not self.sources or tuple(sorted(set(self.sources))) != self.sources:
            raise BuildGraphError(f"unit {self.name!r} sources must be sorted and unique")
        for source in self.sources:
            _relative_path(source, field=f"unit {self.name} source")
        if tuple(sorted(set(self.dependencies))) != self.dependencies:
            raise BuildGraphError(f"unit {self.name!r} dependencies must be sorted and unique")
        if tuple(sorted(set(self.foreign_libraries))) != self.foreign_libraries:
            raise BuildGraphError(
                f"unit {self.name!r} foreign libraries must be sorted and unique"
            )


@dataclass(frozen=True, slots=True)
class TargetProfile:
    target: str
    profile: str
    optimization: str

    def __post_init__(self) -> None:
        if not self.target or not self.profile:
            raise BuildGraphError("target and profile must be non-empty")
        try:
            parsed = OptimizationLevel.parse(self.optimization)
        except ValueError as error:
            raise BuildGraphError(str(error)) from error
        object.__setattr__(self, "optimization", parsed.value)


@dataclass(frozen=True, slots=True)
class BuildPlanStep:
    unit_name: str
    dependencies: tuple[str, ...]
    artifact_identity: str


@dataclass(frozen=True, slots=True)
class BuildGraph:
    name: str
    root: Path
    units: tuple[BuildUnit, ...]
    target_profile: TargetProfile
    foreign_libraries: tuple[ForeignLibrary, ...] = ()
    _source_records_snapshot: tuple[tuple[str, tuple[dict[str, str], ...]], ...] = field(
        init=False,
        repr=False,
    )
    _foreign_records_snapshot: tuple[dict[str, str | None], ...] = field(
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        _name(self.name, field="project name")
        object.__setattr__(self, "root", Path(self.root).resolve())
        unit_names = tuple(unit.name for unit in self.units)
        if unit_names != tuple(sorted(unit_names)) or len(set(unit_names)) != len(unit_names):
            raise BuildGraphError("project units must be sorted and unique")
        foreign_names = tuple(item.name for item in self.foreign_libraries)
        if foreign_names != tuple(sorted(foreign_names)) or len(set(foreign_names)) != len(foreign_names):
            raise BuildGraphError("foreign libraries must be sorted and unique")
        self.topological_order
        object.__setattr__(
            self,
            "_source_records_snapshot",
            tuple(
                (unit.name, self._read_source_records(unit))
                for unit in self.units
            ),
        )
        object.__setattr__(self, "_foreign_records_snapshot", self._read_foreign_records())
        known_foreign = set(foreign_names)
        for unit in self.units:
            unknown = set(unit.foreign_libraries) - known_foreign
            if unknown:
                missing = sorted(unknown)[0]
                raise BuildGraphError(
                    f"missing foreign library '{missing}' referenced by unit '{unit.name}'"
                )

    @classmethod
    def from_toml(cls, manifest_path: str | Path) -> BuildGraph:
        path = Path(manifest_path).resolve()
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except OSError as error:
            raise BuildGraphError(f"cannot read manifest {path}: {error}") from error
        except tomllib.TOMLDecodeError as error:
            raise BuildGraphError(f"invalid s3.toml: {error}") from error
        return cls.from_mapping(data, manifest_path=path)

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        *,
        manifest_path: str | Path | None = None,
    ) -> BuildGraph:
        project = data.get("project")
        if not isinstance(project, Mapping):
            raise BuildGraphError("s3.toml requires a [project] table")
        manifest = Path(manifest_path).resolve() if manifest_path is not None else None
        base = manifest.parent if manifest is not None else Path.cwd()
        root_value = project.get("root", ".")
        root_relative = _relative_path(root_value, field="project root", allow_dot=True)
        root = (base / root_relative).resolve()
        profile_name = project.get("profile", "debug")
        profile_name = _name(profile_name, field="profile")
        profiles = data.get("profiles", {})
        profile_data = profiles.get(profile_name, {}) if isinstance(profiles, Mapping) else {}
        if not isinstance(profile_data, Mapping):
            raise BuildGraphError(f"profile {profile_name!r} must be a table")
        target = project.get("target", "linux-x86_64")
        try:
            builtin_target_catalog().get(target)
        except (TypeError, ValueError) as error:
            raise BuildGraphError(f"unsupported target {target!r}") from error
        optimization = profile_data.get("optimization", "O0")
        target_profile = TargetProfile(target, profile_name, optimization)

        raw_units = data.get("unit", [])
        if not isinstance(raw_units, list) or not raw_units:
            raise BuildGraphError("s3.toml requires at least one [[unit]]")
        units: list[BuildUnit] = []
        for raw in raw_units:
            if not isinstance(raw, Mapping):
                raise BuildGraphError("each [[unit]] must be a table")
            unit_name = _name(raw.get("name"), field="unit name")
            units.append(
                BuildUnit(
                    unit_name,
                    _relative_path(raw.get("path", "."), field=f"unit {unit_name} path", allow_dot=True),
                    _sorted_unique(raw.get("sources"), field=f"unit {unit_name} sources"),
                    _sorted_unique(raw.get("dependencies", []), field=f"unit {unit_name} dependencies"),
                    _sorted_unique(
                        raw.get("foreign_libraries", []),
                        field=f"unit {unit_name} foreign libraries",
                    ),
                )
            )

        raw_foreign = data.get("foreign_library", [])
        if not isinstance(raw_foreign, list):
            raise BuildGraphError("foreign_library entries must be tables")
        foreign: list[ForeignLibrary] = []
        for raw in raw_foreign:
            if not isinstance(raw, Mapping):
                raise BuildGraphError("each [[foreign_library]] must be a table")
            name = _name(raw.get("name"), field="foreign library name")
            foreign.append(
                ForeignLibrary(
                    name,
                    raw.get("target", target),
                    raw.get("kind", "system"),
                    raw.get("path"),
                )
            )
        return cls(
            project.get("name"),
            root,
            tuple(sorted(units, key=lambda unit: unit.name)),
            target_profile,
            tuple(sorted(foreign, key=lambda item: item.name)),
        )

    @property
    def _units_by_name(self) -> dict[str, BuildUnit]:
        return {unit.name: unit for unit in self.units}

    @property
    def topological_order(self) -> tuple[str, ...]:
        units = self._units_by_name
        reverse: dict[str, list[str]] = {name: [] for name in units}
        remaining: dict[str, int] = {}
        for unit in self.units:
            missing = sorted(set(unit.dependencies) - set(units))
            if missing:
                raise BuildGraphError(
                    f"missing dependency '{missing[0]}' referenced by unit '{unit.name}'"
                )
            remaining[unit.name] = len(unit.dependencies)
            for dependency in unit.dependencies:
                reverse[dependency].append(unit.name)
        ready = [name for name, count in remaining.items() if count == 0]
        heapify(ready)
        order: list[str] = []
        while ready:
            name = heappop(ready)
            order.append(name)
            for dependent in sorted(reverse[name]):
                remaining[dependent] -= 1
                if remaining[dependent] == 0:
                    heappush(ready, dependent)
        if len(order) != len(units):
            cycle = sorted(name for name, count in remaining.items() if count)
            raise BuildGraphError(f"dependency cycle involving: {', '.join(cycle)}")
        return tuple(order)

    def _unit_root(self, unit: BuildUnit) -> Path:
        path = (self.root / unit.path).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as error:
            raise BuildGraphError(f"unit '{unit.name}' escapes project root") from error
        if not path.is_dir():
            raise BuildGraphError(f"missing unit directory for '{unit.name}': {unit.path}")
        return path

    def _read_source_records(self, unit: BuildUnit) -> tuple[dict[str, str], ...]:
        unit_root = self._unit_root(unit)
        records: list[dict[str, str]] = []
        for source in unit.sources:
            path = (unit_root / source).resolve()
            try:
                path.relative_to(unit_root)
            except ValueError as error:
                raise BuildGraphError(
                    f"source '{source}' escapes unit '{unit.name}'"
                ) from error
            if not path.is_file():
                raise BuildGraphError(
                    f"missing source '{source}' in unit '{unit.name}'"
                )
            records.append(
                {
                    "path": source,
                    "sha256": _sha256(path.read_bytes()),
                }
            )
        return tuple(records)

    def _source_records(self, unit: BuildUnit) -> tuple[dict[str, str], ...]:
        return dict(self._source_records_snapshot)[unit.name]

    def _read_foreign_records(self) -> tuple[dict[str, str | None], ...]:
        records: list[dict[str, str | None]] = []
        for library in self.foreign_libraries:
            digest: str | None = None
            if library.path is not None:
                path = (self.root / library.path).resolve()
                try:
                    path.relative_to(self.root)
                except ValueError as error:
                    raise BuildGraphError(
                        f"foreign library '{library.name}' escapes project root"
                    ) from error
                if not path.is_file():
                    raise BuildGraphError(
                        f"missing foreign library '{library.name}' at {library.path}"
                    )
                digest = _sha256(path.read_bytes())
            records.append(
                {
                    "name": library.name,
                    "target": library.target,
                    "kind": library.kind,
                    "path": library.path,
                    "sha256": digest,
                }
            )
        return tuple(records)

    def _foreign_records(self) -> tuple[dict[str, str | None], ...]:
        return self._foreign_records_snapshot

    def _unit_payload(self, unit: BuildUnit) -> dict[str, object]:
        return {
            "name": unit.name,
            "path": unit.path,
            "sources": list(self._source_records(unit)),
            "dependencies": list(unit.dependencies),
            "foreign_libraries": list(unit.foreign_libraries),
        }

    def _base_payload(self) -> dict[str, object]:
        return {
            "format": _LOCKFILE_FORMAT,
            "project": self.name,
            "target_profile": {
                "target": self.target_profile.target,
                "profile": self.target_profile.profile,
                "optimization": self.target_profile.optimization,
            },
            "topological_order": list(self.topological_order),
            "foreign_libraries": list(self._foreign_records()),
            "units": [self._unit_payload(unit) for unit in self.units],
        }

    @property
    def graph_sha256(self) -> str:
        return _sha256(_canonical_json(self._base_payload()))

    @property
    def unit_artifact_identities(self) -> dict[str, str]:
        identities: dict[str, str] = {}
        for name in self.topological_order:
            unit = self._units_by_name[name]
            payload = {
                "graph": self.graph_sha256,
                "target_profile": {
                    "target": self.target_profile.target,
                    "profile": self.target_profile.profile,
                    "optimization": self.target_profile.optimization,
                },
                "unit": self._unit_payload(unit),
                "dependencies": [identities[dependency] for dependency in unit.dependencies],
            }
            identities[name] = _sha256(_canonical_json(payload))
        return identities

    @property
    def artifact_identity(self) -> str:
        return _sha256(
            _canonical_json(
                {
                    "graph": self.graph_sha256,
                    "units": self.unit_artifact_identities,
                }
            )
        )

    @property
    def build_plan(self) -> tuple[BuildPlanStep, ...]:
        identities = self.unit_artifact_identities
        return tuple(
            BuildPlanStep(name, self._units_by_name[name].dependencies, identities[name])
            for name in self.topological_order
        )

    @property
    def lockfile_payload(self) -> dict[str, object]:
        base = self._base_payload()
        base["graph_sha256"] = self.graph_sha256
        base["artifact_identity"] = self.artifact_identity
        base["unit_artifact_identities"] = self.unit_artifact_identities
        return base

    @property
    def lockfile_text(self) -> str:
        return json.dumps(self.lockfile_payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n"

    @property
    def lockfile_sha256(self) -> str:
        return _sha256(self.lockfile_text)

    def write_lockfile(self, path: str | Path) -> None:
        Path(path).write_text(self.lockfile_text, encoding="utf-8", newline="\n")

    def load_sources(self) -> dict[str, str]:
        """Load all graph sources in topological unit order for the compiler."""
        result: dict[str, str] = {}
        for name in self.topological_order:
            unit = self._units_by_name[name]
            unit_root = self._unit_root(unit)
            for source in unit.sources:
                logical_path = f"{unit.name}/{source}"
                path = unit_root / source
                expected = next(
                    record["sha256"]
                    for record in self._source_records(unit)
                    if record["path"] == source
                )
                if _sha256(path.read_bytes()) != expected:
                    raise BuildGraphError(
                        f"source '{source}' in unit '{unit.name}' changed after graph resolution"
                    )
                result[logical_path] = path.read_text(encoding="utf-8")
        return result
