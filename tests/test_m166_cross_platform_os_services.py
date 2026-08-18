from __future__ import annotations

import sys

from bootstrap.s3.os_services import (
    CrossPlatformOSServices,
    HostErrorCode,
    HostPath,
)


def test_relative_paths_and_directory_listing_are_deterministic(tmp_path) -> None:
    provider = CrossPlatformOSServices(root=tmp_path, environment={})
    (tmp_path / "b.txt").write_text("b", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "folder").mkdir()

    result = provider.list_directory(HostPath("."))
    assert result.is_ok
    assert [entry.name for entry in result.value_or(())] == ["a.txt", "b.txt", "folder"]


def test_owned_file_closes_deterministically_and_reports_closed_use(tmp_path) -> None:
    provider = CrossPlatformOSServices(root=tmp_path, environment={})
    opened = provider.open_text(HostPath("nested/value.txt"), "w")
    assert opened.is_ok
    handle = opened.value_or(None)
    assert handle is not None
    assert handle.write("payload").is_ok
    handle.close()
    handle.close()
    failure = handle.write("again")
    assert failure.is_err
    assert failure.error_or(None).code is HostErrorCode.CLOSED
    assert (tmp_path / "nested" / "value.txt").read_text(encoding="utf-8") == "payload"


def test_missing_and_escape_paths_are_explicit_errors(tmp_path) -> None:
    provider = CrossPlatformOSServices(root=tmp_path, environment={})
    missing = provider.open_text(HostPath("missing.txt"))
    assert missing.is_err
    assert missing.error_or(None).code is HostErrorCode.NOT_FOUND
    escape = provider.open_text(HostPath("../outside.txt"))
    assert escape.is_err
    assert escape.error_or(None).code is HostErrorCode.INVALID_PATH


def test_environment_argv_and_nonzero_process_result_are_explicit(tmp_path) -> None:
    provider = CrossPlatformOSServices(
        root=tmp_path,
        argv=("s3", "main.s3"),
        environment={"S3_MODE": "test"},
    )
    assert provider.argv() == ("s3", "main.s3")
    assert provider.environment("S3_MODE").value_or("") == "test"
    assert provider.environment("MISSING").is_none
    result = provider.spawn(sys.executable, ("-c", "import sys; sys.exit(7)"))
    assert result.is_ok
    assert result.value_or(None).returncode == 7
    assert provider.spawn(sys.executable, ("-c", "pass"), timeout=30.001).error_or(None).code is HostErrorCode.TIMEOUT
    assert provider.spawn(sys.executable, (None,)).error_or(None).code is HostErrorCode.PROCESS_START


def test_linux_and_windows_style_provider_contract_uses_no_absolute_identity(tmp_path) -> None:
    provider = CrossPlatformOSServices(root=tmp_path, environment={})
    assert HostPath("folder/file.txt").value == "folder/file.txt"
    assert provider.open_text(HostPath("folder/file.txt"), "w").is_ok
