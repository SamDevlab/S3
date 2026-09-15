"""Single-request Reliability Lab v2 worker process.

The worker performs compiler work only inside a disposable child process. It
never decides TIMEOUT: the parent watchdog owns deadlines and process-tree kill
semantics.
"""

from __future__ import annotations

import base64
import contextlib
import io
import json
import sys
from typing import Any

from bootstrap.s3.diagnostics import S3Error, diagnostic_from_exception
from bootstrap.s3.pipeline import compile_source, run_source
from tools.reliability_contract_v2 import (
    DEFAULT_RESOURCE_POLICY,
    WORKER_REQUEST_SCHEMA,
    WORKER_RESPONSE_SCHEMA,
    canonical_json_document,
    canonical_json_payload,
    decode_and_verify_source,
    sha256_hex,
)

_REQUEST_MAX_BYTES = 262_144
_ZERO_CASE_ID = "0" * 64
_ALLOWED_REQUEST_KEYS = {
    "schema",
    "case_id",
    "compiler_head",
    "source_b64",
    "source_sha256",
    "source_bytes",
    "operation",
    "optimization",
    "backend",
    "options",
}
_ALLOWED_OPTIONS = {"entry", "max_frames", "max_instructions"}


class WorkerProtocolError(ValueError):
    """Raised when the parent-to-worker request violates the frozen protocol."""


class _CaptureLimitExceeded(RuntimeError):
    def __init__(self, stream_name: str) -> None:
        self.stream_name = stream_name
        super().__init__(f"{stream_name} output exceeds frozen byte limit")


class _BoundedTextCapture(io.TextIOBase):
    def __init__(self, stream_name: str, limit: int) -> None:
        super().__init__()
        self._stream_name = stream_name
        self._limit = limit
        self._data = bytearray()

    @property
    def encoding(self) -> str:
        return "utf-8"

    def writable(self) -> bool:
        return True

    def write(self, text: str) -> int:
        if not isinstance(text, str):
            raise TypeError("text capture accepts str only")
        encoded = text.encode("utf-8")
        if len(self._data) + len(encoded) > self._limit:
            raise _CaptureLimitExceeded(self._stream_name)
        self._data.extend(encoded)
        return len(text)

    def flush(self) -> None:
        return None

    @property
    def data(self) -> bytes:
        return bytes(self._data)


def _worker_response(
    *,
    case_id: str,
    operation: str,
    status: str,
    exit_code: int | None = None,
    signal: str | None = None,
    result_sha256: str | None = None,
    diagnostic_code: str | None = None,
    diagnostic_family: str | None = None,
    stdout: bytes = b"",
    stderr: bytes = b"",
    worker_error_family: str | None = None,
) -> dict[str, object]:
    return {
        "schema": WORKER_RESPONSE_SCHEMA,
        "case_id": case_id,
        "status": status,
        "operation": operation,
        "exit_code": exit_code,
        "signal": signal,
        "result_sha256": result_sha256,
        "diagnostic_code": diagnostic_code,
        "diagnostic_family": diagnostic_family,
        "stdout_b64": base64.b64encode(stdout).decode("ascii"),
        "stderr_b64": base64.b64encode(stderr).decode("ascii"),
        "worker_error_family": worker_error_family,
    }


def _read_request() -> dict[str, object]:
    raw = sys.stdin.buffer.read(_REQUEST_MAX_BYTES + 1)
    if len(raw) > _REQUEST_MAX_BYTES:
        raise WorkerProtocolError("request exceeds worker protocol byte limit")
    if not raw:
        raise WorkerProtocolError("request is empty")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise WorkerProtocolError("request is not UTF-8") from error
    try:
        value = json.loads(decoded)
    except json.JSONDecodeError as error:
        raise WorkerProtocolError("request is not valid JSON") from error
    if not isinstance(value, dict):
        raise WorkerProtocolError("request root must be an object")
    return value


def _require_string(request: dict[str, object], name: str) -> str:
    value = request.get(name)
    if not isinstance(value, str) or not value:
        raise WorkerProtocolError(f"{name} must be a non-empty string")
    return value


def _require_int(request: dict[str, object], name: str) -> int:
    value = request.get(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise WorkerProtocolError(f"{name} must be an integer")
    return value


def _validate_request(request: dict[str, object]) -> dict[str, object]:
    if set(request) != _ALLOWED_REQUEST_KEYS:
        raise WorkerProtocolError("request keys do not match frozen protocol")
    if request.get("schema") != WORKER_REQUEST_SCHEMA:
        raise WorkerProtocolError("unsupported worker request schema")

    case_id = _require_string(request, "case_id")
    compiler_head = _require_string(request, "compiler_head")
    source_b64 = _require_string(request, "source_b64")
    source_sha256 = _require_string(request, "source_sha256")
    source_bytes = _require_int(request, "source_bytes")
    operation = _require_string(request, "operation")
    optimization = _require_string(request, "optimization")
    backend = _require_string(request, "backend")

    if len(case_id) != 64 or any(ch not in "0123456789abcdef" for ch in case_id):
        raise WorkerProtocolError("case_id must be lowercase SHA-256 hex")
    if len(compiler_head) != 40 or any(ch not in "0123456789abcdef" for ch in compiler_head):
        raise WorkerProtocolError("compiler_head must be lowercase 40-hex commit id")
    if operation not in {"CHECK", "RUN_HOSTED", "RUN_NATIVE"}:
        raise WorkerProtocolError("unknown worker operation")
    if optimization not in {"O0", "O1"}:
        raise WorkerProtocolError("unknown optimization")
    if backend not in {"hosted", "linux-x86_64-native"}:
        raise WorkerProtocolError("unknown backend")
    if operation in {"CHECK", "RUN_HOSTED"} and backend != "hosted":
        raise WorkerProtocolError("hosted operation requires hosted backend")
    if operation == "RUN_NATIVE" and backend != "linux-x86_64-native":
        raise WorkerProtocolError("RUN_NATIVE requires linux-x86_64-native backend")

    options = request.get("options")
    if not isinstance(options, dict):
        raise WorkerProtocolError("options must be an object")
    if any(not isinstance(key, str) for key in options):
        raise WorkerProtocolError("option names must be strings")
    unknown_options = set(options) - _ALLOWED_OPTIONS
    if unknown_options:
        raise WorkerProtocolError(
            "unsupported worker option(s): " + ",".join(sorted(unknown_options))
        )

    entry = options.get("entry", "main")
    max_frames = options.get("max_frames")
    max_instructions = options.get("max_instructions")
    if not isinstance(entry, str) or not entry or len(entry) > 128:
        raise WorkerProtocolError("entry must be a non-empty string <= 128 characters")
    for name, value in (
        ("max_frames", max_frames),
        ("max_instructions", max_instructions),
    ):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
        ):
            raise WorkerProtocolError(f"{name} must be a positive integer")

    source = decode_and_verify_source(source_b64, source_sha256, source_bytes)
    try:
        source_text = source.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise WorkerProtocolError("source bytes are not valid UTF-8") from error

    return {
        "case_id": case_id,
        "compiler_head": compiler_head,
        "source_sha256": source_sha256,
        "source_text": source_text,
        "operation": operation,
        "optimization": optimization,
        "backend": backend,
        "entry": entry,
        "max_frames": max_frames,
        "max_instructions": max_instructions,
    }


def _run_compiler(validated: dict[str, object]) -> dict[str, object]:
    case_id = str(validated["case_id"])
    operation = str(validated["operation"])
    optimization = str(validated["optimization"])
    source_text = str(validated["source_text"])
    entry = str(validated["entry"])
    max_frames = validated["max_frames"]
    max_instructions = validated["max_instructions"]

    stdout_capture = _BoundedTextCapture(
        "stdout", DEFAULT_RESOURCE_POLICY.stdout_max_bytes
    )
    stderr_capture = _BoundedTextCapture(
        "stderr", DEFAULT_RESOURCE_POLICY.stderr_max_bytes
    )

    if operation == "RUN_NATIVE":
        return _worker_response(
            case_id=case_id,
            operation=operation,
            status="WORKER_ERROR",
            worker_error_family="operation-not-implemented-r1:RUN_NATIVE",
        )

    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(
            stderr_capture
        ):
            if operation == "CHECK":
                compile_source(source_text, optimization=optimization)
                result_sha = None
            else:
                kwargs: dict[str, Any] = {
                    "entry": entry,
                    "optimization": optimization,
                }
                if max_frames is not None:
                    kwargs["max_frames"] = max_frames
                if max_instructions is not None:
                    kwargs["max_instructions"] = max_instructions
                value = run_source(source_text, **kwargs)
                result_sha = sha256_hex(canonical_json_payload({"value": value}))
    except _CaptureLimitExceeded as error:
        return _worker_response(
            case_id=case_id,
            operation=operation,
            status="WORKER_ERROR",
            stdout=stdout_capture.data,
            stderr=stderr_capture.data,
            worker_error_family=f"resource-limit:{error.stream_name}_max_bytes",
        )
    except S3Error as error:
        diagnostic = diagnostic_from_exception(error)
        return _worker_response(
            case_id=case_id,
            operation=operation,
            status="REJECTED",
            diagnostic_code=diagnostic.code.value,
            diagnostic_family=(
                f"{diagnostic.phase.value}:{diagnostic.category.value}"
            ),
            stdout=stdout_capture.data,
            stderr=stderr_capture.data,
        )

    return _worker_response(
        case_id=case_id,
        operation=operation,
        status="COMPLETED",
        exit_code=0,
        result_sha256=result_sha,
        stdout=stdout_capture.data,
        stderr=stderr_capture.data,
    )


def _protocol_error_response(
    error: Exception,
    request: dict[str, object] | None,
) -> dict[str, object]:
    raw_case_id = None if request is None else request.get("case_id")
    case_id = (
        raw_case_id
        if isinstance(raw_case_id, str)
        and len(raw_case_id) == 64
        and all(ch in "0123456789abcdef" for ch in raw_case_id)
        else _ZERO_CASE_ID
    )
    raw_operation = None if request is None else request.get("operation")
    operation = (
        raw_operation
        if raw_operation in {"CHECK", "RUN_HOSTED", "RUN_NATIVE"}
        else "CHECK"
    )
    return _worker_response(
        case_id=case_id,
        operation=str(operation),
        status="WORKER_ERROR",
        worker_error_family=f"protocol:{type(error).__name__}",
    )


def main() -> int:
    request: dict[str, object] | None = None
    try:
        request = _read_request()
        validated = _validate_request(request)
    except (WorkerProtocolError, ValueError, TypeError) as error:
        response = _protocol_error_response(error, request)
    else:
        # Unexpected compiler exceptions intentionally escape this function. The
        # parent then observes a non-zero worker exit and classifies CRASH.
        response = _run_compiler(validated)

    sys.stdout.buffer.write(canonical_json_document(response))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
