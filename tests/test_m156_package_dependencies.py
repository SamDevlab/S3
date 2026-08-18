from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.package_dependencies import (
    PackageDependency,
    PackageDependencyError,
    PackageLock,
    PackageManifest,
    parse_package_manifest,
)


def test_package_manifest_and_lock_are_canonical_and_revision_pinned(tmp_path: Path) -> None:
    manifest_path = tmp_path / "package.toml"
    manifest_path.write_text(
        "[package]\n"
        "name = 'app'\n"
        "version = '1.0.0'\n"
        "\n"
        "[[dependency]]\n"
        "name = 'core'\n"
        "source = 'core'\n"
        "revision = 'abcdef1234567'\n"
        "\n"
        "[[dependency]]\n"
        "name = 'util'\n"
        "source = 'git+https://example.invalid/util'\n"
        "revision = '0123456789abcdef'\n",
        encoding="utf-8",
    )
    manifest = parse_package_manifest(str(manifest_path))
    assert [item.name for item in manifest.dependencies] == ["core", "util"]

    manifests = {
        "app": manifest,
        "core": PackageManifest("core", "2.0.0"),
        "util": PackageManifest("util", "3.0.0"),
    }
    lock = PackageLock.resolve("app", manifests)
    assert lock.topological_order == ("core", "util", "app")
    assert lock.payload["format"] == "s3.package-lock.v1"
    assert lock.text == PackageLock.resolve("app", dict(reversed(list(manifests.items())))).text
    assert lock.sha256
    assert "tmp_path" not in lock.text


def test_package_resolution_rejects_missing_dependencies_and_cycles() -> None:
    missing = {
        "app": PackageManifest(
            "app",
            "1.0.0",
            (PackageDependency("core", "core"),),
        )
    }
    with pytest.raises(PackageDependencyError, match="missing package dependency"):
        PackageLock.resolve("app", missing)

    cycle = {
        "a": PackageManifest("a", "1.0.0", (PackageDependency("b", "b"),)),
        "b": PackageManifest("b", "1.0.0", (PackageDependency("a", "a"),)),
    }
    with pytest.raises(PackageDependencyError, match="dependency cycle"):
        PackageLock.resolve("a", cycle)


def test_package_source_and_revision_contracts_are_fail_closed() -> None:
    with pytest.raises(PackageDependencyError, match="stay relative"):
        PackageDependency("core", "../outside")
    with pytest.raises(PackageDependencyError, match="require an immutable revision"):
        PackageDependency("core", "git+https://example.invalid/core")
    with pytest.raises(PackageDependencyError, match="hexadecimal"):
        PackageDependency("core", "core", "not-a-revision")


def _diamond_manifests(
    left_reference: PackageDependency,
    right_reference: PackageDependency,
    *,
    include_unreachable: bool = False,
) -> dict[str, PackageManifest]:
    manifests = {
        "root": PackageManifest(
            "root",
            "1.0.0",
            (
                PackageDependency("left", "left"),
                PackageDependency("right", "right"),
            ),
        ),
        "left": PackageManifest("left", "1.0.0", (left_reference,)),
        "right": PackageManifest("right", "1.0.0", (right_reference,)),
        "core": PackageManifest("core", "1.0.0"),
    }
    if include_unreachable:
        manifests["unreachable"] = PackageManifest(
            "unreachable",
            "1.0.0",
            (PackageDependency("core", "unrelated", "ccccccc"),),
        )
    return manifests


def test_conflicting_reachable_dependency_sources_fail_closed() -> None:
    forward = _diamond_manifests(
        PackageDependency("core", "vendor/core-a", "aaaaaaa"),
        PackageDependency("core", "vendor/core-b", "bbbbbbb"),
    )
    reverse = {
        "root": forward["root"],
        "right": forward["right"],
        "left": forward["left"],
        "core": forward["core"],
    }
    messages = []
    for manifests in (forward, reverse):
        with pytest.raises(PackageDependencyError, match="inconsistent dependency identity.*core") as error:
            PackageLock.resolve("root", manifests)
        messages.append(str(error.value))
    assert messages[0] == messages[1]


def test_conflicting_reachable_dependency_revisions_fail_closed() -> None:
    manifests = _diamond_manifests(
        PackageDependency("core", "vendor/core", "aaaaaaa"),
        PackageDependency("core", "vendor/core", "bbbbbbb"),
    )
    with pytest.raises(PackageDependencyError, match="inconsistent dependency identity.*core"):
        PackageLock.resolve("root", manifests)


def test_identical_multi_parent_dependency_is_canonical_and_order_independent() -> None:
    manifests = _diamond_manifests(
        PackageDependency("core", "vendor/core", "aaaaaaa"),
        PackageDependency("core", "vendor/core", "aaaaaaa"),
    )
    reversed_manifests = {
        "root": manifests["root"],
        "right": manifests["right"],
        "left": manifests["left"],
        "core": manifests["core"],
    }
    lock = PackageLock.resolve("root", manifests)
    reversed_lock = PackageLock.resolve("root", reversed_manifests)
    core = next(entry for entry in lock.entries if entry.name == "core")
    assert core.source == "vendor/core"
    assert core.revision == "aaaaaaa"
    assert lock.text == reversed_lock.text
    assert lock.sha256 == reversed_lock.sha256


def test_unreachable_dependency_reference_does_not_influence_root_lock() -> None:
    reachable = _diamond_manifests(
        PackageDependency("core", "vendor/core", "aaaaaaa"),
        PackageDependency("core", "vendor/core", "aaaaaaa"),
    )
    with_unreachable = _diamond_manifests(
        PackageDependency("core", "vendor/core", "aaaaaaa"),
        PackageDependency("core", "vendor/core", "aaaaaaa"),
        include_unreachable=True,
    )
    lock = PackageLock.resolve("root", reachable)
    lock_with_unreachable = PackageLock.resolve("root", with_unreachable)
    assert lock.text == lock_with_unreachable.text
    assert lock.sha256 == lock_with_unreachable.sha256
