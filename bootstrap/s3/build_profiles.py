"""Deterministic development/release profiles and a PGO provenance boundary."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


class BuildProfileError(ValueError):
    """Raised for unknown profiles or stale optimization evidence."""


@dataclass(frozen=True, slots=True)
class BuildProfile:
    name: str
    target: str
    optimization: str
    debug_info: bool
    flags: tuple[str, ...]

    @classmethod
    def resolve(cls, name: str, target: str) -> "BuildProfile":
        if name == "development":
            return cls(name, target, "O0", True, ("debug-info", "deterministic"))
        if name == "release":
            return cls(name, target, "O1", False, ("deterministic", "strip-host-paths"))
        raise BuildProfileError(f"unknown build profile {name!r}")

    def __post_init__(self) -> None:
        if self.name not in {"development", "release"} or not self.target:
            raise BuildProfileError("build profile identity is invalid")
        if self.optimization not in {"O0", "O1"}:
            raise BuildProfileError("build profile optimization is unsupported")
        if tuple(sorted(set(self.flags))) != self.flags:
            raise BuildProfileError("build profile flags must be sorted and unique")

    @property
    def payload(self) -> dict[str, object]:
        return {"name": self.name, "target": self.target, "optimization": self.optimization, "debug_info": self.debug_info, "flags": list(self.flags)}


@dataclass(frozen=True, slots=True)
class ProfileProvenance:
    profile: BuildProfile
    compiler_sha: str
    source_identity: str
    target: str

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value for value in (self.compiler_sha, self.source_identity, self.target)):
            raise BuildProfileError("profile provenance fields must be non-empty")
        if self.target != self.profile.target:
            raise BuildProfileError("profile provenance target mismatch")

    @property
    def payload(self) -> dict[str, object]:
        return {"profile": self.profile.payload, "compiler_sha": self.compiler_sha, "source_identity": self.source_identity, "target": self.target}


@dataclass(frozen=True, slots=True)
class PGOProfileIdentity:
    source_identity: str
    compiler_sha: str
    target: str
    workload_identity: str
    profile_digest: str

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value for value in (self.source_identity, self.compiler_sha, self.target, self.workload_identity, self.profile_digest)):
            raise BuildProfileError("PGO profile identity fields must be non-empty")

    @classmethod
    def create(cls, *, source_identity: str, compiler_sha: str, target: str, workload_identity: str, profile_data: bytes) -> "PGOProfileIdentity":
        if not isinstance(profile_data, bytes) or not profile_data:
            raise BuildProfileError("PGO profile data must be non-empty bytes")
        digest = hashlib.sha256(profile_data).hexdigest()
        return cls(source_identity, compiler_sha, target, workload_identity, digest)

    def matches(self, provenance: ProfileProvenance, workload_identity: str) -> bool:
        return self.source_identity == provenance.source_identity and self.compiler_sha == provenance.compiler_sha and self.target == provenance.target and self.target == provenance.profile.target and self.workload_identity == workload_identity

    @property
    def text(self) -> str:
        return json.dumps(
            {
                "source_identity": self.source_identity,
                "compiler_sha": self.compiler_sha,
                "target": self.target,
                "workload_identity": self.workload_identity,
                "profile_digest": self.profile_digest,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
