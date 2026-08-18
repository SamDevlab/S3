from __future__ import annotations

import hashlib
import io
import json
import tarfile

import pytest

from bootstrap.s3.registry_client import RegistryClient, RegistryError, RegistryLock


pytestmark = pytest.mark.s3_contract


def _archive(name: str = "src/main.s3", content: bytes = b"fn main() -> tryte:\n    return 1\n") -> bytes:
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w") as archive:
        info = tarfile.TarInfo(name)
        info.size = len(content)
        archive.addfile(info, io.BytesIO(content))
    return output.getvalue()


def _registry(tmp_path, archive: bytes | None = None) -> tuple[RegistryClient, RegistryLock, bytes]:
    payload = archive or _archive()
    sha256 = hashlib.sha256(payload).hexdigest()
    root = tmp_path / "registry"
    (root / "objects").mkdir(parents=True)
    (root / "objects" / "package.tar").write_bytes(payload)
    (root / "index.json").write_text(json.dumps({
        "format": "s3.registry.index.v1",
        "packages": [{"name": "demo", "object": "objects/package.tar", "sha256": sha256, "version": "1.0.0"}],
    }), encoding="utf-8")
    return RegistryClient(root), RegistryLock("demo", "1.0.0", sha256), payload


def test_resolution_is_exact_content_addressed_and_cacheable(tmp_path) -> None:
    client, lock, _payload = _registry(tmp_path)
    assert client.read_only
    assert client.resolve("demo", "1.0.0") == lock
    artifact = client.fetch(lock)
    assert artifact.archive
    (client.root / "objects" / "package.tar").unlink()
    assert client.fetch(lock).archive == artifact.archive


def test_install_is_deterministic_and_rejects_hash_mismatch(tmp_path) -> None:
    client, lock, payload = _registry(tmp_path)
    destination = tmp_path / "install"
    assert client.install(client.fetch(lock), destination) == ("src/main.s3",)
    bad = RegistryLock(lock.name, lock.version, "0" * 64)
    with pytest.raises(RegistryError, match="SHA-256"):
        client._verify(bad, payload)


def test_archive_traversal_and_symlink_members_are_rejected(tmp_path) -> None:
    traversal = _archive("../escape.s3")
    client, lock, _ = _registry(tmp_path, traversal)
    with pytest.raises(RegistryError, match="traversal"):
        client.install(client.fetch(lock), tmp_path / "install")

    link_output = io.BytesIO()
    with tarfile.open(fileobj=link_output, mode="w") as archive:
        info = tarfile.TarInfo("link")
        info.type = tarfile.SYMTYPE
        info.linkname = "outside"
        archive.addfile(info)
    link_client, link_lock, _ = _registry(tmp_path / "links", link_output.getvalue())
    with pytest.raises(RegistryError, match="regular file"):
        link_client.install(link_client.fetch(link_lock), tmp_path / "links-install")


def test_duplicate_identity_and_publish_are_rejected(tmp_path) -> None:
    root = tmp_path / "duplicate"
    root.mkdir()
    entry = {"name": "demo", "version": "1", "sha256": "0" * 64, "object": "object"}
    (root / "index.json").write_text(json.dumps({"format": "s3.registry.index.v1", "packages": [entry, entry]}), encoding="utf-8")
    with pytest.raises(RegistryError, match="duplicate"):
        RegistryClient(root)

    client, lock, _ = _registry(tmp_path / "publish")
    with pytest.raises(RegistryError, match="read-only"):
        client.publish(client.fetch(lock))
