from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.reliability_contract_v2 import canonical_json_document, sha256_hex
from tools.reliability_differential_v2 import (
    MAX_NATIVE_CASES,
    run_campaign,
    run_case,
)
from tools.reliability_generator_v2 import generate_case
from tools.reliability_runner_v2 import IsolatedRunResult


pytestmark = [pytest.mark.s3_contract, pytest.mark.s3_differential]
HEAD = "a" * 40


def _response_result(
    request: dict[str, object],
    *,
    result_sha: str | None = None,
    response_status: str = "COMPLETED",
    diagnostic_code: str | None = None,
    diagnostic_family: str | None = None,
) -> IsolatedRunResult:
    response = {
        "schema": "s3.reliability.worker-response.v1",
        "case_id": request["case_id"],
        "status": response_status,
        "operation": request["operation"],
        "exit_code": 0 if response_status == "COMPLETED" else None,
        "signal": None,
        "result_sha256": result_sha,
        "diagnostic_code": diagnostic_code,
        "diagnostic_family": diagnostic_family,
        "stdout_b64": "",
        "stderr_b64": "",
        "worker_error_family": None,
    }
    return IsolatedRunResult(
        status="RESPONSE",
        failure_signature=None,
        response=response,
        process_exit_code=0,
        reaped=True,
        stdout_sha256="0" * 64,
        stderr_sha256="0" * 64,
        stdout_bytes=0,
        stderr_bytes=0,
        stdout_truncated=False,
        stderr_truncated=False,
    )


def _terminal_result(status: str, signature: str) -> IsolatedRunResult:
    return IsolatedRunResult(
        status=status,
        failure_signature=signature,
        response=None,
        process_exit_code=None,
        reaped=True,
        stdout_sha256="0" * 64,
        stderr_sha256="0" * 64,
        stdout_bytes=0,
        stderr_bytes=0,
        stdout_truncated=False,
        stderr_truncated=False,
    )


def _hash(label: str) -> str:
    return sha256_hex(label.encode("ascii"))


def test_r3_hosted_o0_o1_equal_is_pass_without_confirmation() -> None:
    calls: list[tuple[str, str, bool]] = []

    def executor(request, native):
        calls.append((str(request["backend"]), str(request["optimization"]), native))
        return _response_result(request, result_sha=_hash("same"))

    case = generate_case("r3-pass", 1, 0, "valid")
    result = run_case(case, HEAD, native=False, executor=executor)

    assert result.outcome == "PASS"
    assert result.failure_signature is None
    assert result.confirmation_runs == 0
    assert calls == [("hosted", "O0", False), ("hosted", "O1", False)]


def test_r3_stable_hosted_mismatch_is_miscompile_and_emits_replay(tmp_path: Path) -> None:
    calls: list[tuple[str, str]] = []

    def executor(request, native):
        assert native is False
        key = (str(request["backend"]), str(request["optimization"]))
        calls.append(key)
        result_sha = _hash("o0") if key[1] == "O0" else _hash("o1")
        return _response_result(request, result_sha=result_sha)

    case = generate_case("r3-miscompile", 2, 0, "valid")
    result = run_case(
        case,
        HEAD,
        native=False,
        replay_root=tmp_path,
        executor=executor,
    )

    assert result.outcome == "MISCOMPILE"
    assert result.failure_signature is not None
    assert result.failure_signature.startswith("miscompile:")
    assert result.confirmation_runs == 4
    assert len(calls) == 6  # initial O0/O1 + two confirmations for each path
    assert result.replay_path == case.case_id

    bundle = tmp_path / case.case_id
    assert (bundle / "input.s3").read_bytes() == case.source
    metadata_bytes = (bundle / "metadata.json").read_bytes()
    result_bytes = (bundle / "result.json").read_bytes()
    replay_bytes = (bundle / "replay.json").read_bytes()
    assert metadata_bytes == canonical_json_document(json.loads(metadata_bytes))
    assert result_bytes == canonical_json_document(json.loads(result_bytes))
    assert replay_bytes == canonical_json_document(json.loads(replay_bytes))
    replay = json.loads(replay_bytes)
    assert replay["source_sha256"] == case.source_sha256
    assert replay["metadata_sha256"] == sha256_hex(metadata_bytes)
    assert replay["result_sha256"] == sha256_hex(result_bytes)
    assert replay["expected_failure_signature"] == result.failure_signature


def test_r3_changing_confirmation_becomes_nondeterminism() -> None:
    counts: dict[str, int] = {"O0": 0, "O1": 0}

    def executor(request, native):
        assert native is False
        optimization = str(request["optimization"])
        counts[optimization] += 1
        if optimization == "O0":
            value = "o0-first" if counts[optimization] == 1 else "o0-changed"
        else:
            value = "o1"
        return _response_result(request, result_sha=_hash(value))

    case = generate_case("r3-nondeterminism", 3, 0, "valid")
    result = run_case(case, HEAD, native=False, executor=executor)

    assert result.outcome == "NONDETERMINISM"
    assert result.failure_signature == "nondeterminism:differential-matrix"
    assert result.confirmation_runs == 4


def test_r3_stable_timeout_preserves_timeout_class() -> None:
    calls = 0

    def executor(request, native):
        nonlocal calls
        calls += 1
        if request["optimization"] == "O0":
            return _terminal_result(
                "TIMEOUT",
                "timeout:RUN_HOSTED:hosted:O0:5000",
            )
        return _response_result(request, result_sha=_hash("unused"))

    case = generate_case("r3-timeout", 4, 0, "valid")
    result = run_case(case, HEAD, native=False, executor=executor)

    assert result.outcome == "TIMEOUT"
    assert result.failure_signature == "timeout:RUN_HOSTED:hosted:O0:5000"
    assert result.confirmation_runs == 2
    # Both initial paths are observed before classification, then only O0 repeats.
    assert calls == 4


def test_r3_rejected_valid_case_is_unexpected_rejection() -> None:
    def executor(request, native):
        if request["optimization"] == "O0":
            return _response_result(
                request,
                response_status="REJECTED",
                diagnostic_code="S3E_PARSE_SYNTAX",
                diagnostic_family="parsing:syntax",
            )
        return _response_result(request, result_sha=_hash("unused"))

    case = generate_case("r3-rejection", 5, 0, "valid")
    result = run_case(case, HEAD, native=False, executor=executor)

    assert result.outcome == "UNEXPECTED_REJECTION"
    assert result.failure_signature == "unexpected-rejection:hosted:O0"


def test_r3_native_shard_executes_four_paths_and_compares_same_value() -> None:
    calls: list[tuple[str, str, bool]] = []

    def executor(request, native):
        calls.append((str(request["backend"]), str(request["optimization"]), native))
        return _response_result(request, result_sha=_hash("same-value"))

    case = generate_case("r3-native-pass", 6, 0, "valid")
    result = run_case(case, HEAD, native=True, executor=executor)

    assert result.outcome == "PASS"
    assert result.native_selected is True
    assert calls == [
        ("hosted", "O0", False),
        ("hosted", "O1", False),
        ("linux-x86_64-native", "O0", True),
        ("linux-x86_64-native", "O1", True),
    ]


def test_r3_stable_native_mismatch_is_miscompile() -> None:
    def executor(request, native):
        if native and request["optimization"] == "O1":
            return _response_result(request, result_sha=_hash("native-o1-bad"))
        return _response_result(request, result_sha=_hash("expected"))

    case = generate_case("r3-native-miscompile", 7, 0, "valid")
    result = run_case(case, HEAD, native=True, executor=executor)

    assert result.outcome == "MISCOMPILE"
    assert result.confirmation_runs == 8
    assert result.failure_signature is not None


def test_r3_native_case_count_is_bounded_fail_closed() -> None:
    with pytest.raises(ValueError, match="bounded R3 native shard"):
        run_campaign(
            "r3-too-wide",
            8,
            HEAD,
            case_count=MAX_NATIVE_CASES + 1,
            native_case_count=MAX_NATIVE_CASES + 1,
            executor=lambda request, native: _response_result(
                request, result_sha=_hash("unused")
            ),
        )


def test_r3_campaign_selects_first_n_native_cases_deterministically() -> None:
    seen_native_case_ids: list[str] = []

    def executor(request, native):
        if native:
            case_id = str(request["case_id"])
            if case_id not in seen_native_case_ids:
                seen_native_case_ids.append(case_id)
        return _response_result(request, result_sha=_hash("same"))

    report = run_campaign(
        "r3-campaign",
        9,
        HEAD,
        case_count=5,
        native_case_count=2,
        executor=executor,
    )

    expected = [
        generate_case("r3-campaign", 9, index, "valid").case_id
        for index in range(2)
    ]
    assert seen_native_case_ids == expected
    assert report["counts"] == {"PASS": 5}
    assert report["native_case_count"] == 2
    assert list(report["counts"]) == sorted(report["counts"])
