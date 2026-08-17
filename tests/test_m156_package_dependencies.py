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
