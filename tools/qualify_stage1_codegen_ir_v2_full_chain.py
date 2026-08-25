"""Run the guarded Stage1 IR-v2 chain through the native local candidate.

This wrapper adds two protections around the existing candidate chain:
1. validate the static call/call-argument model against the authoritative native
   656-call/736-argument closure before any expensive native candidate build;
2. after a real parameter PASS and exact local static preflight, automatically
   run the transactional native local-metadata qualifier.

The canonical compiler is never modified or promoted. Stage2/Stage3 are never
started here. A routed capacity result is a valid fail-closed outcome.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import tools.qualify_stage1_codegen_ir_v2_chain as base_chain
from tools.audit_stage1_codegen_ir_v2_call_arguments import (
    CLOSURE,
    SOURCE,
    _load_closure,
    audit as audit_call_arguments,
)
from tools.qualify_stage1_codegen_ir_v2_locals import (
    DEFAULT_REPORT as DEFAULT_LOCAL_NATIVE_REPORT,
    LocalNativeQualificationError,
    qualify as qualify_locals,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-full-candidate-chain.json"
)
EXTRA_GUARD_TESTS = (
    "tests/test_stage1_codegen_ir_v2_call_arguments.py",
    "tests/test_stage1_codegen_ir_v2_local_qualifier.py",
    "tests/test_stage1_codegen_ir_v2_full_chain.py",
)

_EXPECTED_RUNTIME_ERRORS = (
    LocalNativeQualificationError,
    OSError,
    RuntimeError,
    ValueError,
    subprocess.SubprocessError,
)


def _write(path: Path, value: dict[str, object]) -> None:
    destination = path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _run_guard_tests() -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *EXTRA_GUARD_TESTS,
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    return {
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "returncode": completed.returncode,
        "files": list(EXTRA_GUARD_TESTS),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def run_full_chain(
    *,
    full_report_path: Path,
    base_chain_report_path: Path = base_chain.DEFAULT_CHAIN_REPORT,
    local_native_report_path: Path = DEFAULT_LOCAL_NATIVE_REPORT,
    run_guard_tests: bool = True,
) -> dict[str, object]:
    guard_tests = (
        _run_guard_tests()
        if run_guard_tests
        else {
            "status": "SKIPPED_BY_TEST_HARNESS",
            "returncode": None,
            "files": list(EXTRA_GUARD_TESTS),
        }
    )
    guard_tests_pass = guard_tests.get("status") == "PASS" or not run_guard_tests

    call_argument_guard: dict[str, object] | None = None
    call_argument_error: str | None = None
    if guard_tests_pass:
        try:
            canonical_source = SOURCE.read_text(encoding="utf-8")
            call_argument_guard = audit_call_arguments(
                canonical_source=canonical_source,
                closure=_load_closure(CLOSURE),
            )
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            call_argument_error = str(error)

    call_argument_guard_pass = bool(
        isinstance(call_argument_guard, dict)
        and call_argument_guard.get("status") == "PASS_STATIC_CALL_ARGUMENT_MODEL"
        and call_argument_guard.get("parameter_candidate", {}).get(
            "safe_under_current_call_and_argument_capacities"
        ) is True
    )

    base_result: dict[str, object] | None = None
    base_error: str | None = None
    local_native: dict[str, object] | None = None
    local_error: str | None = None

    if guard_tests_pass and call_argument_guard_pass:
        try:
            base_result = base_chain.run_chain(
                capacity_report_path=base_chain.DEFAULT_CAPACITY_REPORT,
                parameter_report_path=base_chain.DEFAULT_PARAMETER_REPORT,
                next_phase_report_path=base_chain.DEFAULT_NEXT_PHASE_REPORT,
                local_preflight_report_path=base_chain.DEFAULT_LOCAL_PREFLIGHT_REPORT,
                static_preflight_report_path=base_chain.DEFAULT_STATIC_PREFLIGHT_REPORT,
                chain_report_path=base_chain_report_path,
                run_tooling_tests=True,
            )
        except _EXPECTED_RUNTIME_ERRORS as error:
            base_error = str(error)

    base_pass = bool(
        base_result is not None
        and base_result.get("chain_status") == "PASS_THROUGH_PARAMETER_CANDIDATE"
    )
    local_preflight = (
        base_result.get("local_candidate_preflight", {})
        if isinstance(base_result, dict)
        else {}
    )
    local_static_allows_native = bool(
        isinstance(local_preflight, dict)
        and local_preflight.get("native_qualification_allowed") is True
        and local_preflight.get("next") == "NATIVE_LOCAL_METADATA_CANDIDATE"
    )

    if base_pass and local_static_allows_native:
        try:
            local_native = qualify_locals(
                parameter_report_path=base_chain.DEFAULT_PARAMETER_REPORT,
                static_preflight_report_path=base_chain.DEFAULT_LOCAL_PREFLIGHT_REPORT,
                report_path=local_native_report_path,
            )
        except _EXPECTED_RUNTIME_ERRORS as error:
            local_error = str(error)

    local_native_pass = bool(
        isinstance(local_native, dict)
        and local_native.get("qualification", {}).get("local_ir_v2_candidate")
        == "PASS_NATIVE_CANDIDATE"
    )

    if not guard_tests_pass:
        status = "BLOCKED_AT_IR_V2_GUARD_TESTS"
        next_gate = "REPAIR_IR_V2_GUARD_TOOLING"
    elif call_argument_error is not None:
        status = "BLOCKED_AT_CALL_ARGUMENT_PREFLIGHT_ERROR"
        next_gate = "REPAIR_CALL_ARGUMENT_PREFLIGHT_OR_CLOSURE_INPUT"
    elif not call_argument_guard_pass:
        status = "BLOCKED_AT_PARAMETER_CALL_ARGUMENT_PREFLIGHT"
        next_gate = (
            str(call_argument_guard.get("next"))
            if isinstance(call_argument_guard, dict)
            else "REVIEW_CALL_ARGUMENT_PREFLIGHT"
        )
    elif base_error is not None:
        status = "BLOCKED_AT_BASE_PARAMETER_CHAIN_ERROR"
        next_gate = "REPAIR_BASE_PARAMETER_CHAIN_OR_ENVIRONMENT"
    elif not base_pass:
        status = "BLOCKED_IN_BASE_PARAMETER_CHAIN"
        next_gate = (
            str(base_result.get("local_candidate_preflight", {}).get("next"))
            if isinstance(base_result, dict)
            else "REVIEW_BASE_CHAIN_REPORT"
        )
    elif not local_static_allows_native:
        status = "ROUTED_AFTER_PARAMETER_LOCAL_STATIC_PREFLIGHT"
        next_gate = str(local_preflight.get("next"))
    elif local_error is not None:
        status = "BLOCKED_AT_LOCAL_NATIVE_QUALIFIER_ERROR"
        next_gate = "REPAIR_LOCAL_NATIVE_QUALIFIER_OR_CANDIDATE"
    elif not local_native_pass:
        status = "BLOCKED_AT_LOCAL_NATIVE_CANDIDATE"
        next_gate = (
            str(local_native.get("qualification", {}).get("next"))
            if isinstance(local_native, dict)
            else "REVIEW_LOCAL_NATIVE_REPORT"
        )
    else:
        status = "PASS_THROUGH_LOCAL_NATIVE_CANDIDATE"
        next_gate = "UNIFIED_VALUE_NAMESPACE_CANDIDATE_PREFLIGHT"

    result: dict[str, object] = {
        "schema": "s3.selfhost.codegen-ir-v2-full-candidate-chain.v2",
        "canonical_source_mutated": False,
        "guard_tests": guard_tests,
        "call_argument_guard": call_argument_guard,
        "call_argument_error": call_argument_error,
        "base_chain": base_result,
        "base_chain_error": base_error,
        "local_native": local_native,
        "local_native_error": local_error,
        "status": status,
        "next": next_gate,
        "canonical_commit_allowed": False,
        "general_emitter": "BLOCKED_IR_V2_INCOMPLETE",
        "self_emit": "NOT_STARTED",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
        "qualification_rule": (
            "PASS here means only that candidate compaction, parameter metadata and local metadata reached their expected Stage1 boundaries. It never promotes canonical source and never implies self-emission or Stage2."
        ),
    }
    _write(full_report_path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--base-chain-report", type=Path, default=base_chain.DEFAULT_CHAIN_REPORT)
    parser.add_argument("--local-native-report", type=Path, default=DEFAULT_LOCAL_NATIVE_REPORT)
    args = parser.parse_args(argv)

    result = run_full_chain(
        full_report_path=args.report,
        base_chain_report_path=args.base_chain_report,
        local_native_report_path=args.local_native_report,
        run_guard_tests=True,
    )
    print(f"REPORT={args.report.resolve()}")
    print(f"GUARD_TESTS={result['guard_tests']['status']}")
    call_guard = result.get("call_argument_guard")
    if isinstance(call_guard, dict):
        call_model = call_guard["canonical"]["model"]
        parameter_model = call_guard["parameter_candidate"]["model"]
        print(f"CANONICAL_CALL_ARGUMENTS={call_model['total_call_arguments']}")
        print(f"PARAMETER_CALL_ARGUMENTS={parameter_model['total_call_arguments']}")
        print(f"PARAMETER_CALL_ARGUMENT_HEADROOM={parameter_model['call_argument_headroom']}")
    else:
        print("CANONICAL_CALL_ARGUMENTS=NOT_AVAILABLE")
        print("PARAMETER_CALL_ARGUMENTS=NOT_AVAILABLE")
        print("PARAMETER_CALL_ARGUMENT_HEADROOM=NOT_AVAILABLE")
    if result.get("call_argument_error"):
        print(f"CALL_ARGUMENT_ERROR={result['call_argument_error']}")
    base = result.get("base_chain")
    print(
        "BASE_CHAIN_STATUS="
        + (str(base.get("chain_status")) if isinstance(base, dict) else "NOT_RUN")
    )
    if result.get("base_chain_error"):
        print(f"BASE_CHAIN_ERROR={result['base_chain_error']}")
    local_preflight = base.get("local_candidate_preflight", {}) if isinstance(base, dict) else {}
    print(f"LOCAL_STATIC_PREFLIGHT={local_preflight.get('status', 'NOT_RUN')}")
    print(f"LOCAL_NATIVE_QUALIFICATION_ALLOWED={local_preflight.get('native_qualification_allowed', False)}")
    local = result.get("local_native")
    print(
        "LOCAL_NATIVE_CANDIDATE="
        + (
            str(local.get("qualification", {}).get("local_ir_v2_candidate"))
            if isinstance(local, dict)
            else "NOT_RUN"
        )
    )
    if isinstance(local, dict):
        local_call = local["call_argument_preflight"]["local_candidate"]["model"]
        print(f"LOCAL_CALL_ARGUMENTS={local_call['total_call_arguments']}")
        print(f"LOCAL_CALL_ARGUMENT_HEADROOM={local_call['call_argument_headroom']}")
    if result.get("local_native_error"):
        print(f"LOCAL_NATIVE_ERROR={result['local_native_error']}")
    print(f"STATUS={result['status']}")
    print(f"NEXT={result['next']}")
    print("CANONICAL_SOURCE_MUTATED=False")
    print("STAGE2=NOT_STARTED")
    print("STAGE3=NOT_STARTED")
    return 0 if result["status"] == "PASS_THROUGH_LOCAL_NATIVE_CANDIDATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
