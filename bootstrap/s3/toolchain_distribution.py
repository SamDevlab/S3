"""Deterministic local toolchain bundles for S3 M1.80/M1.90."""

from __future__ import annotations

import hashlib
import io
import json
from dataclasses import dataclass
from pathlib import PurePosixPath
import re
import zipfile


class DistributionError(ValueError):
    pass


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RESERVED = frozenset({"LICENSE", "MANIFEST.json"})
_MANIFEST_KEYS = frozenset({"format", "license", "license_sha256", "license_size", "metadata", "files"})
_FILE_KEYS = frozenset({"path", "sha256", "size"})


@dataclass(frozen=True, slots=True)
class ToolchainBundle:
    data: bytes
    manifest: dict[str, object]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


class ToolchainBundler:
    """Build and fail-closed verify local reproducible bundles; never publish."""

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
            if safe in _RESERVED or safe in normalized:
                raise DistributionError(f"duplicate or reserved bundle path: {name!r}")
            if not isinstance(data, bytes):
                raise DistributionError(f"bundle file must be bytes: {name!r}")
            normalized[safe] = data

        license_bytes = license_text.encode("utf-8")
        files = [
            {"path": name, "sha256": hashlib.sha256(normalized[name]).hexdigest(), "size": len(normalized[name])}
            for name in sorted(normalized)
        ]
        manifest: dict[str, object] = {
            "format": "s3.toolchain.bundle.v1",
            "license": "LICENSE",
            "license_sha256": hashlib.sha256(license_bytes).hexdigest(),
            "license_size": len(license_bytes),
            "metadata": {key: metadata[key] for key in sorted(metadata)},
            "files": files,
        }
        manifest_bytes = _canonical_manifest_bytes(manifest)
        entries: dict[str, bytes] = {**normalized, "LICENSE": license_bytes, "MANIFEST.json": manifest_bytes}
        if sum(len(data) for data in entries.values()) > self.max_bundle_bytes:
            raise DistributionError("toolchain uncompressed content exceeds configured size")

        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
            for name in sorted(entries):
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, entries[name])
        data = output.getvalue()
        if len(data) > self.max_bundle_bytes:
            raise DistributionError("toolchain bundle exceeds configured size")
        bundle = ToolchainBundle(data, manifest)
        self.verify(bundle)
        return bundle

    def verify(self, bundle: ToolchainBundle) -> None:
        if not isinstance(bundle, ToolchainBundle) or not isinstance(bundle.data, bytes) or not isinstance(bundle.manifest, dict):
            raise DistributionError("toolchain bundle object is invalid")
        if not bundle.data or len(bundle.data) > self.max_bundle_bytes:
            raise DistributionError("toolchain bundle exceeds configured size")
        try:
            with zipfile.ZipFile(io.BytesIO(bundle.data), "r", allowZip64=False) as archive:
                infos = tuple(archive.infolist())
                if len(infos) > self.max_files + len(_RESERVED):
                    raise DistributionError("toolchain archive file limit exceeded")

                raw_names = tuple(info.filename for info in infos)
                if len(set(raw_names)) != len(raw_names):
                    raise DistributionError("toolchain archive contains duplicate member names")

                canonical_names: set[str] = set()
                total_uncompressed = 0
                for info in infos:
                    safe = _safe_name(info.filename, self.max_path_length)
                    if safe != info.filename:
                        raise DistributionError(f"archive member path is not canonical: {info.filename!r}")
                    if safe in canonical_names:
                        raise DistributionError(f"archive member canonical path is duplicated: {safe!r}")
                    canonical_names.add(safe)
                    if info.is_dir():
                        raise DistributionError("directory entries are not valid toolchain files")
                    file_kind = (info.external_attr >> 16) & 0o170000
                    if file_kind not in {0, 0o100000}:
                        raise DistributionError("non-regular archive entries are rejected")
                    if info.compress_type != zipfile.ZIP_STORED:
                        raise DistributionError("toolchain bundle requires stored deterministic entries")
                    if info.file_size < 0 or info.file_size > self.max_bundle_bytes:
                        raise DistributionError("archive member exceeds configured size")
                    total_uncompressed += info.file_size
                    if total_uncompressed > self.max_bundle_bytes:
                        raise DistributionError("toolchain uncompressed content exceeds configured size")

                names = set(raw_names)
                if not _RESERVED <= names:
                    raise DistributionError("bundle must contain LICENSE and MANIFEST.json")

                embedded_manifest_bytes = archive.read("MANIFEST.json")
                manifest = json.loads(embedded_manifest_bytes.decode("utf-8"))
                _validate_manifest(manifest, self.max_files, self.max_path_length, self.max_bundle_bytes)
                if manifest != bundle.manifest:
                    raise DistributionError("embedded manifest differs from bundle manifest")
                if embedded_manifest_bytes != _canonical_manifest_bytes(manifest):
                    raise DistributionError("embedded manifest is not canonical")

                manifest_files = manifest["files"]
                expected_names = {"LICENSE", "MANIFEST.json"}
                expected_names.update(item["path"] for item in manifest_files)
                if names != expected_names:
                    missing = sorted(expected_names - names)
                    extras = sorted(names - expected_names)
                    raise DistributionError(f"archive membership differs from manifest: missing={missing}, extra={extras}")

                license_bytes = archive.read("LICENSE")
                if not license_bytes:
                    raise DistributionError("LICENSE must not be empty")
                try:
                    license_bytes.decode("utf-8")
                except UnicodeDecodeError as error:
                    raise DistributionError("LICENSE must be UTF-8 text") from error
                if len(license_bytes) != manifest["license_size"] or hashlib.sha256(license_bytes).hexdigest() != manifest["license_sha256"]:
                    raise DistributionError("LICENSE does not match manifest binding")

                for item in manifest_files:
                    name = item["path"]
                    data = archive.read(name)
                    if hashlib.sha256(data).hexdigest() != item["sha256"] or len(data) != item["size"]:
                        raise DistributionError(f"bundle checksum mismatch: {name}")
        except (OSError, KeyError, TypeError, ValueError, UnicodeError, zipfile.BadZipFile, zipfile.LargeZipFile) as error:
            if isinstance(error, DistributionError):
                raise
            raise DistributionError("toolchain bundle is malformed") from error

    def publish(self, _bundle: ToolchainBundle) -> None:
        raise DistributionError("toolchain distribution is local-only; remote release is not implemented")


def _validate_manifest(manifest: object, max_files: int, max_path_length: int, max_bundle_bytes: int) -> None:
    if not isinstance(manifest, dict) or set(manifest) != _MANIFEST_KEYS:
        raise DistributionError("toolchain manifest schema is invalid")
    if manifest.get("format") != "s3.toolchain.bundle.v1" or manifest.get("license") != "LICENSE":
        raise DistributionError("unsupported toolchain bundle format")
    license_sha = manifest.get("license_sha256")
    license_size = manifest.get("license_size")
    if not isinstance(license_sha, str) or _SHA256.fullmatch(license_sha) is None:
        raise DistributionError("manifest LICENSE digest is invalid")
    if isinstance(license_size, bool) or not isinstance(license_size, int) or not 0 < license_size <= max_bundle_bytes:
        raise DistributionError("manifest LICENSE size is invalid")
    metadata = manifest.get("metadata")
    if not isinstance(metadata, dict) or any(not isinstance(key, str) or not isinstance(value, str) for key, value in metadata.items()):
        raise DistributionError("manifest metadata is invalid")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) > max_files:
        raise DistributionError("manifest file list is invalid")
    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != _FILE_KEYS:
            raise DistributionError("manifest file record schema is invalid")
        name = item.get("path")
        digest = item.get("sha256")
        size = item.get("size")
        safe = _safe_name(name, max_path_length)
        if safe != name or safe in _RESERVED or safe in seen:
            raise DistributionError(f"manifest path is duplicate, reserved, or non-canonical: {name!r}")
        seen.add(safe)
        if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
            raise DistributionError(f"manifest checksum is invalid: {safe}")
        if isinstance(size, bool) or not isinstance(size, int) or size < 0 or size > max_bundle_bytes:
            raise DistributionError(f"manifest size is invalid: {safe}")


def _canonical_manifest_bytes(manifest: dict[str, object]) -> bytes:
    return (json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _safe_name(name: str, max_length: int) -> str:
    if not isinstance(name, str) or not name or len(name) > max_length:
        raise DistributionError("bundle path is empty or too long")
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or ".." in path.parts or ":" in path.parts[0] or any(not part for part in path.parts):
        raise DistributionError(f"machine or traversal path is rejected: {name!r}")
    return "/".join(path.parts)
