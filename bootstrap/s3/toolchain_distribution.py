"""Deterministic local toolchain bundles for S3 M1.80."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import PurePosixPath
import zipfile


class DistributionError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ToolchainBundle:
    data: bytes
    manifest: dict[str, object]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


class ToolchainBundler:
    """Build local reproducible bundles and never publish them remotely."""

    def __init__(self, *, max_files: int = 4096, max_path_length: int = 240, max_bundle_bytes: int = 64 * 1024 * 1024) -> None:
        values = (max_files, max_path_length, max_bundle_bytes)
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in values):
            raise ValueError("distribution limits must be positive integers")
        self.max_files = max_files
        self.max_path_length = max_path_length
        self.max_bundle_bytes = max_bundle_bytes

    def build(self, source_files: dict[str, bytes], *, license_text: str, metadata: dict[str, str]) -> ToolchainBundle:
        if not isinstance(license_text, str) or not license_text.strip():
            raise DistributionError("license text is required")
        if not isinstance(metadata, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in metadata.items()):
            raise DistributionError("metadata must be a string-to-string mapping")
        if len(source_files) > self.max_files:
            raise DistributionError("toolchain file limit exceeded")
        normalized: dict[str, bytes] = {}
        for name, data in source_files.items():
            safe = _safe_name(name, self.max_path_length)
            if safe in {"MANIFEST.json", "LICENSE"} or safe in normalized:
                raise DistributionError(f"duplicate or reserved bundle path: {name!r}")
            if not isinstance(data, bytes):
                raise DistributionError(f"bundle file must be bytes: {name!r}")
            normalized[safe] = data
        files = [{"path": name, "sha256": hashlib.sha256(normalized[name]).hexdigest(), "size": len(normalized[name])} for name in sorted(normalized)]
        manifest: dict[str, object] = {
            "format": "s3.toolchain.bundle.v1",
            "license": "LICENSE",
            "metadata": {key: metadata[key] for key in sorted(metadata)},
            "files": files,
        }
        manifest_bytes = (json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        entries: dict[str, bytes] = {**normalized, "LICENSE": license_text.encode("utf-8"), "MANIFEST.json": manifest_bytes}
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
            for name in sorted(entries):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, entries[name])
        data = output.getvalue()
        if len(data) > self.max_bundle_bytes:
            raise DistributionError("toolchain bundle exceeds configured size")
        return ToolchainBundle(data, manifest)

    def verify(self, bundle: ToolchainBundle) -> None:
        try:
            with zipfile.ZipFile(io.BytesIO(bundle.data), "r") as archive:
                names = tuple(sorted(archive.namelist()))
                if "LICENSE" not in names or "MANIFEST.json" not in names:
                    raise DistributionError("bundle must contain LICENSE and MANIFEST.json")
                manifest = json.loads(archive.read("MANIFEST.json"))
                if manifest.get("format") != "s3.toolchain.bundle.v1":
                    raise DistributionError("unsupported toolchain bundle format")
                for item in manifest.get("files", []):
                    name = item["path"]
                    _safe_name(name, self.max_path_length)
                    data = archive.read(name)
                    if hashlib.sha256(data).hexdigest() != item["sha256"] or len(data) != item["size"]:
                        raise DistributionError(f"bundle checksum mismatch: {name}")
        except (OSError, KeyError, TypeError, ValueError, zipfile.BadZipFile) as error:
            if isinstance(error, DistributionError):
                raise
            raise DistributionError("toolchain bundle is malformed") from error

    def publish(self, _bundle: ToolchainBundle) -> None:
        raise DistributionError("toolchain distribution is local-only; remote release is not implemented")


def _safe_name(name: str, max_length: int) -> str:
    if not isinstance(name, str) or not name or len(name) > max_length:
        raise DistributionError("bundle path is empty or too long")
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or ":" in path.parts[0] or any(not part for part in path.parts):
        raise DistributionError(f"machine or traversal path is rejected: {name!r}")
    return "/".join(path.parts)
