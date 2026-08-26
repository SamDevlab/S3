"""Qualify the Stage1 wide-numeric token-lane candidate on Linux x86-64.

The qualifier deliberately separates tokenizer correctness from the capacities
that become visible once the compiler can finally scan its entire own source.
A token-lane PASS therefore proves full-source AST/call observations match the
static repaired model; it does *not* authorize canonical promotion while newly
exposed call/event/value/block capacities remain unresolved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tools.audit_stage1_token_lane_wide_literals import audit as static_audit
from tools.build_stage1_compiler import build_stage1
from tools.patch_stage1_token_lane_wide_literals import (
    BASELINE_SOURCE_SHA256,
    SOURCE,
    transform,
)
from tools.preflight_stage1_codegen_ir_v2_locals import stage1_tokens
from tools.qualify_stage1_codegen_ir_v2_capacity import (
    _expected_trivial_assembly,
    _parse_audit,
    _run_stage1,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "packed-token-lane-native-candidate.json"
)

CALL_CAPACITY = 730
CALL_ARGUMENT_CAPACITY = 746
EVENT_CAPACITY = 1460


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_tests() -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_stage1_token_lane_wide_literals.py",
            "tests/test_stage1_codegen_ir_v2_call_arguments.py",
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
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _expected_ast_metrics(source: str, full_call_model: dict[str, object]) -> dict[str, int]:
    tokens = stage1_tokens(source)
    identifiers = [token.value for token in tokens if token.kind == 1]
    punctuation = [token.value for token in tokens if token.kind == 4]
    assignments = sum(1 for value in identifiers if value == 87) + sum(
        1 for value in punctuation if value in {5, 14}
    )
    binops = sum(1 for value in punctuation if value in {6, 7, 8, 9, 13, 15, 16, 17})
    comparisons = sum(1 for value in punctuation if value in {13, 15, 16, 17})
    structural_events = (
        sum(1 for value in identifiers if value in {342, 162, 135, 37, 220, 87})
        + sum(1 for value in punctuation if value in {5, 6, 7, 8, 9, 13, 14, 15, 16, 17})
        + int(full_call_model["calls"])
    )
    return {
        "local_count": sum(1 for value in identifiers if value == 87),
        "ast_assignment_count": assignments,
        "ast_call_count": int(full_call_model["calls"]),
        "ast_return_count": sum(1 for value in identifiers if value == 342),
        "ast_match_count": sum(1 for value in identifiers if value == 135),
        "ast_while_count": sum(1 for value in identifiers if value == 162),
        "ast_break_count": sum(1 for value in identifiers if value == 37),
        "ast_binop_count": binops,
        "ast_comparison_count": comparisons,
        "ast_cast_count": 0,
        "ast_discard_count": sum(1 for value in identifiers if value == 220),
        "full_structural_event_tokens": structural_events,
        "full_numeric_tokens": sum(1 for token in tokens if token.kind == 2),
        "function_signature_tokens": sum(
            1 for token in tokens if token.kind == 1 and token.value == 352
        ),
    }


def _ast_guards(audit: dict[str, int] | None, expected: dict[str, int]) -> dict[str, bool]:
    fields = (
        "local_count",
        "ast_assignment_count",
        "ast_call_count",
        "ast_return_count",
        "ast_match_count",
        "ast_while_count",
        "ast_break_count",
        "ast_binop_count",
        "ast_comparison_count",
        "ast_cast_count",
        "ast_discard_count",
    )
    if audit is None:
        return {field: False for field in fields}
    return {field: audit.get(field) == expected[field] for field in fields}


def qualify(*, report_path: Path, run_tests: bool = True) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("wide token-lane native qualification requires Linux x86-64")
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise RuntimeError("wide token-lane qualification requires cc, gcc, or clang")

    baseline_bytes = SOURCE.read_bytes()
    baseline_sha = _sha256(baseline_bytes)
    if baseline_sha != BASELINE_SOURCE_SHA256:
        raise RuntimeError(
            "canonical source differs from frozen token-lane baseline: "
            f"expected {BASELINE_SOURCE_SHA256}, got {baseline_sha}"
        )
    baseline_text = baseline_bytes.decode("utf-8")
    candidate_text = transform(baseline_text)
    candidate_bytes = candidate_text.encode("utf-8")

    static = static_audit(baseline_text)
    static_pass = str(static["status"]).startswith("STATIC_WIDE_TOKEN_LANE_PASS")
    candidate_model = static["repaired_candidate_model"]["call_model"]
    expected_ast = _expected_ast_metrics(candidate_text, candidate_model)

    tests = _run_tests() if run_tests else {"status": "SKIPPED_BY_OPERATOR"}
    tests_pass = tests.get("status") == "PASS"
    if run_tests and not tests_pass:
        raise RuntimeError("wide token-lane focused tests failed before native build")

    with tempfile.TemporaryDirectory(prefix="s3-wide-token-lane-") as directory:
        temp = Path(directory)
        candidate_source = temp / "s3c_stage1.wide-token-lane.s3"
        executable = temp / "s3c-stage1-wide-token-lane"
        assembly = temp / "s3c-stage1-wide-token-lane.s"
        candidate_source.write_bytes(candidate_bytes)

        build_stage1(executable, source=candidate_source, assembly_output=assembly)
        executable_bytes = executable.read_bytes()
        assembly_bytes = assembly.read_bytes()

        trivial = _run_stage1(executable, b"fn main() -> tryte:\n    return 7\n")
        trivial_pass = (
            trivial.returncode == 0
            and trivial.stderr == b""
            and trivial.stdout == _expected_trivial_assembly(7)
        )

        self_run = _run_stage1(executable, candidate_bytes)
        native_audit, stderr_lines = _parse_audit(self_run.stderr)
        final_marker = stderr_lines[-1] if stderr_lines else None
        audit_present = native_audit is not None
        ast_guards = _ast_guards(native_audit, expected_ast)
        full_ast_match = all(ast_guards.values())
        fail_closed_boundary = (
            self_run.returncode == 2
            and self_run.stdout == b""
            and audit_present
        )

        token_lane_pass = bool(
            static_pass
            and tests_pass
            and trivial_pass
            and fail_closed_boundary
            and full_ast_match
        )

        calls = int(candidate_model["calls"])
        arguments = int(candidate_model["total_call_arguments"])
        events = int(expected_ast["full_structural_event_tokens"])
        if not token_lane_pass:
            next_gate = "FIX_WIDE_TOKEN_LANE_NATIVE_DIFFERENTIAL"
        elif calls > CALL_CAPACITY:
            next_gate = "EXPAND_CALL_CAPACITY_FROM_FULL_SOURCE_TOKEN_LANE_MODEL"
        elif arguments > CALL_ARGUMENT_CAPACITY:
            next_gate = "EXPAND_CALL_ARGUMENT_CAPACITY_FROM_FULL_SOURCE_TOKEN_LANE_MODEL"
        elif events >= EVENT_CAPACITY:
            next_gate = "QUALIFY_FULL_SOURCE_EVENT_COMPACTION_OR_CAPACITY"
        else:
            next_gate = "REBASE_COMPACTION_ON_QUALIFIED_WIDE_TOKEN_LANE_CANDIDATE"

        result = {
            "schema": "s3.selfhost.packed-token-lane-native-candidate.v1",
            "platform": {
                "system": platform.system(),
                "machine": platform.machine(),
                "compiler": compiler,
                "python": sys.executable,
            },
            "canonical_source_mutated": False,
            "canonical_commit_allowed": False,
            "baseline": {
                "source_sha256": baseline_sha,
                "source_bytes": len(baseline_bytes),
            },
            "candidate": {
                "source_sha256": _sha256(candidate_bytes),
                "source_bytes": len(candidate_bytes),
                "stage1_executable_sha256": _sha256(executable_bytes),
                "stage1_executable_bytes": len(executable_bytes),
                "stage1_assembly_sha256": _sha256(assembly_bytes),
                "stage1_assembly_bytes": len(assembly_bytes),
            },
            "focused_tests": tests,
            "static_preflight": static,
            "expected_full_source_ast": expected_ast,
            "trivial_compile": {
                "status": "PASS" if trivial_pass else "FAIL",
                "returncode": trivial.returncode,
                "stderr": trivial.stderr.decode("ascii", errors="replace"),
                "stdout_sha256": _sha256(trivial.stdout),
            },
            "self_source": {
                "returncode": self_run.returncode,
                "stdout_bytes": len(self_run.stdout),
                "stderr_lines": stderr_lines,
                "final_marker": final_marker,
                "audit": native_audit,
                "audit_present": audit_present,
                "fail_closed_boundary": fail_closed_boundary,
                "full_source_ast_guards": ast_guards,
                "full_source_ast_match": full_ast_match,
            },
            "exposed_capacity_model": {
                "calls_required": calls,
                "calls_capacity": CALL_CAPACITY,
                "call_arguments_required": arguments,
                "call_arguments_capacity": CALL_ARGUMENT_CAPACITY,
                "structural_events_required_before_compaction": events,
                "event_capacity": EVENT_CAPACITY,
                "numeric_tokens": expected_ast["full_numeric_tokens"],
            },
            "qualification": {
                "token_lane_candidate": (
                    "PASS_NATIVE_CANDIDATE" if token_lane_pass else "FAIL"
                ),
                "full_source_ast_match": "PASS" if full_ast_match else "FAIL",
                "canonical_commit_allowed": False,
                "next": next_gate,
                "self_emit": "NOT_STARTED",
                "stage2": "NOT_STARTED",
                "stage3": "NOT_STARTED",
                "full_self_hosting": False,
            },
        }

    destination = report_path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args(argv)

    result = qualify(report_path=args.report, run_tests=not args.skip_tests)
    qualification = result["qualification"]
    print(f"REPORT={args.report.resolve()}")
    print(f"TOKEN_LANE_CANDIDATE={qualification['token_lane_candidate']}")
    print(f"FULL_SOURCE_AST_MATCH={qualification['full_source_ast_match']}")
    capacity = result["exposed_capacity_model"]
    print(f"FULL_SOURCE_CALLS_REQUIRED={capacity['calls_required']}")
    print(f"FULL_SOURCE_CALL_ARGUMENTS_REQUIRED={capacity['call_arguments_required']}")
    print(f"FULL_SOURCE_EVENTS_REQUIRED={capacity['structural_events_required_before_compaction']}")
    print(f"CANONICAL_COMMIT_ALLOWED={qualification['canonical_commit_allowed']}")
    print(f"NEXT={qualification['next']}")
    return 0 if qualification["token_lane_candidate"] == "PASS_NATIVE_CANDIDATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
