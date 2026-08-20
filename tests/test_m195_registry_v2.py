from __future__ import annotations

import hashlib
import json

import pytest

from bootstrap.s3.registry_v2 import RegistryV2Client, RegistryV2Error, RegistryV2Limits


def _registry(tmp_path):
    root = tmp_path / "registry"
    (root / "objects").mkdir(parents=True)
    leaf = b"leaf"
    root_body = b"root"
    leaf_digest = hashlib.sha256(leaf).hexdigest()
    root_digest = hashlib.sha256(root_body).hexdigest()
    (root / "objects" / "leaf.tar").write_bytes(leaf)
    (root / "objects" / "root.tar").write_bytes(root_body)
    (root / "index.json").write_text(json.dumps({
        "format": "s3.registry.index.v2",
        "origin": "https://registry.fixture",
        "packages": [
            {"name": "root", "version": "1.0", "sha256": root_digest, "object": "objects/root.tar", "dependencies": [{"name": "leaf", "version": "1.0", "sha256": leaf_digest}]},
            {"name": "leaf", "version": "1.0", "sha256": leaf_digest, "object": "objects/leaf.tar", "dependencies": []},
        ],
    }), encoding="utf-8")
    return root, root_digest, leaf_digest


def test_registry_v2_resolves_exact_dependency_identity_and_verified_cache(tmp_path) -> None:
    root, root_digest, leaf_digest = _registry(tmp_path)
    client = RegistryV2Client(root, expected_origin="https://registry.fixture")
    resolution = client.resolve("root", "1.0")
    assert [item.sha256 for item in resolution.packages] == [root_digest, leaf_digest]
    assert client.fetch(resolution.packages[1]) == b"leaf"
    (root / "objects" / "leaf.tar").unlink()
    assert client.fetch(resolution.packages[1]) == b"leaf"


def test_registry_v2_rejects_cycles_bad_digest_and_origin(tmp_path) -> None:
    root, root_digest, _ = _registry(tmp_path)
    data = json.loads((root / "index.json").read_text(encoding="utf-8"))
    data["packages"][1]["dependencies"] = [{"name": "root", "version": "1.0", "sha256": root_digest}]
    (root / "index.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RegistryV2Error, match="cycle"):
        RegistryV2Client(root, expected_origin="https://registry.fixture").resolve("root", "1.0")
    data["packages"][1]["dependencies"] = []
    data["packages"][1]["sha256"] = "0" * 64
    (root / "index.json").write_text(json.dumps(data), encoding="utf-8")
    client = RegistryV2Client(root, expected_origin="https://registry.fixture")
    with pytest.raises(RegistryV2Error, match="digest"):
        client.fetch(client.resolve("leaf", "1.0").root)
    with pytest.raises(RegistryV2Error, match="origin"):
        RegistryV2Client(root, expected_origin="https://other.fixture")


def test_registry_v2_limits_resolution_and_cache(tmp_path) -> None:
    root, _root_digest, _leaf_digest = _registry(tmp_path)
    client = RegistryV2Client(root, expected_origin="https://registry.fixture", limits=RegistryV2Limits(max_resolved_packages=1))
    with pytest.raises(RegistryV2Error, match="resolved package"):
        client.resolve("root", "1.0")
