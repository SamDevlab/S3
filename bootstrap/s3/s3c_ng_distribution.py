"""Explicit, hash-pinned installation of the Linux S3C-NG bootstrap artifact."""

from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import re
import shutil
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from .diagnostics import S3Error

_LOCK_PATH = Path(__file__).with_name("s3c_ng_bootstrap_lock.json")
_MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
_MAX_EXECUTABLE_BYTES = 64 * 1024 * 1024
_MAX_MANIFEST_BYTES = 1024 * 1024
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_TAG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_ASSET_NAME = "s3c-ng-bootstrap-linux-x86_64.tar.gz"


class BootstrapDistributionError(S3Error):
    """A pinned bootstrap artifact is absent, incompatible, or untrusted."""


@dataclass(frozen=True, slots=True)
class BootstrapPin:
    release_tag: str
    asset_sha256: str
    artifact_sha256: str
    artifact_bytes: int
    source_commit: str
    source_graph_sha256: str
    compiler: str
    toolchain_version: str
    assembler: str
    linker: str


def _load_pin(path: Path | None = None) -> BootstrapPin:
    path = _LOCK_PATH if path is None else path
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BootstrapDistributionError(f"S3C-NG bootstrap lock is unavailable or invalid: {error}") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise BootstrapDistributionError("S3C-NG bootstrap lock has an unsupported schema")
    if payload.get("status") != "PINNED":
        raise BootstrapDistributionError("no published S3C-NG bootstrap artifact is pinned in this checkout")
    release_tag = payload.get("release_tag")
    asset_name = payload.get("asset_name")
    asset_sha256 = payload.get("asset_sha256")
    artifact_sha256 = payload.get("artifact_sha256")
    artifact_bytes = payload.get("artifact_bytes")
    source_commit = payload.get("source_commit")
    source_graph_sha256 = payload.get("source_graph_sha256")
    toolchain = payload.get("toolchain")
    if (
        not isinstance(release_tag, str)
        or _TAG.fullmatch(release_tag) is None
        or asset_name != _ASSET_NAME
        or not isinstance(asset_sha256, str)
        or _SHA256.fullmatch(asset_sha256) is None
        or not isinstance(artifact_sha256, str)
        or _SHA256.fullmatch(artifact_sha256) is None
        or not isinstance(artifact_bytes, int)
        or isinstance(artifact_bytes, bool)
        or not 20 <= artifact_bytes <= _MAX_EXECUTABLE_BYTES
        or not isinstance(source_commit, str)
        or _COMMIT.fullmatch(source_commit) is None
        or not isinstance(source_graph_sha256, str)
        or _SHA256.fullmatch(source_graph_sha256) is None
        or not isinstance(toolchain, dict)
        or not isinstance(toolchain.get("compiler"), str)
        or not toolchain["compiler"].strip()
        or not isinstance(toolchain.get("version"), str)
        or not toolchain["version"].strip()
        or not isinstance(toolchain.get("assembler"), str)
        or not toolchain["assembler"].strip()
        or not isinstance(toolchain.get("linker"), str)
        or not toolchain["linker"].strip()
        or payload.get("target") != "linux-x86_64"
    ):
        raise BootstrapDistributionError("S3C-NG bootstrap lock does not satisfy the pinned artifact contract")
    return BootstrapPin(
        release_tag,
        asset_sha256,
        artifact_sha256,
        artifact_bytes,
        source_commit,
        source_graph_sha256,
        toolchain["compiler"],
        toolchain["version"],
        toolchain["assembler"],
        toolchain["linker"],
    )


def pinned_install_path(*, lock_path: Path | None = None) -> Path | None:
    """Return the stable cache executable path, or None before a release is pinned."""

    lock_path = _LOCK_PATH if lock_path is None else lock_path
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise BootstrapDistributionError(f"S3C-NG bootstrap lock is unavailable or invalid: {error}") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise BootstrapDistributionError("S3C-NG bootstrap lock has an unsupported schema")
    if payload.get("status") == "UNPUBLISHED":
        return None
    pin = _load_pin(lock_path)
    return _cache_root() / pin.release_tag / "s3c-ng"


def _cache_root() -> Path:
    override = os.environ.get("S3_BOOTSTRAP_CACHE")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".cache" / "s3" / "bootstrap"


def _release_asset_url(pin: BootstrapPin) -> str:
    from urllib.parse import quote

    tag = quote(pin.release_tag, safe=".-_")
    return (
        "https://github.com/SamDevlab/S3/releases/download/"
        f"{tag}/{_ASSET_NAME}"
    )


def _download(url: str) -> bytes:
    try:
        with urlopen(url, timeout=60) as response:
            data = response.read(_MAX_ARCHIVE_BYTES + 1)
    except (OSError, URLError, TimeoutError) as error:
        raise BootstrapDistributionError(f"could not download the pinned S3C-NG bootstrap asset: {error}") from error
    if len(data) > _MAX_ARCHIVE_BYTES:
        raise BootstrapDistributionError("S3C-NG bootstrap archive exceeds the configured size limit")
    return data


def _archive_members(archive_bytes: bytes) -> tuple[bytes, bytes]:
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            members = archive.getmembers()
            if len(members) != 2 or {member.name for member in members} != {
                "s3c-ng",
                "s3c-ng.manifest.json",
            }:
                raise BootstrapDistributionError("bootstrap archive must contain exactly the executable and its manifest")
            by_name = {member.name: member for member in members}
            executable_member = by_name["s3c-ng"]
            manifest_member = by_name["s3c-ng.manifest.json"]
            if (
                not executable_member.isfile()
                or not manifest_member.isfile()
                or not 20 <= executable_member.size <= _MAX_EXECUTABLE_BYTES
                or not 1 <= manifest_member.size <= _MAX_MANIFEST_BYTES
            ):
                raise BootstrapDistributionError("bootstrap archive contains unsupported member types or sizes")
            executable_stream = archive.extractfile(executable_member)
            manifest_stream = archive.extractfile(manifest_member)
            if executable_stream is None or manifest_stream is None:
                raise BootstrapDistributionError("bootstrap archive is missing a required file body")
            executable = executable_stream.read(_MAX_EXECUTABLE_BYTES + 1)
            manifest = manifest_stream.read(_MAX_MANIFEST_BYTES + 1)
    except (tarfile.TarError, OSError) as error:
        raise BootstrapDistributionError(f"S3C-NG bootstrap archive is invalid: {error}") from error
    if len(executable) > _MAX_EXECUTABLE_BYTES or len(manifest) > _MAX_MANIFEST_BYTES:
        raise BootstrapDistributionError("bootstrap archive member exceeds the configured size limit")
    return executable, manifest


def _verify_manifest(executable: bytes, manifest_bytes: bytes, pin: BootstrapPin) -> dict[str, object]:
    from .native_compiler import NG_IR_FORMAT_VERSION

    try:
        manifest = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise BootstrapDistributionError("S3C-NG bootstrap manifest is invalid JSON") from error
    actual_sha256 = hashlib.sha256(executable).hexdigest()
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 2
        or manifest.get("target") != "linux-x86_64"
        or manifest.get("ng_ir_format_version") != NG_IR_FORMAT_VERSION
        or manifest.get("artifact_sha256") != pin.artifact_sha256
        or manifest.get("artifact_sha256") != actual_sha256
        or manifest.get("artifact_bytes") != pin.artifact_bytes
        or manifest.get("artifact_bytes") != len(executable)
        or manifest.get("source_commit") != pin.source_commit
        or manifest.get("source_graph_sha256") != pin.source_graph_sha256
        or not isinstance(manifest.get("toolchain"), dict)
        or manifest["toolchain"].get("compiler") != pin.compiler
        or manifest["toolchain"].get("version") != pin.toolchain_version
        or manifest["toolchain"].get("assembler") != pin.assembler
        or manifest["toolchain"].get("linker") != pin.linker
        or manifest.get("entry_module") != "app"
        or manifest.get("optimization_mode") != "O0"
        or not isinstance(manifest.get("entry_symbol"), str)
    ):
        raise BootstrapDistributionError("S3C-NG bootstrap manifest does not match the pinned provenance")
    return manifest


def _validate_installed(directory: Path, pin: BootstrapPin) -> Path:
    executable = directory / "s3c-ng"
    manifest_path = executable.with_suffix(".manifest.json")
    try:
        executable_bytes = executable.read_bytes()
        manifest_bytes = manifest_path.read_bytes()
    except OSError as error:
        raise BootstrapDistributionError(f"installed S3C-NG bootstrap is incomplete: {error}") from error
    _verify_manifest(executable_bytes, manifest_bytes, pin)
    from .native_compiler import inspect_s3c_ng_executable

    availability = inspect_s3c_ng_executable(executable)
    if not availability.available:
        raise BootstrapDistributionError(availability.reason or "installed S3C-NG bootstrap is invalid")
    return executable


def verify_default_artifact(executable: Path) -> str | None:
    """Check pinned provenance when the selected executable is the managed cache copy."""

    try:
        expected_path = pinned_install_path()
    except BootstrapDistributionError as error:
        return str(error)
    if expected_path is None:
        return None
    try:
        is_managed = executable.resolve() == expected_path.resolve()
    except OSError:
        is_managed = False
    if not is_managed:
        return None
    try:
        pin = _load_pin()
        _verify_manifest(executable.read_bytes(), executable.with_suffix(".manifest.json").read_bytes(), pin)
    except (OSError, BootstrapDistributionError) as error:
        return str(error)
    return None


def install_s3c_ng_bootstrap(
    *,
    lock_path: Path = _LOCK_PATH,
    cache_root: Path | None = None,
) -> Path:
    """Download and install the pinned release only when explicitly requested."""

    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise BootstrapDistributionError("the S3C-NG bootstrap release currently supports Linux x86-64 only")
    pin = _load_pin(lock_path)
    root = _cache_root() if cache_root is None else Path(cache_root).expanduser().resolve()
    destination = root / pin.release_tag
    if destination.exists():
        return _validate_installed(destination, pin)

    archive_bytes = _download(_release_asset_url(pin))
    if hashlib.sha256(archive_bytes).hexdigest() != pin.asset_sha256:
        raise BootstrapDistributionError("downloaded S3C-NG bootstrap archive SHA-256 does not match the lock")
    executable_bytes, manifest_bytes = _archive_members(archive_bytes)
    _verify_manifest(executable_bytes, manifest_bytes, pin)
    root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{pin.release_tag}-", dir=root))
    try:
        executable = staging / "s3c-ng"
        executable.write_bytes(executable_bytes)
        executable.chmod(0o755)
        executable.with_suffix(".manifest.json").write_bytes(manifest_bytes)
        _validate_installed(staging, pin)
        try:
            staging.rename(destination)
        except FileExistsError:
            return _validate_installed(destination, pin)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return destination / "s3c-ng"
