from __future__ import annotations

import json
import subprocess

import pytest

import bootstrap.s3.cli as cli
from bootstrap.s3.container_backend import (
    ContainerBackendError,
    DockerCliBackend,
    OciDescriptor,
    OciFilesystemEntry,
    OciFilesystemLayerPlan,
    OciImageConfig,
    OciImageLayout,
    OciImageManifest,
    S3OciBackend,
    select_container_backend,
)
from bootstrap.s3.project_container import ProjectTooling


def test_oci_descriptors_and_canonical_documents_are_deterministic() -> None:
    config = OciImageConfig(
        entrypoint=("s3", "run", "/app/main.s3"),
        environment=(("MODE", "test"),),
    )
    layer = OciFilesystemLayerPlan(
        (
            OciFilesystemEntry(
                "src/main.s3",
                OciDescriptor.from_bytes("text/plain", b"main\n"),
            ),
        )
    )
    manifest = OciImageManifest(config.descriptor(), (layer.descriptor(),))
    layout = OciImageLayout(manifest.descriptor())

    assert config.canonical_bytes() == config.canonical_bytes()
    assert manifest.canonical_bytes() == manifest.canonical_bytes()
    assert layout.layout_bytes() == b'{"imageLayoutVersion":"1.0.0"}\n'
    assert layout.archive_members() == (
        "oci-layout",
        "index.json",
        f"blobs/sha256/{manifest.descriptor().digest.removeprefix('sha256:')}",
    )
    assert OciDescriptor.from_bytes("text/plain", b"main\n").digest != OciDescriptor.from_bytes(
        "text/plain", b"changed\n"
    ).digest
    assert layout.index_bytes() == layout.index_bytes()


def test_oci_contracts_reject_unordered_or_invalid_metadata() -> None:
    with pytest.raises(ContainerBackendError, match="sorted"):
        OciDescriptor(
            "text/plain",
            "sha256:" + "0" * 64,
            0,
            (("Z", "1"), ("A", "2")),
        )
    with pytest.raises(ContainerBackendError, match="relative"):
        OciFilesystemEntry(
            "../secret",
            OciDescriptor.from_bytes("text/plain", b"secret"),
        )


def test_backend_selection_is_explicit_and_auto_fallback_is_recorded() -> None:
    docker, docker_selection = select_container_backend("docker")
    auto, auto_selection = select_container_backend("auto")
    s3, s3_selection = select_container_backend("s3")

    assert isinstance(docker, DockerCliBackend)
    assert isinstance(auto, DockerCliBackend)
    assert isinstance(s3, S3OciBackend)
    assert docker_selection.evidence() == {
        "CONTAINER_BACKEND": "docker",
        "FALLBACK_REASON": "none",
    }
    assert auto_selection.evidence() == {
        "CONTAINER_BACKEND": "docker",
        "FALLBACK_REASON": "S3_OCI_BACKEND_NOT_QUALIFIED",
    }
    assert s3_selection.evidence() == {
        "CONTAINER_BACKEND": "s3",
        "FALLBACK_REASON": "none",
    }
    assert not isinstance(s3, DockerCliBackend)
    with pytest.raises(ContainerBackendError, match="unsupported"):
        select_container_backend("invalid")


def test_docker_cli_backend_keeps_real_provider_path() -> None:
    calls: list[tuple[str, ...]] = []

    def runner(argv, **kwargs):
        del kwargs
        calls.append(tuple(argv))
        return subprocess.CompletedProcess(argv, 0, "27.0\n", "")

    backend = DockerCliBackend(runner=runner)
    result = backend.version()
    assert result.ok
    assert calls == [("docker", "version", "--format", "{{.Server.Version}}")]


def test_s3_oci_plan_is_structural_and_build_fails_closed(tmp_path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.s3").write_text(
        "module main\n\nfn main() -> i64:\n    return 7\n",
        encoding="ascii",
    )
    (tmp_path / "s3.toml").write_text(
        "[project]\nname='app'\nversion='1'\nentrypoint='main'\n"
        "source_roots=['src']\nprofile='hosted'\n",
        encoding="ascii",
    )

    backend = S3OciBackend()
    plan = backend.plan(ProjectTooling(tmp_path), "s3/app:experimental")
    assert plan["provider"] == "s3-oci"
    assert plan["qualified"] is False
    assert plan["export"] == "oci-layout-and-tar-contract-only"
    with pytest.raises(ContainerBackendError, match="experimental"):
        backend.build()


def test_cli_auto_backend_reports_docker_fallback(tmp_path, capsys) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.s3").write_text("return 1\n", encoding="ascii")
    (tmp_path / "s3.toml").write_text(
        "[project]\nname='app'\nversion='1'\nentrypoint='main'\n"
        "source_roots=['src']\nprofile='hosted'\n",
        encoding="ascii",
    )

    assert cli.main(
        ["container", "inspect", str(tmp_path), "--image", "s3/app:dev", "--backend", "auto"]
    ) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["CONTAINER_BACKEND"] == "docker"
    assert payload["FALLBACK_REASON"] == "S3_OCI_BACKEND_NOT_QUALIFIED"


def test_cli_explicit_s3_build_is_fail_closed(tmp_path, capsys) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.s3").write_text("return 1\n", encoding="ascii")
    (tmp_path / "s3.toml").write_text(
        "[project]\nname='app'\nversion='1'\nentrypoint='main'\n"
        "source_roots=['src']\nprofile='hosted'\n",
        encoding="ascii",
    )

    assert cli.main(
        ["container", "build", str(tmp_path), "--image", "s3/app:dev", "--backend", "s3"]
    ) == 1
    assert "CONTAINER_BACKEND=s3" in capsys.readouterr().err
