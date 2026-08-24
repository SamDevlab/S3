"""Container backend boundaries and OCI artifact contracts.

The Docker CLI provider remains the compatible M1.38 implementation.  The
OCI backend in this module is deliberately experimental: it defines stable,
deterministic data contracts but does not claim image-build or runtime
qualification yet.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Mapping, Protocol

from .s3_docker import DockerProvider, DockerResult, DockerSpec

if TYPE_CHECKING:
    from .project_container import ProjectTooling


class ContainerBackendError(ValueError):
    """Raised when a container backend cannot satisfy an operation."""


class ContainerBackend(Protocol):
    """Minimal provider identity contract shared by container backends."""

    name: str
    qualified: bool


def _canonical_json_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _sha256_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_RELATIVE_PATH = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.?/)[^\\]+$")


@dataclass(frozen=True, slots=True)
class OciDescriptor:
    """A validated OCI descriptor whose digest and size are self-consistent."""

    media_type: str
    digest: str
    size: int
    annotations: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.media_type:
            raise ContainerBackendError("OCI descriptor media type must not be empty")
        if not _DIGEST.fullmatch(self.digest):
            raise ContainerBackendError("OCI descriptor digest must be sha256")
        if not isinstance(self.size, int) or self.size < 0:
            raise ContainerBackendError("OCI descriptor size must be non-negative")
        names = tuple(name for name, _ in self.annotations)
        if any(not name for name in names):
            raise ContainerBackendError("OCI descriptor annotation names must not be empty")
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise ContainerBackendError("OCI descriptor annotations must be sorted and unique")

    @classmethod
    def from_bytes(
        cls,
        media_type: str,
        payload: bytes,
        annotations: Mapping[str, str] | None = None,
    ) -> "OciDescriptor":
        ordered = tuple(sorted((str(name), str(value)) for name, value in (annotations or {}).items()))
        return cls(media_type, _sha256_digest(payload), len(payload), ordered)

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "digest": self.digest,
            "mediaType": self.media_type,
            "size": self.size,
        }
        if self.annotations:
            result["annotations"] = dict(self.annotations)
        return result


@dataclass(frozen=True, slots=True)
class OciFilesystemEntry:
    """A deterministic source entry in a future OCI filesystem layer."""

    path: str
    digest: OciDescriptor

    def __post_init__(self) -> None:
        if not _RELATIVE_PATH.fullmatch(self.path) or self.path.endswith("/"):
            raise ContainerBackendError("OCI filesystem paths must be relative POSIX paths")

    def to_dict(self) -> dict[str, object]:
        return {"path": self.path, "descriptor": self.digest.to_dict()}


@dataclass(frozen=True, slots=True)
class OciFilesystemLayerPlan:
    """Canonical layer plan; it is not yet a generated OCI tar layer."""

    entries: tuple[OciFilesystemEntry, ...]

    def __post_init__(self) -> None:
        paths = tuple(entry.path for entry in self.entries)
        if paths != tuple(sorted(paths)) or len(set(paths)) != len(paths):
            raise ContainerBackendError("OCI filesystem entries must be sorted and unique")

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes({"entries": [entry.to_dict() for entry in self.entries]})

    def descriptor(self) -> OciDescriptor:
        return OciDescriptor.from_bytes(
            "application/vnd.s3.oci.layer-plan.v1+json",
            self.canonical_bytes(),
        )


@dataclass(frozen=True, slots=True)
class OciImageConfig:
    """Timestamp-free canonical OCI image configuration."""

    architecture: str = "amd64"
    operating_system: str = "linux"
    entrypoint: tuple[str, ...] = ()
    environment: tuple[tuple[str, str], ...] = ()
    rootfs_diff_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.architecture or not self.operating_system:
            raise ContainerBackendError("OCI image config platform must be explicit")
        if any(not item for item in self.entrypoint):
            raise ContainerBackendError("OCI image config entrypoint must not contain empty values")
        names = tuple(name for name, _ in self.environment)
        if names != tuple(sorted(names)) or len(set(names)) != len(names):
            raise ContainerBackendError("OCI image config environment must be sorted and unique")
        if any(not _DIGEST.fullmatch(digest) for digest in self.rootfs_diff_ids):
            raise ContainerBackendError("OCI image config rootfs diff IDs must be sha256")

    def to_dict(self) -> dict[str, object]:
        return {
            "architecture": self.architecture,
            "config": {
                "Env": [f"{name}={value}" for name, value in self.environment],
                "Entrypoint": list(self.entrypoint) or None,
            },
            "os": self.operating_system,
            "rootfs": {"diff_ids": list(self.rootfs_diff_ids), "type": "layers"},
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.to_dict())

    def descriptor(self) -> OciDescriptor:
        return OciDescriptor.from_bytes(
            "application/vnd.oci.image.config.v1+json",
            self.canonical_bytes(),
        )


@dataclass(frozen=True, slots=True)
class OciImageManifest:
    """Canonical OCI image manifest contract."""

    config: OciDescriptor
    layers: tuple[OciDescriptor, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "config": self.config.to_dict(),
            "layers": [layer.to_dict() for layer in self.layers],
            "schemaVersion": 2,
        }

    def canonical_bytes(self) -> bytes:
        return _canonical_json_bytes(self.to_dict())

    def descriptor(self) -> OciDescriptor:
        return OciDescriptor.from_bytes(
            "application/vnd.oci.image.manifest.v1+json",
            self.canonical_bytes(),
        )


@dataclass(frozen=True, slots=True)
class OciImageLayout:
    """OCI layout metadata and deterministic archive member plan."""

    manifest: OciDescriptor

    def layout_bytes(self) -> bytes:
        return _canonical_json_bytes({"imageLayoutVersion": "1.0.0"})

    def index_bytes(self) -> bytes:
        return _canonical_json_bytes(
            {"manifests": [self.manifest.to_dict()], "schemaVersion": 2}
        )

    def archive_members(self) -> tuple[str, ...]:
        digest = self.manifest.digest.partition(":")[2]
        return (
            "oci-layout",
            "index.json",
            f"blobs/sha256/{digest}",
        )


@dataclass(frozen=True, slots=True)
class BackendSelection:
    """Explicit backend selection evidence for CLI and higher-level callers."""

    backend: str
    fallback_reason: str | None = None

    def evidence(self) -> dict[str, str]:
        return {
            "CONTAINER_BACKEND": self.backend,
            "FALLBACK_REASON": self.fallback_reason or "none",
        }


class DockerCliBackend(DockerProvider):
    """Named adapter for the existing M1.38 Docker CLI provider."""

    name = "docker"
    qualified = True


class S3OciBackend:
    """Experimental OCI backend: contracts are available, execution is not."""

    name = "s3"
    qualified = False
    status = "experimental-partial"

    def plan(self, project: "ProjectTooling", image: str) -> dict[str, object]:
        project.check()
        source_files = project.source_files()
        entries = tuple(
            OciFilesystemEntry(
                path=name,
                digest=OciDescriptor.from_bytes(
                    "application/vnd.s3.source.v1+text",
                    content.encode("utf-8"),
                ),
            )
            for name, content in sorted(source_files.items())
        )
        layer = OciFilesystemLayerPlan(entries)
        config = OciImageConfig(entrypoint=("s3", "run", f"/app/{project.manifest.entrypoint}.s3"))
        return {
            "kind": "s3.oci.plan.v1",
            "provider": "s3-oci",
            "status": self.status,
            "qualified": self.qualified,
            "image": image,
            "entrypoint": config.entrypoint,
            "filesystem_layer": layer.descriptor().to_dict(),
            "canonical_config": config.descriptor().to_dict(),
            "export": "oci-layout-and-tar-contract-only",
        }

    def _unsupported(self, operation: str) -> None:
        raise ContainerBackendError(
            "CONTAINER_BACKEND=s3; FALLBACK_REASON=none; "
            f"S3 OCI backend is experimental and cannot {operation} before qualification"
        )

    def build(self, *args: object, **kwargs: object) -> DockerResult:
        self._unsupported("build images")
        raise AssertionError("unreachable")

    def run(self, *args: object, **kwargs: object) -> DockerResult:
        self._unsupported("run containers")
        raise AssertionError("unreachable")


def select_container_backend(requested: str) -> tuple[ContainerBackend, BackendSelection]:
    """Select a backend without silently changing the requested mode."""

    if requested == "docker":
        return DockerCliBackend(), BackendSelection("docker")
    if requested == "s3":
        return S3OciBackend(), BackendSelection("s3")
    if requested == "auto":
        return DockerCliBackend(), BackendSelection("docker", "S3_OCI_BACKEND_NOT_QUALIFIED")
    raise ContainerBackendError(f"unsupported container backend {requested!r}")
