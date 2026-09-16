"""Parent-side isolated subprocess runner for S3 Reliability Lab v2 R1."""

from __future__ import annotations

import base64
import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from tools.reliability_contract_v2 import (
    DEFAULT_RESOURCE_POLICY,
    WORKER_REQUEST_SCHEMA,
    WORKER_RESPONSE_SCHEMA,
    canonical_json_document,
    decode_and_verify_source,
    sha256_hex,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKER_MODULE = "tools.reliability_worker_v2"
_PROTOCOL_STDOUT_MAX_BYTES = 3 * 1024 * 1024
_PROTOCOL_STDERR_MAX_BYTES = DEFAULT_RESOURCE_POLICY.stderr_max_bytes
_RESPONSE_KEYS = {
    "schema",
    "case_id",
    "status",
    "operation",
    "exit_code",
    "signal",
    "result_sha256",
    "diagnostic_code",
    "diagnostic_family",
    "stdout_b64",
    "stderr_b64",
    "worker_error_family",
}


@dataclass(frozen=True, slots=True)
class IsolatedRunResult:
    """Parent observation of exactly one fresh worker process."""

    status: str
    failure_signature: str | None
    response: dict[str, object] | None
    process_exit_code: int | None
    reaped: bool
    stdout_sha256: str
    stderr_sha256: str
    stdout_bytes: int
    stderr_bytes: int
    stdout_truncated: bool
    stderr_truncated: bool


class _BoundedReader:
    def __init__(self, stream, limit: int) -> None:
        self._stream = stream
        self._limit = limit
        self._data = bytearray()
        self.overflow = threading.Event()
        self.done = threading.Event()

    def run(self) -> None:
        try:
            while True:
                chunk = self._stream.read(64 * 1024)
                if not chunk:
                    break
                remaining = self._limit - len(self._data)
                if remaining > 0:
                    self._data.extend(chunk[:remaining])
                if len(chunk) > max(0, remaining):
                    self.overflow.set()
                # After overflow keep draining so a writer cannot deadlock while
                # the parent performs process-tree termination.
        finally:
            self.done.set()

    @property
    def data(self) -> bytes:
        return bytes(self._data)


def _require_request_shape(request: Mapping[str, object]) -> None:
    if request.get("schema") != WORKER_REQUEST_SCHEMA:
        raise ValueError("unsupported worker request schema")
    case_id = request.get("case_id")
    if (
        not isinstance(case_id, str)
        or len(case_id) != 64
        or any(ch not in "0123456789abcdef" for ch in case_id)
    ):
        raise ValueError("invalid case_id")
    operation = request.get("operation")
    if operation not in {"CHECK", "RUN_HOSTED", "RUN_NATIVE"}:
        raise ValueError("invalid worker operation")
    optimization = request.get("optimization")
    if optimization not in {"O0", "O1"}:
        raise ValueError("invalid optimization")
    backend = request.get("backend")
    if backend not in {"hosted", "linux-x86_64-native"}:
        raise ValueError("invalid backend")
    source_b64 = request.get("source_b64")
    source_sha256 = request.get("source_sha256")
    source_bytes = request.get("source_bytes")
    if not isinstance(source_b64, str) or not isinstance(source_sha256, str):
        raise ValueError("invalid source transport")
    if isinstance(source_bytes, bool) or not isinstance(source_bytes, int):
        raise ValueError("invalid source byte count")
    decode_and_verify_source(source_b64, source_sha256, source_bytes)


def _timeout_budget_ms(request: Mapping[str, object]) -> int:
    if request.get("backend") == "linux-x86_64-native":
        return DEFAULT_RESOURCE_POLICY.native_case_wall_ms
    return DEFAULT_RESOURCE_POLICY.hosted_case_wall_ms


def _default_worker_argv() -> tuple[str, ...]:
    return (sys.executable, "-m", _WORKER_MODULE)


def _taskkill(pid: int, *, force: bool, timeout_seconds: float) -> None:
    command = ["taskkill", "/PID", str(pid), "/T"]
    if force:
        command.append("/F")
    try:
        subprocess.run(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=max(0.1, timeout_seconds),
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def _kill_process_tree(process: subprocess.Popen[bytes], grace_ms: int) -> bool:
    grace_seconds = max(0.0, grace_ms / 1000.0)

    if os.name == "nt":
        _taskkill(process.pid, force=False, timeout_seconds=max(0.25, grace_seconds))
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            pass
        _taskkill(process.pid, force=True, timeout_seconds=max(0.25, grace_seconds))
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            pass
        # Send SIGKILL to the group even when the leader already exited; a
        # descendant may still hold inherited pipes open.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if process.poll() is None:
            try:
                process.kill()
            except OSError:
                pass

    try:
        process.wait(timeout=max(1.0, grace_seconds + 0.5))
    except subprocess.TimeoutExpired:
        return False
    return process.poll() is not None


def _crash_signature(operation: object, return_code: int | None) -> str:
    if return_code is None:
        return f"crash:{operation}:missing-exit-code"
    if return_code < 0 and os.name != "nt":
        try:
            signal_name = signal.Signals(-return_code).name
        except ValueError:
            signal_name = f"SIG{-return_code}"
        return f"crash:{operation}:signal-{signal_name}"
    return f"crash:{operation}:exit-{return_code}"


def _result(
    *,
    status: str,
    failure_signature: str | None,
    response: dict[str, object] | None,
    process: subprocess.Popen[bytes],
    reaped: bool,
    stdout_reader: _BoundedReader,
    stderr_reader: _BoundedReader,
) -> IsolatedRunResult:
    stdout = stdout_reader.data
    stderr = stderr_reader.data
    return IsolatedRunResult(
        status=status,
        failure_signature=failure_signature,
        response=response,
        process_exit_code=process.poll(),
        reaped=reaped,
        stdout_sha256=sha256_hex(stdout),
        stderr_sha256=sha256_hex(stderr),
        stdout_bytes=len(stdout),
        stderr_bytes=len(stderr),
        stdout_truncated=stdout_reader.overflow.is_set(),
        stderr_truncated=stderr_reader.overflow.is_set(),
    )


def _decode_channel(value: object, name: str, limit: int) -> bytes:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be Base64 text")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except Exception as error:
        raise ValueError(f"{name} is not valid Base64") from error
    if len(decoded) > limit:
        raise OverflowError(name)
    return decoded


def _validate_response(
    request: Mapping[str, object],
    raw_stdout: bytes,
) -> tuple[dict[str, object], str | None]:
    try:
        text = raw_stdout.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("worker response is not UTF-8") from error
    try:
        response = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("worker response is not valid JSON") from error
    if not isinstance(response, dict):
        raise ValueError("worker response root must be an object")
    if set(response) != _RESPONSE_KEYS:
        raise ValueError("worker response keys do not match frozen protocol")
    if response.get("schema") != WORKER_RESPONSE_SCHEMA:
        raise ValueError("unsupported worker response schema")
    if response.get("case_id") != request.get("case_id"):
        raise ValueError("worker response case_id mismatch")
    if response.get("operation") != request.get("operation"):
        raise ValueError("worker response operation mismatch")
    if response.get("status") not in {"COMPLETED", "REJECTED", "WORKER_ERROR"}:
        raise ValueError("unknown worker response status")
    if canonical_json_document(response) != raw_stdout:
        raise ValueError("worker response is not canonical JSON")

    try:
        _decode_channel(
            response.get("stdout_b64"),
            "stdout_b64",
            DEFAULT_RESOURCE_POLICY.stdout_max_bytes,
        )
        _decode_channel(
            response.get("stderr_b64"),
            "stderr_b64",
            DEFAULT_RESOURCE_POLICY.stderr_max_bytes,
        )
    except OverflowError as error:
        return response, f"resource-limit:{error.args[0]}"

    status = response["status"]
    worker_error_family = response.get("worker_error_family")
    if status == "WORKER_ERROR":
        if not isinstance(worker_error_family, str) or not worker_error_family:
            raise ValueError("WORKER_ERROR requires worker_error_family")
        if worker_error_family.startswith("resource-limit:"):
            return response, worker_error_family
    elif worker_error_family is not None:
        raise ValueError("non-WORKER_ERROR response carries worker_error_family")

    if status == "COMPLETED":
        if response.get("exit_code") != 0:
            raise ValueError("COMPLETED response requires exit_code=0")
        diagnostic_code = response.get("diagnostic_code")
        diagnostic_family = response.get("diagnostic_family")
        if diagnostic_code is not None or diagnostic_family is not None:
            raise ValueError("COMPLETED response must not carry diagnostic")
    elif status == "REJECTED":
        if not isinstance(response.get("diagnostic_code"), str):
            raise ValueError("REJECTED response requires diagnostic_code")
        if not isinstance(response.get("diagnostic_family"), str):
            raise ValueError("REJECTED response requires diagnostic_family")

    result_sha = response.get("result_sha256")
    if result_sha is not None and (
        not isinstance(result_sha, str)
        or len(result_sha) != 64
        or any(ch not in "0123456789abcdef" for ch in result_sha)
    ):
        raise ValueError("invalid result_sha256")

    return response, None


def run_isolated_worker(
    request: Mapping[str, object],
    *,
    worker_argv: Sequence[str] | None = None,
    timeout_ms: int | None = None,
    cwd: Path | str | None = None,
    env_overrides: Mapping[str, str] | None = None,
) -> IsolatedRunResult:
    """Run one request in one fresh killable child process.

    ``worker_argv`` and ``timeout_ms`` are explicit test/integration seams. The
    request schema itself never accepts arbitrary commands or timeout weakening.
    """

    _require_request_shape(request)
    budget_ms = _timeout_budget_ms(request) if timeout_ms is None else timeout_ms
    if isinstance(budget_ms, bool) or not isinstance(budget_ms, int) or budget_ms <= 0:
        raise ValueError("timeout_ms must be a positive integer")

    argv = tuple(worker_argv) if worker_argv is not None else _default_worker_argv()
    if not argv or any(not isinstance(item, str) or not item for item in argv):
        raise ValueError("worker_argv must contain non-empty strings")

    environment = os.environ.copy()
    environment.update({"PYTHONHASHSEED": "0", "PYTHONUTF8": "1"})
    if env_overrides:
        environment.update(env_overrides)

    creationflags = 0
    popen_kwargs: dict[str, object] = {}
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen(
        argv,
        cwd=str(_REPO_ROOT if cwd is None else cwd),
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creationflags,
        **popen_kwargs,
    )
    assert process.stdin is not None
    assert process.stdout is not None
    assert process.stderr is not None

    stdout_reader = _BoundedReader(process.stdout, _PROTOCOL_STDOUT_MAX_BYTES)
    stderr_reader = _BoundedReader(process.stderr, _PROTOCOL_STDERR_MAX_BYTES)
    stdout_thread = threading.Thread(target=stdout_reader.run, daemon=True)
    stderr_thread = threading.Thread(target=stderr_reader.run, daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    request_bytes = canonical_json_document(dict(request))
    write_error: Exception | None = None
    try:
        process.stdin.write(request_bytes)
        process.stdin.flush()
    except (BrokenPipeError, OSError) as error:
        write_error = error
    finally:
        try:
            process.stdin.close()
        except OSError:
            pass

    deadline = time.monotonic() + budget_ms / 1000.0
    termination: str | None = None
    while process.poll() is None:
        if stdout_reader.overflow.is_set():
            termination = "worker-protocol-stdout"
            break
        if stderr_reader.overflow.is_set():
            termination = "worker-process-stderr"
            break
        if time.monotonic() >= deadline:
            termination = "timeout"
            break
        time.sleep(0.005)

    if termination is not None:
        reaped = _kill_process_tree(process, DEFAULT_RESOURCE_POLICY.kill_grace_ms)
    else:
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            reaped = _kill_process_tree(process, DEFAULT_RESOURCE_POLICY.kill_grace_ms)
            termination = "post-exit-wait"
        else:
            reaped = process.poll() is not None

    # A descendant can keep inherited pipes open even after the direct worker
    # exits. Such a tree violates the one-case process boundary, so terminate it.
    stdout_thread.join(timeout=0.5)
    stderr_thread.join(timeout=0.5)
    if (stdout_thread.is_alive() or stderr_thread.is_alive()) and termination is None:
        reaped = _kill_process_tree(process, DEFAULT_RESOURCE_POLICY.kill_grace_ms)
        termination = "orphaned-pipe"
        stdout_thread.join(timeout=1.0)
        stderr_thread.join(timeout=1.0)

    if termination != "timeout":
        if stdout_reader.overflow.is_set():
            termination = "worker-protocol-stdout"
        elif stderr_reader.overflow.is_set():
            termination = "worker-process-stderr"

    if termination == "timeout":
        signature = (
            f"timeout:{request['operation']}:{request['backend']}:"
            f"{request['optimization']}:{budget_ms}"
        )
        return _result(
            status="TIMEOUT",
            failure_signature=signature,
            response=None,
            process=process,
            reaped=reaped,
            stdout_reader=stdout_reader,
            stderr_reader=stderr_reader,
        )

    if termination in {"worker-protocol-stdout", "worker-process-stderr"}:
        return _result(
            status="RESOURCE_LIMIT",
            failure_signature=f"resource-limit:{termination}",
            response=None,
            process=process,
            reaped=reaped,
            stdout_reader=stdout_reader,
            stderr_reader=stderr_reader,
        )

    if termination is not None:
        return _result(
            status="HARNESS_ERROR",
            failure_signature=f"harness-error:process-boundary:{termination}",
            response=None,
            process=process,
            reaped=reaped,
            stdout_reader=stdout_reader,
            stderr_reader=stderr_reader,
        )

    return_code = process.poll()
    if return_code != 0:
        return _result(
            status="CRASH",
            failure_signature=_crash_signature(request.get("operation"), return_code),
            response=None,
            process=process,
            reaped=reaped,
            stdout_reader=stdout_reader,
            stderr_reader=stderr_reader,
        )

    if write_error is not None:
        return _result(
            status="HARNESS_ERROR",
            failure_signature=(
                f"harness-error:request-write:{type(write_error).__name__}"
            ),
            response=None,
            process=process,
            reaped=reaped,
            stdout_reader=stdout_reader,
            stderr_reader=stderr_reader,
        )

    try:
        response, resource_failure = _validate_response(request, stdout_reader.data)
    except (ValueError, TypeError) as error:
        return _result(
            status="HARNESS_ERROR",
            failure_signature=f"harness-error:response:{type(error).__name__}",
            response=None,
            process=process,
            reaped=reaped,
            stdout_reader=stdout_reader,
            stderr_reader=stderr_reader,
        )

    if resource_failure is not None:
        return _result(
            status="RESOURCE_LIMIT",
            failure_signature=resource_failure,
            response=response,
            process=process,
            reaped=reaped,
            stdout_reader=stdout_reader,
            stderr_reader=stderr_reader,
        )

    if response["status"] == "WORKER_ERROR":
        return _result(
            status="HARNESS_ERROR",
            failure_signature=(
                f"harness-error:worker:{response['worker_error_family']}"
            ),
            response=response,
            process=process,
            reaped=reaped,
            stdout_reader=stdout_reader,
            stderr_reader=stderr_reader,
        )

    return _result(
        status="RESPONSE",
        failure_signature=None,
        response=response,
        process=process,
        reaped=reaped,
        stdout_reader=stdout_reader,
        stderr_reader=stderr_reader,
    )
