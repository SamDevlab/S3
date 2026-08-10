from __future__ import annotations

import pytest

from bootstrap.s3.s3_docker import DockerConfigError, DockerSpec


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

