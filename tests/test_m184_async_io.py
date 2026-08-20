from __future__ import annotations

import sys

from bootstrap.s3.async_io import AsyncIOLimits, AsyncIOService


def test_filesystem_future_is_root_confined_and_bounded(tmp_path) -> None:
    service = AsyncIOService(root=tmp_path, limits=AsyncIOLimits(max_bytes=4))
    write = service.write_file("data.bin", b"data")
    assert write.await_once().is_ok
    assert service.read_file("data.bin").await_once().value_or(None) == b"data"
    assert service.write_file("large.bin", b"too-large").poll().value_or(None).error is not None
    escaped = service.read_file("../outside").poll().value_or(None)
    assert escaped.error is not None and "invalid_path" in escaped.error.detail


def test_process_future_uses_argv_without_shell_and_bounds_output(tmp_path) -> None:
    service = AsyncIOService(root=tmp_path, limits=AsyncIOLimits(max_bytes=64))
    result = service.run_process(sys.executable, ("-c", "print('ok')"), timeout=5).await_once()
    assert result.is_ok
    assert result.value_or(None).stdout.replace(b"\r\n", b"\n") == b"ok\n"
    forbidden = service.run_process("echo ok", shell=True).poll().value_or(None)
    assert forbidden.error is not None and "shell_forbidden" in forbidden.error.detail


def test_process_output_overflow_and_timeout_are_explicit(tmp_path) -> None:
    service = AsyncIOService(root=tmp_path, limits=AsyncIOLimits(max_bytes=32, max_timeout_seconds=5))
    overflow = service.run_process(
        sys.executable,
        ("-c", "import sys; sys.stdout.write('x' * 100000); sys.stdout.flush()"),
        timeout=5,
    ).poll().value_or(None)
    assert overflow.error is not None and "output_limit" in overflow.error.detail
    invalid_timeout = service.run_process(sys.executable, ("-c", "print(1)"), timeout=9).poll().value_or(None)
    assert invalid_timeout.error is not None and "timeout" in invalid_timeout.error.detail


def test_stdout_and_stderr_share_one_capture_budget(tmp_path) -> None:
    service = AsyncIOService(root=tmp_path, limits=AsyncIOLimits(max_bytes=8, max_timeout_seconds=5))
    overflow = service.run_process(
        sys.executable,
        ("-c", "import sys; sys.stdout.write('12345'); sys.stderr.write('67890')"),
        timeout=5,
    ).poll().value_or(None)
    assert overflow.error is not None and "output_limit" in overflow.error.detail
