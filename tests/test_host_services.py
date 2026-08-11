from __future__ import annotations

import sys

import pytest

from bootstrap.s3.dynamic import DynamicError, DynamicKind, DynamicValue
from bootstrap.s3.host_services import (
    HostService,
    HostServiceError,
    HostServiceRegistry,
    HostServiceRequest,
    LinuxHostServices,
)


def test_host_service_registry_is_explicit_and_injectable() -> None:
    registry = HostServiceRegistry()
    registry.register(
        HostService.DIAGNOSTIC,
        lambda arguments: DynamicValue.i64(len(arguments)),
    )
    result = registry.invoke(
        HostServiceRequest(HostService.DIAGNOSTIC, (DynamicValue.tryte(1),))
    )
    assert result.kind is DynamicKind.I64
    assert result.value == 1


def test_host_service_registry_rejects_missing_or_duplicate_services() -> None:
    registry = HostServiceRegistry()
    request = HostServiceRequest(HostService.CLOCK_MONOTONIC)
    with pytest.raises(HostServiceError, match="unavailable"):
        registry.invoke(request)
    registry.register(HostService.CLOCK_MONOTONIC, lambda _: DynamicValue.i64(1))
    with pytest.raises(HostServiceError, match="already registered"):
        registry.register(HostService.CLOCK_MONOTONIC, lambda _: DynamicValue.i64(2))


def test_host_service_handler_result_is_checked() -> None:
    registry = HostServiceRegistry()
    registry.register(HostService.DIAGNOSTIC, lambda _: DynamicValue.i64(1))
    assert registry.invoke(HostServiceRequest(HostService.DIAGNOSTIC)).value == 1


def test_linux_provider_covers_argv_environment_files_and_stdio(tmp_path) -> None:
    helper = tmp_path / "helper.py"
    helper.write_text(
        "import os, sys\n"
        "data = sys.stdin.read()\n"
        "print(os.environ['S3_HELPER_MODE'] + ':' + '|'.join(sys.argv[1:]) + ':' + data)\n"
        "print('helper-stderr', file=sys.stderr)\n",
        encoding="ascii",
    )
    provider = LinuxHostServices(
        argv=("s3", "input.s3"),
        environment={"S3_HELPER_MODE": "test"},
    )
    assert provider.argv() == ("s3", "input.s3")
    assert provider.environment("S3_HELPER_MODE") == "test"
    path = tmp_path / "nested" / "output.txt"
    provider.write_file(path, "payload")
    assert provider.read_file(path) == "payload"
    result = provider.spawn(sys.executable, (str(helper), "a", "b"), stdin="stdin")
    assert result.returncode == 0
    assert result.stdout.strip() == "test:a|b:stdin"
    assert result.stderr.strip() == "helper-stderr"


def test_linux_provider_spawn_wait_exit_and_pipe() -> None:
    provider = LinuxHostServices(environment={})
    failed = provider.spawn(sys.executable, ("-c", "import sys; sys.exit(7)"))
    assert failed.returncode == 7
    piped = provider.pipe(
        (sys.executable, ("-c", "print('pipe-data')")),
        (sys.executable, ("-c", "import sys; print(sys.stdin.read().strip().upper())")),
    )
    assert piped.returncode == 0
    assert piped.stdout.strip() == "PIPE-DATA"
