"""Qualify the pre-IR-v2 Stage1 token lane before compaction/metadata work.

The prior IR-v2 chain assumed the native Stage1 could observe its complete own
source. Native/static differential evidence disproved that assumption: wide
numeric literals spill out of ``pack_token``'s 1000-state value lane and can
advance the decoded cursor past the remaining source. This wrapper therefore
makes full-source token-lane qualification the mandatory predecessor to any
further compaction/parameter/local qualification.

Before the native build it also proves the rebased discard-compaction semantic
model and computes the minimum full-source capacity plan. It never mutates the
canonical compiler and intentionally does not invoke the legacy IR-v2 chain.
After token-lane PASS it routes to the exact capacity or compaction-rebase task
exposed by the full-source model.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tools.audit_stage1_compaction_after_token_lane import (
    audit as audit_compaction,
)
from tools.audit_stage1_token_lane_wide_literals import (
    SOURCE,
    audit as audit_token_lane,
)
from tools.plan_stage1_full_source_capacities import plan as plan_capacities
from tools.qualify_stage1_token_lane_wide_literals import (
    DEFAULT_REPORT as DEFAULT_NATIVE_REPORT,
    qualify as qualify_token_lane,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "pre-ir-v2-token-lane-chain.json"
)

GUARD_TESTS = (
    "tests/test_stage1_token_lane_wide_literals.py",
    "tests/test_stage1_compaction_after_token_lane.py",
    "tests/test_stage1_compaction_after_token_lane_audit.py",
    "tests/test_stage1_full_source_capacity_plan.py",
    "tests/test_stage1_codegen_ir_v2_call_arguments.py",
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
        [sys.executable, "-m", "pytest", "-q", *GUARD_TESTS],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
        shell=False,
    )
    return {
        "status": "PASS" if completed.returncode == 0 else "FAIL",
        "returncode": completed.returncode,
        "files": list(GUARD_TESTS),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def run_chain(
    *,
    report_path: Path = DEFAULT_REPORT,
    native_report_path: Path = DEFAULT_NATIVE_REPORT,
    run_tests: bool = True,
) -> dict[str, object]:
    guard_tests = _run_guard_tests() if run_tests else {"status": "SKIPPED"}
    guards_pass = guard_tests.get("status") == "PASS" or not run_tests

    source_text: str | None = None
    static: dict[str, object] | None = None
    static_error: str | None = None
    compaction_static: dict[str, object] | None = None
    compaction_static_error: str | None = None
    capacity_plan: dict[str, object] | None = None
    capacity_plan_error: str | None = None
    native: dict[str, object] | None = None
    native_error: str | None = None

    if guards_pass:
        try:
            source_text = SOURCE.read_text(encoding="utf-8")
            static = audit_token_lane(source_text)
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            static_error = str(error)

    static_pass = bool(
        isinstance(static, dict)
        and str(static.get("status", "")).startswith("STATIC_WIDE_TOKEN_LANE_PASS")
    )

    if guards_pass and static_pass and source_text is not None:
        try:
            compaction_static = audit_compaction(source_text)
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            compaction_static_error = str(error)

    compaction_static_pass = bool(
        isinstance(compaction_static, dict)
        and compaction_static.get("status")
        == "STATIC_COMPACTION_SEMANTIC_DIFFERENTIAL_PASS_NATIVE_2X2_REQUIRED"
    )

    if guards_pass and static_pass and compaction_static_pass and source_text is not None:
        try:
            capacity_plan = plan_capacities(source_text)
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            capacity_plan_error = str(error)

    capacity_plan_pass = bool(
        isinstance(capacity_plan, dict)
        and capacity_plan.get("status") == "STATIC_PLAN_NATIVE_REMEASUREMENT_REQUIRED"
    )

    if guards_pass and static_pass and compaction_static_pass and capacity_plan_pass:
        try:
            native = qualify_token_lane(
                report_path=native_report_path,
                run_tests=False,
            )
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            native_error = str(error)

    native_pass = bool(
        isinstance(native, dict)
        and native.get("qualification", {}).get("token_lane_candidate")
        == "PASS_NATIVE_CANDIDATE"
    )

    if not guards_pass:
        status = "BLOCKED_AT_TOKEN_LANE_GUARD_TESTS"
        next_gate = "REPAIR_TOKEN_LANE_TOOLING"
    elif static_error is not None:
        status = "BLOCKED_AT_TOKEN_LANE_STATIC_AUDIT_ERROR"
        next_gate = "REPAIR_TOKEN_LANE_STATIC_AUDIT"
    elif not static_pass:
        status = "BLOCKED_AT_TOKEN_LANE_STATIC_AUDIT"
        next_gate = (
            str(static.get("next")) if isinstance(static, dict)
            else "REVIEW_TOKEN_LANE_STATIC_REPORT"
        )
    elif compaction_static_error is not None:
        status = "BLOCKED_AT_REBASED_COMPACTION_STATIC_AUDIT_ERROR"
        next_gate = "REPAIR_REBASED_COMPACTION_STATIC_AUDIT"
    elif not compaction_static_pass:
        status = "BLOCKED_AT_REBASED_COMPACTION_STATIC_AUDIT"
        next_gate = (
            str(compaction_static.get("next"))
            if isinstance(compaction_static, dict)
            else "REVIEW_REBASED_COMPACTION_STATIC_REPORT"
        )
    elif capacity_plan_error is not None:
        status = "BLOCKED_AT_FULL_SOURCE_CAPACITY_PLAN_ERROR"
        next_gate = "REPAIR_FULL_SOURCE_CAPACITY_PLANNER"
    elif not capacity_plan_pass:
        status = "BLOCKED_AT_FULL_SOURCE_CAPACITY_PLAN"
        next_gate = "REVIEW_FULL_SOURCE_CAPACITY_PLAN"
    elif native_error is not None:
        status = "BLOCKED_AT_TOKEN_LANE_NATIVE_QUALIFIER_ERROR"
        next_gate = "REPAIR_TOKEN_LANE_NATIVE_QUALIFIER_OR_ENVIRONMENT"
    elif not native_pass:
        status = "BLOCKED_AT_TOKEN_LANE_NATIVE_CANDIDATE"
        next_gate = (
            str(native.get("qualification", {}).get("next"))
            if isinstance(native, dict)
            else "REVIEW_TOKEN_LANE_NATIVE_REPORT"
        )
    else:
        status = "PASS_TOKEN_LANE_NATIVE_CANDIDATE_ROUTE_NEXT_CAPACITY"
        # Native evidence has precedence, but the static capacity plan is kept
        # adjacent in the report so the next bounded source transform can be
        # selected from exact/full-source requirements rather than old prefix
        # closure counts.
        next_gate = str(native["qualification"]["next"])

    result: dict[str, object] = {
        "schema": "s3.selfhost.pre-ir-v2-token-lane-chain.v2",
        "canonical_source_mutated": False,
        "guard_tests": guard_tests,
        "static_token_lane": static,
        "static_error": static_error,
        "rebased_compaction_static": compaction_static,
        "rebased_compaction_static_error": compaction_static_error,
        "full_source_capacity_plan": capacity_plan,
        "full_source_capacity_plan_error": capacity_plan_error,
        "native_token_lane": native,
        "native_error": native_error,
        "status": status,
        "next": next_gate,
        "legacy_ir_v2_chain_invoked": False,
        "reason_legacy_chain_not_invoked": (
            "Compaction/parameter/local candidates must be rebased on a natively "
            "qualified full-source token lane; the legacy chain operates on the "
            "known partial-source token behavior."
        ),
        "canonical_commit_allowed": False,
        "general_emitter": "BLOCKED_IR_V2_INCOMPLETE",
        "self_emit": "NOT_STARTED",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }
    _write(report_path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--native-report", type=Path, default=DEFAULT_NATIVE_REPORT)
    args = parser.parse_args(argv)

    result = run_chain(
        report_path=args.report,
        native_report_path=args.native_report,
        run_tests=True,
    )
    print(f"REPORT={args.report.resolve()}")
    print(f"GUARD_TESTS={result['guard_tests']['status']}")
    static = result.get("static_token_lane")
    if isinstance(static, dict):
        repaired = static["repaired_candidate_model"]
        calls = repaired["call_model"]
        print(f"STATIC_TOKEN_LANE={static['status']}")
        print(f"STATIC_FULL_COVERAGE={repaired['full_character_coverage']}")
        print(f"FULL_SOURCE_CALLS={calls['calls']}")
        print(f"FULL_SOURCE_CALL_ARGUMENTS={calls['total_call_arguments']}")
    else:
        print("STATIC_TOKEN_LANE=NOT_RUN")

    compaction = result.get("rebased_compaction_static")
    print(
        "REBASED_COMPACTION_STATIC="
        + (str(compaction.get("status")) if isinstance(compaction, dict) else "NOT_RUN")
    )
    plan = result.get("full_source_capacity_plan")
    if isinstance(plan, dict):
        requirements = plan["requirements"]
        print(f"PLANNED_CALLS={requirements['calls']}")
        print(f"PLANNED_CALL_ARGUMENTS={requirements['call_arguments']}")
        print(f"PLANNED_EVENTS_AFTER_COMPACTION={requirements['events_after_discard_compaction']}")
        print(f"CAPACITY_ROUTES={','.join(str(item) for item in plan['routes'])}")
    else:
        print("CAPACITY_PLAN=NOT_RUN")

    native = result.get("native_token_lane")
    print(
        "NATIVE_TOKEN_LANE="
        + (
            str(native.get("qualification", {}).get("token_lane_candidate"))
            if isinstance(native, dict)
            else "NOT_RUN"
        )
    )
    print(f"STATUS={result['status']}")
    print(f"NEXT={result['next']}")
    print("LEGACY_IR_V2_CHAIN_INVOKED=False")
    print("CANONICAL_SOURCE_MUTATED=False")
    print("STAGE2=NOT_STARTED")
    print("STAGE3=NOT_STARTED")
    return 0 if str(result["status"]).startswith("PASS_TOKEN_LANE") else 2


if __name__ == "__main__":
    raise SystemExit(main())
