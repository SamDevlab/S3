from __future__ import annotations

import gzip
import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

import bootstrap.s3.cli as cli
import bootstrap.s3.native_compiler as native_compiler
import bootstrap.s3.s3c_ng_distribution as distribution
import tools.package_s3c_ng_bootstrap as package_tool
from tools.package_s3c_ng_bootstrap import _archive as package_archive


def _candidate() -> tuple[bytes, bytes, dict[str, object]]:
    executable = bytearray(64)
    executable[:4] = b"\x7fELF"
    executable[4] = 2
    executable[5] = 1
    executable[18:20] = (62).to_bytes(2, "little")
    executable_bytes = bytes(executable)
    artifact_sha = hashlib.sha256(executable_bytes).hexdigest()
    ir_sha = "2" * 64
    manifest: dict[str, object] = {
        "schema_version": 2,
        "target": "linux-x86_64",
        "ng_ir_format_version": native_compiler.NG_IR_FORMAT_VERSION,
        "entry_module": "app",
        "entry_symbol": "ng_emit_source_set",
        "optimization_mode": "O0",
        "artifact_sha256": artifact_sha,
        "artifact_bytes": len(executable_bytes),
        "source_commit": "a" * 40,
        "source_graph_sha256": "1" * 64,
        "compiler_ir_sha256": ir_sha,
        "assembly_sha256": "3" * 64,
        "object_sha256": "4" * 64,
        "toolchain": {
            "compiler": "cc",
            "version": "cc 1.0",
            "assembler": "as",
            "linker": "ld",
        },
        "bootstrap_parent": {
            "kind": "python-reference-stage0",
            "canonical_ir_sha256": ir_sha,
        },
    }
    return executable_bytes, (json.dumps(manifest, sort_keys=True) + "\n").encode(), manifest


def _archive(executable: bytes, manifest: bytes, *, executable_name: str = "s3c-ng") -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as tar:
            for name, contents in (
                (executable_name, executable),
                ("s3c-ng.manifest.json", manifest),
            ):
                info = tarfile.TarInfo(name)
                info.size = len(contents)
                info.mode = 0o755 if name == "s3c-ng" else 0o644
                info.uid = info.gid = info.mtime = 0
                tar.addfile(info, io.BytesIO(contents))
    return buffer.getvalue()


def _write_lock(path: Path, archive: bytes, manifest: dict[str, object]) -> None:
    toolchain = manifest["toolchain"]
    assert isinstance(toolchain, dict)
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "PINNED",
                "release_tag": "s3c-ng-bootstrap-v7-test1",
                "asset_name": "s3c-ng-bootstrap-linux-x86_64.tar.gz",
                "asset_sha256": hashlib.sha256(archive).hexdigest(),
                "artifact_sha256": manifest["artifact_sha256"],
                "artifact_bytes": manifest["artifact_bytes"],
                "source_commit": manifest["source_commit"],
                "source_graph_sha256": manifest["source_graph_sha256"],
                "target": "linux-x86_64",
                "toolchain": toolchain,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def _simulate_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(distribution.platform, "system", lambda: "Linux")
    monkeypatch.setattr(distribution.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(native_compiler.platform, "system", lambda: "Linux")
    monkeypatch.setattr(native_compiler.platform, "machine", lambda: "x86_64")


def test_unpublished_bootstrap_lock_fails_closed_without_download(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = Path(distribution.__file__).with_name("s3c_ng_bootstrap_lock.json")
    monkeypatch.setattr(
        distribution,
        "_download",
        lambda _url: pytest.fail("an unpublished lock must not trigger network access"),
    )
    _simulate_linux(monkeypatch)

    with pytest.raises(distribution.BootstrapDistributionError, match="no published"):
        distribution.install_s3c_ng_bootstrap(lock_path=lock, cache_root=tmp_path)


def test_pinned_bootstrap_download_is_verified_and_reused_from_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _simulate_linux(monkeypatch)
    executable, manifest_bytes, manifest = _candidate()
    archive = _archive(executable, manifest_bytes)
    lock = tmp_path / "lock.json"
    _write_lock(lock, archive, manifest)
    downloads: list[str] = []

    def download(url: str) -> bytes:
        downloads.append(url)
        return archive

    monkeypatch.setattr(distribution, "_download", download)
    installed = distribution.install_s3c_ng_bootstrap(
        lock_path=lock,
        cache_root=tmp_path / "cache",
    )
    assert installed == tmp_path / "cache" / "s3c-ng-bootstrap-v7-test1" / "s3c-ng"
    assert installed.read_bytes() == executable
    assert json.loads(installed.with_suffix(".manifest.json").read_text()) == manifest
    assert len(downloads) == 1
    assert downloads[0] == (
        "https://github.com/SamDevlab/S3/releases/download/"
        "s3c-ng-bootstrap-v7-test1/s3c-ng-bootstrap-linux-x86_64.tar.gz"
    )

    monkeypatch.setattr(
        distribution,
        "_download",
        lambda _url: pytest.fail("a valid cache hit must not download again"),
    )
    assert distribution.install_s3c_ng_bootstrap(
        lock_path=lock,
        cache_root=tmp_path / "cache",
    ) == installed


def test_bootstrap_archive_hash_mismatch_does_not_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _simulate_linux(monkeypatch)
    executable, manifest_bytes, manifest = _candidate()
    archive = _archive(executable, manifest_bytes)
    lock = tmp_path / "lock.json"
    _write_lock(lock, archive, manifest)
    payload = json.loads(lock.read_text())
    payload["asset_sha256"] = "f" * 64
    lock.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(distribution, "_download", lambda _url: archive)
    cache = tmp_path / "cache"

    with pytest.raises(distribution.BootstrapDistributionError, match="archive SHA-256"):
        distribution.install_s3c_ng_bootstrap(lock_path=lock, cache_root=cache)
    assert not cache.exists()


def test_bootstrap_manifest_provenance_mismatch_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _simulate_linux(monkeypatch)
    executable, manifest_bytes, manifest = _candidate()
    changed = dict(manifest)
    changed["source_commit"] = "b" * 40
    archive = _archive(executable, (json.dumps(changed, sort_keys=True) + "\n").encode())
    lock = tmp_path / "lock.json"
    _write_lock(lock, archive, manifest)
    monkeypatch.setattr(distribution, "_download", lambda _url: archive)

    with pytest.raises(distribution.BootstrapDistributionError, match="pinned provenance"):
        distribution.install_s3c_ng_bootstrap(lock_path=lock, cache_root=tmp_path / "cache")


def test_default_managed_candidate_is_checked_against_the_pinned_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _simulate_linux(monkeypatch)
    executable, manifest_bytes, manifest = _candidate()
    archive = _archive(executable, manifest_bytes)
    lock = tmp_path / "lock.json"
    _write_lock(lock, archive, manifest)
    cache = tmp_path / "cache"
    monkeypatch.setattr(distribution, "_LOCK_PATH", lock)
    monkeypatch.setenv("S3_BOOTSTRAP_CACHE", str(cache))
    monkeypatch.setattr(distribution, "_download", lambda _url: archive)
    installed = distribution.install_s3c_ng_bootstrap(lock_path=lock, cache_root=cache)
    assert native_compiler.inspect_s3c_ng_executable().available

    damaged = bytearray(installed.read_bytes())
    damaged[-1] ^= 0x01
    installed.write_bytes(damaged)
    updated_manifest = dict(manifest)
    updated_manifest["artifact_sha256"] = hashlib.sha256(damaged).hexdigest()
    installed.with_suffix(".manifest.json").write_text(
        json.dumps(updated_manifest), encoding="utf-8"
    )
    availability = native_compiler.inspect_s3c_ng_executable()
    assert not availability.available
    assert "pinned provenance" in (availability.reason or "")


def test_bootstrap_archive_rejects_unexpected_member_name() -> None:
    executable, manifest, _ = _candidate()
    archive = _archive(executable, manifest, executable_name="../s3c-ng")

    with pytest.raises(distribution.BootstrapDistributionError, match="exactly the executable"):
        distribution._archive_members(archive)


def test_release_archive_packaging_is_deterministic() -> None:
    executable, manifest, _ = _candidate()

    assert package_archive(executable, manifest) == package_archive(executable, manifest)


def test_release_packager_requires_matching_clean_source_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_commit = "a" * 40
    graph_sha256 = "b" * 64
    commands: list[tuple[str, ...]] = []

    def git(_repository: Path, *arguments: str) -> str:
        commands.append(arguments)
        if arguments == ("rev-parse", "HEAD"):
            return source_commit
        return ""

    monkeypatch.setattr(package_tool, "_git", git)
    monkeypatch.setattr(
        package_tool,
        "compiler_source_set",
        lambda _repo: {"main.s3": "fn main():\n    return 0\n"},
    )
    monkeypatch.setattr(
        package_tool, "compiler_source_graph_sha256", lambda _sources: graph_sha256
    )
    manifest = {
        "source_commit": source_commit,
        "source_graph_sha256": graph_sha256,
        "toolchain": {
            "compiler": "cc",
            "version": "cc 1",
            "assembler": "as",
            "linker": "ld",
        },
    }

    package_tool._validate_source_provenance(tmp_path, manifest)
    assert ("status", "--porcelain", "--", *package_tool._COMPILER_INPUTS) in commands


@pytest.mark.parametrize(
    ("manifest_update", "git_status", "graph_result", "message"),
    [
        ({"source_commit": "c" * 40}, "", "b" * 64, "source commit"),
        ({}, " M selfhost/compiler_ng/module.s3", "b" * 64, "must be clean"),
        ({}, "", "c" * 64, "source graph"),
        ({"toolchain": {"compiler": "cc"}}, "", "b" * 64, "toolchain provenance"),
    ],
)
def test_release_packager_rejects_untrusted_source_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest_update: dict[str, object],
    git_status: str,
    graph_result: str,
    message: str,
) -> None:
    source_commit = "a" * 40
    graph_sha256 = "b" * 64

    def git(_repository: Path, *arguments: str) -> str:
        if arguments == ("rev-parse", "HEAD"):
            return source_commit
        return git_status

    monkeypatch.setattr(package_tool, "_git", git)
    monkeypatch.setattr(
        package_tool, "compiler_source_set", lambda _repo: {"main.s3": "source"}
    )
    monkeypatch.setattr(
        package_tool, "compiler_source_graph_sha256", lambda _sources: graph_result
    )
    manifest: dict[str, object] = {
        "source_commit": source_commit,
        "source_graph_sha256": graph_sha256,
        "toolchain": {
            "compiler": "cc",
            "version": "cc 1",
            "assembler": "as",
            "linker": "ld",
        },
    }
    manifest.update(manifest_update)

    with pytest.raises(ValueError, match=message):
        package_tool._validate_source_provenance(tmp_path, manifest)


def test_bootstrap_distribution_is_linux_x86_64_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(distribution.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        distribution,
        "_download",
        lambda _url: pytest.fail("unsupported hosts must not download"),
    )

    with pytest.raises(distribution.BootstrapDistributionError, match="Linux x86-64 only"):
        distribution.install_s3c_ng_bootstrap(cache_root=tmp_path)


def test_bootstrap_install_cli_reports_explicitly_installed_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected = tmp_path / "s3c-ng"
    monkeypatch.setattr(cli, "install_s3c_ng_bootstrap", lambda: expected)

    assert cli.main(["bootstrap", "install", "s3c-ng"]) == 0
    assert capsys.readouterr().out == f"{expected}\n"
