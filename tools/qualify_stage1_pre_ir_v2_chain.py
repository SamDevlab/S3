"""Qualify the pre-IR-v2 Stage1 token lane before compaction/metadata work.

The prior IR-v2 chain assumed the native Stage1 could observe its complete own
source.  Native/static differential evidence disproved that assumption: wide
numeric literals spill out of ``pack_token``'s 1000-state value lane and can
advance the decoded cursor past the remaining source.  This wrapper therefore
makes full-source token-lane qualification the mandatory predecessor to any
further compaction/parameter/local qualification.

It never mutates the canonical compiler and intentionally does not invoke the
legacy compaction chain.  After token-lane PASS it routes to the exact capacity
or compaction-rebase task exposed by the full-source model.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tools.audit_stage1_token_lane_wide_literals import (
    SOURCE,
    audit as audit_token_lane,
)
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

    static: dict[str, object] | None = None
    static_error: str | None = None
    native: dict[str, object] | None = None
    native_error: str | None = None

    if guards_pass:
        try:
            static = audit_token_lane(SOURCE.read_text(encoding="utf-8"))
        except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
            static_error = str(error)

    static_pass = bool(
        isinstance(static, dict)
        and str(static.get("status", "")).startswith("STATIC_WIDE_TOKEN_LANE_PASS")
    )

    if guards_pass and static_pass:
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
        next_gate = str(native["qualification"]["next"])

    result: dict[str, object] = {
        "schema": "s3.selfhost.pre-ir-v2-token-lane-chain.v1",
        "canonical_source_mutated": False,
        "guard_tests": guard_tests,
        "static_token_lane": static,
        "static_error": static_error,
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
