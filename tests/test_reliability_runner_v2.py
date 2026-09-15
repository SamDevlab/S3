from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tools.reliability_contract_v2 import (
    WORKER_REQUEST_SCHEMA,
    derive_case_seed,
    encode_source,
    make_case_id,
)
from tools.reliability_runner_v2 import run_isolated_worker


pytestmark = [pytest.mark.s3_contract]


def _request(
    source: bytes = b"fn main() -> trit:\n    return 0\n",
    *,
    operation: str = "RUN_HOSTED",
    optimization: str = "O0",
    backend: str = "hosted",
) -> dict[str, object]:
    source_b64, source_sha, source_bytes = encode_source(source)
    case_seed = derive_case_seed(
        11,
        0,
        "s3.reliability.generator.v2.0.0",
        "valid",
    )
    case_id = make_case_id(
        "r1-test",
        0,
        case_seed,
        "s3.reliability.generator.v2.0.0",
        "valid",
        source_sha,
    )
    return {
        "schema": WORKER_REQUEST_SCHEMA,
        "case_id": case_id,
        "compiler_head": "0" * 40,
        "source_b64": source_b64,
        "source_sha256": source_sha,
        "source_bytes": source_bytes,
        "operation": operation,
        "optimization": optimization,
        "backend": backend,
        "options": {},
    }


def _canonical_response_script(
    *,
    status: str = "COMPLETED",
    worker_error_family: str | None = None,
    stdout: bytes = b"",
    stderr: bytes = b"",
) -> str:
    encoded_stdout = base64.b64encode(stdout).decode("ascii")
    encoded_stderr = base64.b64encode(stderr).decode("ascii")
    return f"""
import json, sys
request = json.loads(sys.stdin.read())
response = {{
    "schema": "s3.reliability.worker-response.v1",
    "case_id": request["case_id"],
    "status": {status!r},
    "operation": request["operation"],
    "exit_code": {0 if status == 'COMPLETED' else None!r},
    "signal": None,
    "result_sha256": None,
    "diagnostic_code": {('S3E_PARSE_SYNTAX' if status == 'REJECTED' else None)!r},
    "diagnostic_family": {('parsing:syntax' if status == 'REJECTED' else None)!r},
    "stdout_b64": {encoded_stdout!r},
    "stderr_b64": {encoded_stderr!r},
    "worker_error_family": {worker_error_family!r},
}}
sys.stdout.write(json.dumps(response, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\\n")
sys.stdout.flush()
"""


def test_r1_accepts_one_canonical_worker_response(tmp_path: Path) -> None:
    result = run_isolated_worker(
        _request(),
        worker_argv=(sys.executable, "-c", _canonical_response_script()),
        timeout_ms=1000,
        cwd=tmp_path,
    )
    assert result.status == "RESPONSE"
    assert result.failure_signature is None
    assert result.reaped is True
    assert result.response is not None
    assert result.response["status"] == "COMPLETED"
    assert result.process_exit_code == 0


def test_r1_preserves_bounded_compiler_channels_in_protocol(tmp_path: Path) -> None:
    result = run_isolated_worker(
        _request(),
        worker_argv=(
            sys.executable,
            "-c",
            _canonical_response_script(stdout=b"hello\n", stderr=b"warning\n"),
        ),
        timeout_ms=1000,
        cwd=tmp_path,
    )
    assert result.status == "RESPONSE"
    assert result.response is not None
    assert base64.b64decode(result.response["stdout_b64"]) == b"hello\n"
    assert base64.b64decode(result.response["stderr_b64"]) == b"warning\n"


def test_r1_nonzero_worker_exit_is_crash(tmp_path: Path) -> None:
    script = "import sys; sys.stdin.buffer.read(); raise RuntimeError('synthetic crash')"
    result = run_isolated_worker(
        _request(),
        worker_argv=(sys.executable, "-c", script),
        timeout_ms=1000,
        cwd=tmp_path,
    )
    assert result.status == "CRASH"
    assert result.failure_signature == "crash:RUN_HOSTED:exit-1"
    assert result.reaped is True


def test_r1_malformed_protocol_is_harness_error(tmp_path: Path) -> None:
    script = "import sys; sys.stdin.buffer.read(); sys.stdout.write('{}\\n'); sys.stdout.flush()"
    result = run_isolated_worker(
        _request(),
        worker_argv=(sys.executable, "-c", script),
        timeout_ms=1000,
        cwd=tmp_path,
    )
    assert result.status == "HARNESS_ERROR"
    assert result.failure_signature == "harness-error:response:ValueError"
    assert result.reaped is True


def test_r1_hard_timeout_kills_and_reaps_hung_worker(tmp_path: Path) -> None:
    script = "import sys,time; sys.stdin.buffer.read(); time.sleep(60)"
    result = run_isolated_worker(
        _request(),
        worker_argv=(sys.executable, "-c", script),
        timeout_ms=120,
        cwd=tmp_path,
    )
    assert result.status == "TIMEOUT"
    assert result.failure_signature == "timeout:RUN_HOSTED:hosted:O0:120"
    assert result.reaped is True


def test_r1_timeout_kills_descendant_process_tree(tmp_path: Path) -> None:
    marker = tmp_path / "descendant-survived.txt"
    child = (
        "import os,pathlib,time; "
        "time.sleep(0.8); "
        "pathlib.Path(os.environ['R1_MARKER']).write_text('survived', encoding='utf-8')"
    )
    parent = f"""
import subprocess, sys, time
sys.stdin.buffer.read()
subprocess.Popen([sys.executable, "-c", {child!r}])
time.sleep(60)
"""
    result = run_isolated_worker(
        _request(),
        worker_argv=(sys.executable, "-c", parent),
        timeout_ms=120,
        cwd=tmp_path,
        env_overrides={"R1_MARKER": str(marker)},
    )
    assert result.status == "TIMEOUT"
    assert result.reaped is True
    time.sleep(1.0)
    assert not marker.exists()


def test_r1_protocol_flood_is_resource_limit(tmp_path: Path) -> None:
    script = """
import sys, time
sys.stdin.buffer.read()
sys.stdout.buffer.write(b"x" * (4 * 1024 * 1024))
sys.stdout.buffer.flush()
time.sleep(60)
"""
    result = run_isolated_worker(
        _request(),
        worker_argv=(sys.executable, "-c", script),
        timeout_ms=2000,
        cwd=tmp_path,
    )
    assert result.status == "RESOURCE_LIMIT"
    assert result.failure_signature == "resource-limit:worker-protocol-stdout"
    assert result.stdout_truncated is True
    assert result.reaped is True


def test_r1_worker_error_is_distinct_from_crash(tmp_path: Path) -> None:
    result = run_isolated_worker(
        _request(),
        worker_argv=(
            sys.executable,
            "-c",
            _canonical_response_script(
                status="WORKER_ERROR",
                worker_error_family="protocol:synthetic",
            ),
        ),
        timeout_ms=1000,
        cwd=tmp_path,
    )
    assert result.status == "HARNESS_ERROR"
    assert result.failure_signature == "harness-error:worker:protocol:synthetic"
    assert result.process_exit_code == 0


def test_r1_real_worker_executes_hosted_case() -> None:
    result = run_isolated_worker(_request(), timeout_ms=5000)
    assert result.status == "RESPONSE"
    assert result.reaped is True
    assert result.response is not None
    assert result.response["status"] == "COMPLETED"
    assert isinstance(result.response["result_sha256"], str)


def test_r1_real_worker_preserves_compiler_rejection() -> None:
    result = run_isolated_worker(
        _request(
            b"fn main() -> trit:\n    return (\n",
            operation="CHECK",
        ),
        timeout_ms=5000,
    )
    assert result.status == "RESPONSE"
    assert result.reaped is True
    assert result.response is not None
    assert result.response["status"] == "REJECTED"
    assert result.response["diagnostic_code"] == "S3E_PARSE_SYNTAX"
    assert result.response["diagnostic_family"] == "parsing:syntax"


def test_r1_native_execution_fails_closed_until_r3() -> None:
    result = run_isolated_worker(
        _request(
            operation="RUN_NATIVE",
            backend="linux-x86_64-native",
        ),
        timeout_ms=5000,
    )
    assert result.status == "HARNESS_ERROR"
    assert result.response is not None
    assert result.response["status"] == "WORKER_ERROR"
    assert result.response["worker_error_family"] == "operation-not-implemented-r1:RUN_NATIVE"
