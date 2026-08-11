from __future__ import annotations

import subprocess

import pytest

from bootstrap.s3.s3_docker import DockerConfigError, DockerProvider, DockerSpec


def test_docker_spec_has_deterministic_argv() -> None:
    spec = DockerSpec("s3/compiler:1.38", ("compile", "main.s3"), (("MODE", "check"),))
    assert spec.argv == ("docker", "run", "--rm", "s3/compiler:1.38", "compile", "main.s3")


def test_docker_spec_rejects_invalid_image_and_command() -> None:
    with pytest.raises(DockerConfigError, match="image"):
        DockerSpec("S3/compiler", ("compile",))
    with pytest.raises(DockerConfigError, match="non-empty"):
        DockerSpec("s3/compiler", ())


def test_docker_spec_requires_sorted_unique_environment_and_bounded_timeout() -> None:
    with pytest.raises(DockerConfigError, match="sorted"):
        DockerSpec("s3/compiler", ("compile",), (("Z", "1"), ("A", "2")))
    with pytest.raises(DockerConfigError, match="between"):
        DockerSpec("s3/compiler", ("compile",), timeout_seconds=0)


def test_docker_provider_preserves_real_cli_argv_and_plan() -> None:
    calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def runner(argv, **kwargs):
        calls.append((tuple(argv), kwargs))
        return subprocess.CompletedProcess(argv, 0, "ok\n", "")

    provider = DockerProvider(runner=runner)
    spec = DockerSpec("s3/app:1.38", ("run", "/app/main.s3"), (("MODE", "test"),))
    result = provider.run(spec)
    assert result.ok
    assert result.argv == (
        "docker", "run", "--rm", "--env=MODE=test", "s3/app:1.38",
        "run", "/app/main.s3",
    )
    assert calls[0][0] == result.argv
    assert provider.plan(spec)["kind"] == "s3.docker.plan.v1"


def test_docker_provider_writes_deterministic_build_context(tmp_path) -> None:
    provider = DockerProvider(runner=lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "", ""))
    context = provider.write_deterministic_context(
        tmp_path,
        image="s3/runtime:1.38",
        entrypoint=("s3", "run", "/app/main.s3"),
        source_files={"src/z.s3": "z\n", "src/main.s3": "main\n"},
        foreign_helpers={"helper": "#!/bin/sh\necho helper\n"},
    )
    assert context == tmp_path
    assert (tmp_path / "Dockerfile").read_text(encoding="utf-8") == (
        "FROM s3/runtime:1.38\n"
        "WORKDIR /app\n"
        "COPY . /app\n"
        "COPY foreign /opt/s3/foreign\n"
        "RUN chmod +x /opt/s3/foreign/*\n"
        'ENTRYPOINT ["s3","run","/app/main.s3"]\n'
    )
    assert (tmp_path / "foreign" / "helper").read_text(encoding="ascii").startswith("#!/bin/sh")
    assert provider.build(tmp_path, "s3/app:1.38").ok

