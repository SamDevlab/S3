from __future__ import annotations

from types import SimpleNamespace

import pytest

from bootstrap.s3.backends.x86_64 import NativePlatformError
from tools import reliability_worker_r3 as worker
from tools.reliability_contract_v2 import canonical_json_payload, sha256_hex


pytestmark = [pytest.mark.s3_contract, pytest.mark.s3_native]


def _validated() -> dict[str, object]:
    return {
        "case_id": "a" * 64,
        "compiler_head": "b" * 40,
        "source_sha256": "c" * 64,
        "source_text": "fn main() -> tryte:\n    return 23\n",
        "operation": "RUN_NATIVE",
        "optimization": "O1",
        "backend": "linux-x86_64-native",
        "entry": "main",
        "max_frames": None,
        "max_instructions": None,
    }


class _Compilation:
    def require_ordinary_artifacts(self):
        return object(), object()


def _install_success_path(monkeypatch, *, stdout="program returned: 23\n", stderr="", returncode=0):
    monkeypatch.setattr(worker, "compile_source", lambda source, optimization: _Compilation())
    monkeypatch.setattr(worker, "generate_native_assembly", lambda assembly, **kwargs: "native assembly")

    class FakeToolchain:
        @classmethod
        def detect(cls):
            return cls()

        def build(self, assembly, output):
            assert assembly == "native assembly"
            return output

        def run(self, executable, timeout):
            assert timeout == 30.0
            return SimpleNamespace(
                stdout=stdout,
                stderr=stderr,
                returncode=returncode,
            )

    monkeypatch.setattr(worker, "NativeToolchain", FakeToolchain)


def test_r3_native_worker_hashes_same_canonical_scalar_as_hosted(monkeypatch) -> None:
    _install_success_path(monkeypatch)
    response = worker._run_native(_validated())

    assert response["status"] == "COMPLETED"
    assert response["exit_code"] == 0
    assert response["worker_error_family"] is None
    assert response["result_sha256"] == sha256_hex(
        canonical_json_payload({"value": 23})
    )


def test_r3_native_worker_rejects_unexpected_runtime_output(monkeypatch) -> None:
    _install_success_path(monkeypatch, stdout="23\n")
    response = worker._run_native(_validated())

    assert response["status"] == "WORKER_ERROR"
    assert response["worker_error_family"] == "native-runtime:unexpected-output"


def test_r3_native_worker_preserves_nonzero_runtime_exit(monkeypatch) -> None:
    _install_success_path(
        monkeypatch,
        stdout="",
        stderr="runtime failure\n",
        returncode=17,
    )
    response = worker._run_native(_validated())

    assert response["status"] == "WORKER_ERROR"
    assert response["worker_error_family"] == "native-runtime:exit-17"


def test_r3_native_worker_fails_closed_when_native_host_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(worker, "compile_source", lambda source, optimization: _Compilation())
    monkeypatch.setattr(worker, "generate_native_assembly", lambda assembly, **kwargs: "native assembly")

    class UnavailableToolchain:
        @classmethod
        def detect(cls):
            raise NativePlatformError("native build requires Linux x86-64")

    monkeypatch.setattr(worker, "NativeToolchain", UnavailableToolchain)
    response = worker._run_native(_validated())

    assert response["status"] == "WORKER_ERROR"
    assert str(response["worker_error_family"]).startswith("native-environment:")


def test_r3_native_worker_forwards_frozen_execution_limits(monkeypatch) -> None:
    observed: dict[str, object] = {}
    monkeypatch.setattr(worker, "compile_source", lambda source, optimization: _Compilation())

    def render(assembly, **kwargs):
        observed.update(kwargs)
        return "native assembly"

    monkeypatch.setattr(worker, "generate_native_assembly", render)

    class FakeToolchain:
        @classmethod
        def detect(cls):
            return cls()

        def build(self, assembly, output):
            return output

        def run(self, executable, timeout):
            return SimpleNamespace(
                stdout="program returned: 23\n",
                stderr="",
                returncode=0,
            )

    monkeypatch.setattr(worker, "NativeToolchain", FakeToolchain)
    validated = _validated()
    validated["max_frames"] = 11
    validated["max_instructions"] = 12345
    response = worker._run_native(validated)

    assert response["status"] == "COMPLETED"
    assert observed == {"max_frames": 11, "max_instructions": 12345}
