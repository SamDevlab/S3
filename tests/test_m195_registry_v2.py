from __future__ import annotations

import hashlib
import json

import pytest

from bootstrap.s3.registry_v2 import RegistryV2Client, RegistryV2Error, RegistryV2Limits, _constraint_matches


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


def test_registry_v2_resolves_a_bounded_semver_range_deterministically(tmp_path) -> None:
    root, _root_digest, leaf_digest = _registry(tmp_path)
    data = json.loads((root / "index.json").read_text(encoding="utf-8"))
    leaf = data["packages"][1]
    data["packages"].append({**leaf, "version": "1.1"})
    data["packages"][0]["dependencies"] = [{"name": "leaf", "version": "^1.0", "sha256": leaf_digest}]
    (root / "index.json").write_text(json.dumps(data), encoding="utf-8")
    client = RegistryV2Client(root, expected_origin="https://registry.fixture")
    assert client.resolve("root", "1.0").packages[-1].version == "1.1"


@pytest.mark.parametrize(
    ("constraint", "accepted"),
    (
        ("1.2", "1.2"),
        ("1.x", "1.9"),
        ("^0.0.x", "0.0.7"),
        ("^0.x", "0.9"),
        ("~1.2", "1.2.9"),
        (">=1.0", "1.4"),
        (">1.0", "1.1"),
        ("<=1.0", "1.0"),
        ("<1.0", "0.9"),
        (">=1.0,<2.0", "1.9"),
    ),
)
def test_registry_v2_constraint_subset_has_explicit_major_zero_and_comparator_semantics(constraint, accepted) -> None:
    assert _constraint_matches(accepted, constraint)


def test_registry_v2_range_dependencies_do_not_require_a_preselected_digest(tmp_path) -> None:
    root, _root_digest, leaf_digest = _registry(tmp_path)
    data = json.loads((root / "index.json").read_text(encoding="utf-8"))
    leaf = data["packages"][1]
    data["packages"].append({**leaf, "version": "1.1", "sha256": hashlib.sha256(b"leaf-1.1").hexdigest()})
    (root / "objects" / "leaf-1.1.tar").write_bytes(b"leaf-1.1")
    data["packages"][0]["dependencies"] = [{"name": "leaf", "version": "^1"}]
    (root / "index.json").write_text(json.dumps(data), encoding="utf-8")
    client = RegistryV2Client(root, expected_origin="https://registry.fixture")
    resolution = client.resolve("root", "1.0")
    assert resolution.packages[-1].version == "1.1"
    assert resolution.packages[-1].sha256 != leaf_digest


def test_registry_v2_rejects_transitive_constraints_with_different_versions_and_digests(tmp_path) -> None:
    root, root_digest, leaf_digest = _registry(tmp_path)
    leaf_two = b"leaf-two"
    leaf_two_digest = hashlib.sha256(leaf_two).hexdigest()
    (root / "objects" / "leaf-two.tar").write_bytes(leaf_two)
    data = json.loads((root / "index.json").read_text(encoding="utf-8"))
    leaf = data["packages"][1]
    data["packages"].extend(
        [
            {**leaf, "version": "1.1", "sha256": hashlib.sha256(b"leaf-1.1").hexdigest(), "object": "objects/leaf-1.1.tar"},
            {**leaf, "version": "2.0", "sha256": leaf_two_digest, "object": "objects/leaf-two.tar"},
        ]
    )
    (root / "objects" / "leaf-1.1.tar").write_bytes(b"leaf-1.1")
    data["packages"][0]["dependencies"] = [
        {"name": "leaf", "version": "^1", "sha256": data["packages"][2]["sha256"]},
        {"name": "leaf", "version": "^2", "sha256": leaf_two_digest},
    ]
    (root / "index.json").write_text(json.dumps(data), encoding="utf-8")
    client = RegistryV2Client(root, expected_origin="https://registry.fixture")
    with pytest.raises(RegistryV2Error, match="version conflict"):
        client.resolve("root", "1.0")


@pytest.mark.parametrize("object_name", ("/absolute", "../escape", "objects//empty", "objects/./dot", "objects\\name", "C:drive"))
def test_registry_v2_rejects_object_paths_that_are_not_root_relative(tmp_path, object_name) -> None:
    root, _root_digest, _leaf_digest = _registry(tmp_path)
    data = json.loads((root / "index.json").read_text(encoding="utf-8"))
    data["packages"][0]["object"] = object_name
    (root / "index.json").write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RegistryV2Error, match="object path"):
        RegistryV2Client(root, expected_origin="https://registry.fixture")


def test_registry_v2_normalizes_bounded_read_errors(tmp_path) -> None:
    root, _root_digest, _leaf_digest = _registry(tmp_path)
    (root / "index.json").write_bytes(b"{}" * 100)
    with pytest.raises(RegistryV2Error, match="index LIMIT"):
        RegistryV2Client(root, expected_origin="https://registry.fixture", limits=RegistryV2Limits(max_index_bytes=2))
