"""R3 Reliability Lab worker extension with bounded Linux x86-64 execution.

The frozen R0 request/response protocol is unchanged. Hosted operations remain
owned by ``reliability_worker_v2``; this module only replaces the previously
fail-closed RUN_NATIVE implementation. The R1 parent watchdog still owns the
outer wall deadline and process-tree termination.
"""

from __future__ import annotations

import contextlib
import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativePlatformError,
    NativeToolchain,
    NativeToolchainError,
    generate_native_assembly,
)
from bootstrap.s3.diagnostics import S3Error, diagnostic_from_exception
from bootstrap.s3.pipeline import compile_source
from tools import reliability_worker_v2 as r1
from tools.reliability_contract_v2 import (
    DEFAULT_RESOURCE_POLICY,
    canonical_json_document,
    canonical_json_payload,
    sha256_hex,
)

_NATIVE_RESULT = re.compile(r"program returned: (-?\d+)\n\Z")


def _native_error_response(
    *,
    case_id: str,
    operation: str,
    family: str,
    stdout: bytes = b"",
    stderr: bytes = b"",
) -> dict[str, object]:
    return r1._worker_response(
        case_id=case_id,
        operation=operation,
        status="WORKER_ERROR",
        stdout=stdout,
        stderr=stderr,
        worker_error_family=family,
    )


def _run_native(validated: dict[str, object]) -> dict[str, object]:
    case_id = str(validated["case_id"])
    operation = "RUN_NATIVE"
    optimization = str(validated["optimization"])
    source_text = str(validated["source_text"])
    max_frames = validated["max_frames"]
    max_instructions = validated["max_instructions"]

    stdout_capture = r1._BoundedTextCapture(
        "stdout", DEFAULT_RESOURCE_POLICY.stdout_max_bytes
    )
    stderr_capture = r1._BoundedTextCapture(
        "stderr", DEFAULT_RESOURCE_POLICY.stderr_max_bytes
    )

    try:
        with contextlib.redirect_stdout(stdout_capture), contextlib.redirect_stderr(
            stderr_capture
        ):
            compilation = compile_source(source_text, optimization=optimization)
            _, assembly = compilation.require_ordinary_artifacts()
            kwargs: dict[str, int] = {}
            if max_frames is not None:
                kwargs["max_frames"] = int(max_frames)
            if max_instructions is not None:
                kwargs["max_instructions"] = int(max_instructions)
            native_assembly = generate_native_assembly(assembly, **kwargs)
            toolchain = NativeToolchain.detect()
            with TemporaryDirectory(prefix="s3-reliability-native-") as temporary:
                executable = toolchain.build(
                    native_assembly,
                    Path(temporary) / "case",
                )
                # The parent watchdog is stricter (20s by the frozen R0 policy)
                # and can kill this worker plus descendants. This inner timeout
                # prevents an unbounded direct call when the worker is used alone.
                completed = toolchain.run(executable, timeout=30.0)
    except r1._CaptureLimitExceeded as error:
        return _native_error_response(
            case_id=case_id,
            operation=operation,
            family=f"resource-limit:{error.stream_name}_max_bytes",
            stdout=stdout_capture.data,
            stderr=stderr_capture.data,
        )
    except NativePlatformError as error:
        diagnostic = diagnostic_from_exception(error)
        return _native_error_response(
            case_id=case_id,
            operation=operation,
            family=f"native-environment:{diagnostic.code.value}",
            stdout=stdout_capture.data,
            stderr=stderr_capture.data,
        )
    except NativeToolchainError as error:
        diagnostic = diagnostic_from_exception(error)
        return _native_error_response(
            case_id=case_id,
            operation=operation,
            family=f"native-toolchain:{diagnostic.code.value}",
            stdout=stdout_capture.data,
            stderr=stderr_capture.data,
        )
    except NativeBackendError as error:
        diagnostic = diagnostic_from_exception(error)
        return _native_error_response(
            case_id=case_id,
            operation=operation,
            family=f"native-backend:{diagnostic.code.value}",
            stdout=stdout_capture.data,
            stderr=stderr_capture.data,
        )
    except S3Error as error:
        diagnostic = diagnostic_from_exception(error)
        return r1._worker_response(
            case_id=case_id,
            operation=operation,
            status="REJECTED",
            diagnostic_code=diagnostic.code.value,
            diagnostic_family=f"{diagnostic.phase.value}:{diagnostic.category.value}",
            stdout=stdout_capture.data,
            stderr=stderr_capture.data,
        )

    native_stdout = completed.stdout.encode("utf-8")
    native_stderr = completed.stderr.encode("utf-8")
    if len(native_stdout) > DEFAULT_RESOURCE_POLICY.stdout_max_bytes:
        return _native_error_response(
            case_id=case_id,
            operation=operation,
            family="resource-limit:stdout_max_bytes",
        )
    if len(native_stderr) > DEFAULT_RESOURCE_POLICY.stderr_max_bytes:
        return _native_error_response(
            case_id=case_id,
            operation=operation,
            family="resource-limit:stderr_max_bytes",
        )
    if completed.returncode != 0:
        return _native_error_response(
            case_id=case_id,
            operation=operation,
            family=f"native-runtime:exit-{completed.returncode}",
            stdout=native_stdout,
            stderr=native_stderr,
        )
    match = _NATIVE_RESULT.fullmatch(completed.stdout)
    if match is None:
        return _native_error_response(
            case_id=case_id,
            operation=operation,
            family="native-runtime:unexpected-output",
            stdout=native_stdout,
            stderr=native_stderr,
        )
    value = int(match.group(1))
    result_sha = sha256_hex(canonical_json_payload({"value": value}))
    return r1._worker_response(
        case_id=case_id,
        operation=operation,
        status="COMPLETED",
        exit_code=0,
        result_sha256=result_sha,
        stdout=native_stdout,
        stderr=native_stderr,
    )


def _run_compiler(validated: dict[str, object]) -> dict[str, object]:
    if validated.get("operation") == "RUN_NATIVE":
        return _run_native(validated)
    return r1._run_compiler(validated)


def main() -> int:
    request: dict[str, object] | None = None
    try:
        request = r1._read_request()
        validated = r1._validate_request(request)
    except (r1.WorkerProtocolError, ValueError, TypeError) as error:
        response = r1._protocol_error_response(error, request)
    else:
        # Unexpected compiler/runtime exceptions intentionally escape. R1 parent
        # classification then records a child CRASH rather than hiding it.
        response = _run_compiler(validated)

    sys.stdout.buffer.write(canonical_json_document(response))
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
