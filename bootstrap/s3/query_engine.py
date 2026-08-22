"""Deterministic, fail-closed query identities for incremental tooling."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Callable, Generic, Mapping, TypeVar


class QueryEngineError(ValueError):
    """Raised when a query identity or cache transition is invalid."""


def _digest(payload: object) -> str:
    encoded = json.dumps(
        payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _non_empty(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise QueryEngineError(f"{field} must be a non-empty string")
    return value


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class QueryKey:
    """All semantic inputs that can affect a query result."""

    source: str
    module: str
    dependencies: tuple[str, ...] = ()
    lock: str = "none"
    target: str = "linux-x86_64"
    backend: str = "assembly"
    optimization: str = "O0"
    compiler: str = "unknown"
    config: str = "default"
    generic_args: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in (
            "source", "module", "lock", "target", "backend", "optimization",
            "compiler", "config",
        ):
            _non_empty(getattr(self, field), field)
        if tuple(sorted(set(self.dependencies))) != self.dependencies:
            raise QueryEngineError("dependencies must be sorted and unique")
        if any(not isinstance(item, str) or not item.strip() for item in self.dependencies):
            raise QueryEngineError("dependencies must contain non-empty strings")
        if tuple(sorted(set(self.generic_args))) != self.generic_args:
            raise QueryEngineError("generic_args must be sorted and unique")
        if any(not isinstance(item, str) or not item.strip() for item in self.generic_args):
            raise QueryEngineError("generic_args must contain non-empty strings")

    @property
    def payload(self) -> dict[str, object]:
        return {
            "source": self.source,
            "module": self.module,
            "dependencies": list(self.dependencies),
            "lock": self.lock,
            "target": self.target,
            "backend": self.backend,
            "optimization": self.optimization,
            "compiler": self.compiler,
            "config": self.config,
            "generic_args": list(self.generic_args),
        }

    @property
    def identity(self) -> str:
        return _digest(self.payload)


@dataclass(frozen=True, slots=True)
class QueryRecord(Generic[T]):
    key: QueryKey
    value: object
    dependencies: tuple[str, ...]
    cache_hit: bool

class QueryEngine:
    """In-memory query engine with explicit dependency invalidation."""

    def __init__(self) -> None:
        self._values: dict[str, tuple[QueryKey, object, tuple[str, ...]]] = {}
        self._dependents: dict[str, set[str]] = {}

    def query(
        self,
        key: QueryKey,
        compute: Callable[[], T],
        *,
        dependencies: tuple[str, ...] = (),
    ) -> QueryRecord[T]:
        if tuple(sorted(set(dependencies))) != dependencies:
            raise QueryEngineError("query dependencies must be sorted and unique")
        if any(not isinstance(item, str) or not item for item in dependencies):
            raise QueryEngineError("query dependencies must be non-empty identities")
        identity = key.identity
        cached = self._values.get(identity)
        if cached is not None and cached[0] == key and cached[2] == dependencies:
            return QueryRecord(key, cached[1], dependencies, True)
        value = compute()
        self._values[identity] = (key, value, dependencies)
        for dependency in dependencies:
            self._dependents.setdefault(dependency, set()).add(identity)
        return QueryRecord(key, value, dependencies, False)

    def invalidate(self, identity: str) -> tuple[str, ...]:
        """Invalidate identity and all queries that depend on it."""

        _non_empty(identity, "identity")
        invalidated: set[str] = set()
        pending = [identity]
        while pending:
            current = pending.pop()
            if current in invalidated:
                continue
            invalidated.add(current)
            pending.extend(sorted(self._dependents.get(current, ())))
        for current in invalidated:
            self._values.pop(current, None)
            self._dependents.pop(current, None)
        for dependents in self._dependents.values():
            dependents.difference_update(invalidated)
        return tuple(sorted(invalidated))

    def clear(self) -> None:
        self._values.clear()
        self._dependents.clear()

    def snapshot(self) -> dict[str, object]:
        """Return metadata only; cached values are never serialized."""

        return {
            "format": "s3.query-engine.v1",
            "queries": {
                identity: {
                    "key": key.payload,
                    "dependencies": list(dependencies),
                }
                for identity, (key, _value, dependencies) in sorted(self._values.items())
            },
        }

    @classmethod
    def from_snapshot(cls, snapshot: Mapping[str, object]) -> "QueryEngine":
        """Reject persisted metadata rather than trusting unvalidated values."""

        if snapshot.get("format") != "s3.query-engine.v1":
            raise QueryEngineError("unsupported query snapshot format")
        queries = snapshot.get("queries")
        if not isinstance(queries, Mapping):
            raise QueryEngineError("query snapshot requires a queries object")
        engine = cls()
        for identity, raw in queries.items():
            if not isinstance(identity, str) or not isinstance(raw, Mapping):
                raise QueryEngineError("query snapshot entry is malformed")
            key_payload = raw.get("key")
            dependencies = raw.get("dependencies")
            if not isinstance(key_payload, Mapping) or not isinstance(dependencies, list):
                raise QueryEngineError("query snapshot entry is incomplete")
            try:
                key = QueryKey(
                    source=key_payload["source"], module=key_payload["module"],
                    dependencies=tuple(key_payload.get("dependencies", ())),
                    lock=key_payload.get("lock", "none"),
                    target=key_payload.get("target", "linux-x86_64"),
                    backend=key_payload.get("backend", "assembly"),
                    optimization=key_payload.get("optimization", "O0"),
                    compiler=key_payload.get("compiler", "unknown"),
                    config=key_payload.get("config", "default"),
                    generic_args=tuple(key_payload.get("generic_args", ())),
                )
            except (KeyError, TypeError, QueryEngineError) as error:
                raise QueryEngineError("query snapshot key is malformed") from error
            if key.identity != identity:
                raise QueryEngineError("query snapshot identity mismatch")
            normalized = tuple(dependencies)
            if tuple(sorted(set(normalized))) != normalized:
                raise QueryEngineError("query snapshot dependencies are not canonical")
            for dependency in normalized:
                engine._dependents.setdefault(dependency, set()).add(identity)
        return engine
