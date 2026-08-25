from __future__ import annotations

from pathlib import Path

import tools.qualify_stage1_codegen_ir_v2_full_chain as full


def _call_guard(pass_gate: bool = True) -> dict[str, object]:
    return {
        "status": (
            "PASS_STATIC_CALL_ARGUMENT_MODEL"
            if pass_gate
            else "ROUTE_CALL_ARGUMENT_CAPACITY_BEFORE_PARAMETER_NATIVE"
        ),
        "canonical": {
            "model": {
                "total_call_arguments": 736,
                "calls": 656,
                "call_argument_headroom": 10,
            }
        },
        "parameter_candidate": {
            "safe_under_current_call_and_argument_capacities": pass_gate,
            "model": {
                "total_call_arguments": 737 if pass_gate else 747,
                "calls": 657,
                "call_argument_headroom": 9 if pass_gate else -1,
            },
        },
        "next": (
            "CONTINUE_PREPARED_NATIVE_CANDIDATE_CHAIN"
            if pass_gate
            else "EXTEND_CALL_ARGUMENT_POOL_FROM_EXACT_PARAMETER_CANDIDATE_REQUIREMENT"
        ),
    }


def _base(*, local_allowed: bool, local_next: str) -> dict[str, object]:
    return {
        "chain_status": "PASS_THROUGH_PARAMETER_CANDIDATE",
        "local_candidate_preflight": {
            "status": (
                "PASS_STATIC_LOCAL_CANDIDATE_NATIVE_QUALIFICATION_REQUIRED"
                if local_allowed
                else "ROUTE_PACKED_730_BLOCK_CAPACITY_BEFORE_LOCAL_METADATA"
            ),
            "native_qualification_allowed": local_allowed,
            "next": local_next,
        },
    }


def _local_pass() -> dict[str, object]:
    return {
        "qualification": {
            "local_ir_v2_candidate": "PASS_NATIVE_CANDIDATE",
            "next": "UNIFIED_VALUE_NAMESPACE_CANDIDATE_PREFLIGHT",
        },
        "call_argument_preflight": {
            "local_candidate": {
                "model": {
                    "total_call_arguments": 739,
                    "call_argument_headroom": 7,
                }
            }
        },
    }


def _prepare_guards(monkeypatch) -> None:
    monkeypatch.setattr(
        full,
        "_run_guard_tests",
        lambda: {"status": "PASS", "returncode": 0, "files": []},
    )
    monkeypatch.setattr(full, "audit_call_arguments", lambda **_: _call_guard(True))
    monkeypatch.setattr(full, "_load_closure", lambda _: {})


def test_guard_test_failure_stops_before_base_native_chain(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        full,
        "_run_guard_tests",
        lambda: {"status": "FAIL", "returncode": 1, "files": []},
    )

    def unexpected_base(**_):
        raise AssertionError("base native chain must not run after guard-test failure")

    monkeypatch.setattr(full.base_chain, "run_chain", unexpected_base)
    result = full.run_full_chain(full_report_path=tmp_path / "full.json")
    assert result["status"] == "BLOCKED_AT_IR_V2_GUARD_TESTS"
    assert result["canonical_source_mutated"] is False


def test_call_argument_failure_stops_before_base_native_chain(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        full,
        "_run_guard_tests",
        lambda: {"status": "PASS", "returncode": 0, "files": []},
    )
    monkeypatch.setattr(full, "audit_call_arguments", lambda **_: _call_guard(False))
    monkeypatch.setattr(full, "_load_closure", lambda _: {})

    def unexpected_base(**_):
        raise AssertionError("base native chain must not run after call-argument guard failure")

    monkeypatch.setattr(full.base_chain, "run_chain", unexpected_base)
    result = full.run_full_chain(full_report_path=tmp_path / "full.json")
    assert result["status"] == "BLOCKED_AT_PARAMETER_CALL_ARGUMENT_PREFLIGHT"
    assert result["next"] == "EXTEND_CALL_ARGUMENT_POOL_FROM_EXACT_PARAMETER_CANDIDATE_REQUIREMENT"


def test_call_argument_preflight_error_is_preserved_in_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        full,
        "_run_guard_tests",
        lambda: {"status": "PASS", "returncode": 0, "files": []},
    )

    def broken_guard(**_):
        raise RuntimeError("synthetic call-argument failure")

    monkeypatch.setattr(full, "audit_call_arguments", broken_guard)
    monkeypatch.setattr(full, "_load_closure", lambda _: {})
    result = full.run_full_chain(full_report_path=tmp_path / "full.json")
    assert result["status"] == "BLOCKED_AT_CALL_ARGUMENT_PREFLIGHT_ERROR"
    assert result["call_argument_error"] == "synthetic call-argument failure"
    assert (tmp_path / "full.json").exists()


def test_base_runtime_error_is_preserved_in_report(tmp_path: Path, monkeypatch) -> None:
    _prepare_guards(monkeypatch)

    def broken_base(**_):
        raise RuntimeError("synthetic base failure")

    monkeypatch.setattr(full.base_chain, "run_chain", broken_base)
    result = full.run_full_chain(full_report_path=tmp_path / "full.json")
    assert result["status"] == "BLOCKED_AT_BASE_PARAMETER_CHAIN_ERROR"
    assert result["base_chain_error"] == "synthetic base failure"
    assert result["canonical_source_mutated"] is False
    assert (tmp_path / "full.json").exists()


def test_local_capacity_route_does_not_run_local_native(tmp_path: Path, monkeypatch) -> None:
    _prepare_guards(monkeypatch)
    monkeypatch.setattr(
        full.base_chain,
        "run_chain",
        lambda **_: _base(
            local_allowed=False,
            local_next="PACKED_730_BLOCK_CAPACITY_CANDIDATE",
        ),
    )

    def unexpected_local(**_):
        raise AssertionError("local native qualifier must not run on a routed static preflight")

    monkeypatch.setattr(full, "qualify_locals", unexpected_local)
    result = full.run_full_chain(full_report_path=tmp_path / "full.json")
    assert result["status"] == "ROUTED_AFTER_PARAMETER_LOCAL_STATIC_PREFLIGHT"
    assert result["next"] == "PACKED_730_BLOCK_CAPACITY_CANDIDATE"


def test_local_runtime_error_is_preserved_in_report(tmp_path: Path, monkeypatch) -> None:
    _prepare_guards(monkeypatch)
    monkeypatch.setattr(
        full.base_chain,
        "run_chain",
        lambda **_: _base(
            local_allowed=True,
            local_next="NATIVE_LOCAL_METADATA_CANDIDATE",
        ),
    )

    def broken_local(**_):
        raise RuntimeError("synthetic local failure")

    monkeypatch.setattr(full, "qualify_locals", broken_local)
    result = full.run_full_chain(full_report_path=tmp_path / "full.json")
    assert result["status"] == "BLOCKED_AT_LOCAL_NATIVE_QUALIFIER_ERROR"
    assert result["local_native_error"] == "synthetic local failure"
    assert result["canonical_source_mutated"] is False
    assert (tmp_path / "full.json").exists()


def test_full_pass_runs_local_native_only_after_all_previous_gates(tmp_path: Path, monkeypatch) -> None:
    _prepare_guards(monkeypatch)
    monkeypatch.setattr(
        full.base_chain,
        "run_chain",
        lambda **_: _base(
            local_allowed=True,
            local_next="NATIVE_LOCAL_METADATA_CANDIDATE",
        ),
    )
    monkeypatch.setattr(full, "qualify_locals", lambda **_: _local_pass())
    result = full.run_full_chain(full_report_path=tmp_path / "full.json")
    assert result["status"] == "PASS_THROUGH_LOCAL_NATIVE_CANDIDATE"
    assert result["next"] == "UNIFIED_VALUE_NAMESPACE_CANDIDATE_PREFLIGHT"
    assert result["canonical_commit_allowed"] is False
    assert result["stage2"] == "NOT_STARTED"
    assert result["stage3"] == "NOT_STARTED"
