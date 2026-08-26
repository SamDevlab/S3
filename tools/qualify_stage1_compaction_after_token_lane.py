"""Qualify discard-event compaction after a native wide-token-lane PASS.

The qualifier builds two real Stage1 executables through Stage0:

* E0: wide-token-lane repair only;
* E1: wide-token-lane repair + redundant discard-event compaction.

It then executes each compiler against both exact source inputs S0/E0-source and
S1/E1-source.  This separates compiler-behavior effects from self-source textual
input effects.  The native semantic gate compares full AST observations on the
same input and checks capped event counts against the independent full-source
static model.  Block equality is required only when both compared event streams
fit completely in the current event pool; otherwise block drift remains an
explicit capacity/truncation observation rather than being silently waived.

This is candidate-only and never promotes the canonical compiler.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tools.audit_stage1_compaction_after_token_lane import audit as static_compaction_audit
from tools.patch_stage1_compaction_after_token_lane import (
    build_compacted_candidate,
    build_token_lane_candidate,
)
from tools.patch_stage1_token_lane_wide_literals import SOURCE
from tools.plan_stage1_full_source_capacities import plan as plan_capacities
from tools.qualify_stage1_codegen_ir_v2_capacity import (
    _expected_trivial_assembly,
    _parse_audit,
    _run_stage1,
)
from tools.build_stage1_compiler import build_stage1


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TOKEN_NATIVE_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "packed-token-lane-native-candidate.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "compaction-after-token-lane-native-2x2.json"
)
EVENT_CAPACITY = 1460

_AST_FIELDS = (
    "function_count",
    "foreign_count",
    "parameter_count",
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


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.resolve().read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _validate_token_prerequisite(report: dict[str, Any], token_source: bytes) -> None:
    qualification = report.get("qualification")
    candidate = report.get("candidate")
    if not isinstance(qualification, dict) or not isinstance(candidate, dict):
        raise ValueError("token-lane report missing qualification/candidate sections")
    if qualification.get("token_lane_candidate") != "PASS_NATIVE_CANDIDATE":
        raise ValueError("native wide-token-lane PASS is required before compaction 2x2")
    if report.get("canonical_source_mutated") is not False:
        raise ValueError("token-lane prerequisite must be transactional")
    expected_sha = _sha256(token_source)
    if candidate.get("source_sha256") != expected_sha:
        raise ValueError("token-lane report source SHA does not match exact rebuilt S0")
    if candidate.get("source_bytes") != len(token_source):
        raise ValueError("token-lane report source size does not match exact rebuilt S0")


def _build(source_path: Path, executable: Path, assembly: Path) -> dict[str, object]:
    build_stage1(executable, source=source_path, assembly_output=assembly)
    return {
        "executable_sha256": _sha256(executable.read_bytes()),
        "executable_bytes": executable.stat().st_size,
        "assembly_sha256": _sha256(assembly.read_bytes()),
        "assembly_bytes": assembly.stat().st_size,
    }


def _run_cell(executable: Path, source: bytes) -> dict[str, object]:
    completed = _run_stage1(executable, source)
    audit, stderr_lines = _parse_audit(completed.stderr)
    return {
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256": _sha256(completed.stdout),
        "stderr_lines": stderr_lines,
        "final_marker": stderr_lines[-1] if stderr_lines else None,
        "audit": audit,
        "audit_present": audit is not None,
        "fail_closed_boundary": (
            completed.returncode == 2
            and completed.stdout == b""
            and audit is not None
        ),
    }


def _same_input_ast(left: dict[str, object], right: dict[str, object]) -> dict[str, bool]:
    left_audit = left.get("audit")
    right_audit = right.get("audit")
    if not isinstance(left_audit, dict) or not isinstance(right_audit, dict):
        return {field: False for field in _AST_FIELDS}
    return {field: left_audit.get(field) == right_audit.get(field) for field in _AST_FIELDS}


def _event_count_guard(cell: dict[str, object], expected_full: int) -> bool:
    audit = cell.get("audit")
    if not isinstance(audit, dict):
        return False
    return audit.get("ir_instruction_count") == min(expected_full, EVENT_CAPACITY)


def _input_delta_guards(s0_cell: dict[str, object], s1_cell: dict[str, object]) -> dict[str, bool]:
    a0 = s0_cell.get("audit")
    a1 = s1_cell.get("audit")
    if not isinstance(a0, dict) or not isinstance(a1, dict):
        return {
            "assignment_delta_minus_two": False,
            "discard_count_preserved": False,
            "match_count_preserved": False,
            "while_count_preserved": False,
        }
    return {
        "assignment_delta_minus_two": (
            int(a1.get("ast_assignment_count", -10**9))
            - int(a0.get("ast_assignment_count", 10**9))
            == -2
        ),
        "discard_count_preserved": a1.get("ast_discard_count") == a0.get("ast_discard_count"),
        "match_count_preserved": a1.get("ast_match_count") == a0.get("ast_match_count"),
        "while_count_preserved": a1.get("ast_while_count") == a0.get("ast_while_count"),
    }


def _block_guard(
    e0: dict[str, object],
    e1: dict[str, object],
    *,
    e0_full_events: int,
    e1_full_events: int,
) -> dict[str, object]:
    both_complete = e0_full_events <= EVENT_CAPACITY and e1_full_events <= EVENT_CAPACITY
    a0 = e0.get("audit")
    a1 = e1.get("audit")
    if not both_complete:
        return {
            "applicable": False,
            "pass": None,
            "reason": "EVENT_STREAM_TRUNCATION_PRESENT",
            "e0_full_events": e0_full_events,
            "e1_full_events": e1_full_events,
        }
    passed = bool(
        isinstance(a0, dict)
        and isinstance(a1, dict)
        and a0.get("ir_block_count") == a1.get("ir_block_count")
    )
    return {
        "applicable": True,
        "pass": passed,
        "reason": "BOTH_EVENT_STREAMS_FIT_CURRENT_POOL",
        "e0_full_events": e0_full_events,
        "e1_full_events": e1_full_events,
    }


def qualify(
    *,
    token_native_report_path: Path = DEFAULT_TOKEN_NATIVE_REPORT,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("rebased compaction 2x2 requires Linux x86-64")
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise RuntimeError("rebased compaction 2x2 requires cc, gcc, or clang")

    canonical_text = SOURCE.read_text(encoding="utf-8")
    s0_text = build_token_lane_candidate(canonical_text)
    s1_text = build_compacted_candidate(canonical_text)
    s0 = s0_text.encode("utf-8")
    s1 = s1_text.encode("utf-8")

    token_report = _load_json(token_native_report_path)
    _validate_token_prerequisite(token_report, s0)

    static = static_compaction_audit(canonical_text)
    if static.get("status") != "STATIC_COMPACTION_SEMANTIC_DIFFERENTIAL_PASS_NATIVE_2X2_REQUIRED":
        raise RuntimeError("rebased compaction static differential must pass before native 2x2")
    capacity = plan_capacities(canonical_text)
    matrix_static = static["matrix"]

    with tempfile.TemporaryDirectory(prefix="s3-compaction-2x2-") as directory:
        temp = Path(directory)
        s0_path = temp / "s3c_stage1.token-lane.s3"
        s1_path = temp / "s3c_stage1.token-lane.compacted.s3"
        e0 = temp / "s3c-e0-token-lane"
        e1 = temp / "s3c-e1-compacted"
        e0_asm = temp / "s3c-e0-token-lane.s"
        e1_asm = temp / "s3c-e1-compacted.s"
        s0_path.write_bytes(s0)
        s1_path.write_bytes(s1)

        e0_build = _build(s0_path, e0, e0_asm)
        e1_build = _build(s1_path, e1, e1_asm)

        trivial_source = b"fn main() -> tryte:\n    return 7\n"
        trivial0 = _run_stage1(e0, trivial_source)
        trivial1 = _run_stage1(e1, trivial_source)
        expected_trivial = _expected_trivial_assembly(7)
        trivial0_pass = trivial0.returncode == 0 and trivial0.stderr == b"" and trivial0.stdout == expected_trivial
        trivial1_pass = trivial1.returncode == 0 and trivial1.stderr == b"" and trivial1.stdout == expected_trivial

        cells = {
            "E0_S0": _run_cell(e0, s0),
            "E0_S1": _run_cell(e0, s1),
            "E1_S0": _run_cell(e1, s0),
            "E1_S1": _run_cell(e1, s1),
        }

    boundaries_pass = all(bool(cell["fail_closed_boundary"]) for cell in cells.values())
    same_s0_ast = _same_input_ast(cells["E0_S0"], cells["E1_S0"])
    same_s1_ast = _same_input_ast(cells["E0_S1"], cells["E1_S1"])
    same_input_ast_pass = all(same_s0_ast.values()) and all(same_s1_ast.values())

    expected_events = {
        "E0_S0": int(matrix_static["E0_S0_events"]),
        "E0_S1": int(matrix_static["E0_S1_events"]),
        "E1_S0": int(matrix_static["E1_S0_events"]),
        "E1_S1": int(matrix_static["E1_S1_events"]),
    }
    event_guards = {
        name: _event_count_guard(cells[name], expected)
        for name, expected in expected_events.items()
    }
    event_counts_pass = all(event_guards.values())

    input_delta_e0 = _input_delta_guards(cells["E0_S0"], cells["E0_S1"])
    input_delta_e1 = _input_delta_guards(cells["E1_S0"], cells["E1_S1"])
    input_delta_pass = all(input_delta_e0.values()) and all(input_delta_e1.values())

    block_s0 = _block_guard(
        cells["E0_S0"], cells["E1_S0"],
        e0_full_events=expected_events["E0_S0"],
        e1_full_events=expected_events["E1_S0"],
    )
    block_s1 = _block_guard(
        cells["E0_S1"], cells["E1_S1"],
        e0_full_events=expected_events["E0_S1"],
        e1_full_events=expected_events["E1_S1"],
    )
    applicable_block_checks = [item for item in (block_s0, block_s1) if item["applicable"]]
    blocks_pass = all(item["pass"] is True for item in applicable_block_checks)

    semantic_pass = bool(
        trivial0_pass
        and trivial1_pass
        and boundaries_pass
        and same_input_ast_pass
        and event_counts_pass
        and input_delta_pass
        and blocks_pass
    )

    routes = list(capacity.get("routes", []))
    if not semantic_pass:
        status = "FAIL_NATIVE_COMPACTION_2X2_SEMANTIC_DIFFERENTIAL"
        next_gate = "REPAIR_REBASED_COMPACTION_OR_NATIVE_DIFFERENTIAL_MODEL"
    elif routes != ["NATIVE_TOKEN_LANE_THEN_COMPACTION_2X2"]:
        status = "PASS_NATIVE_COMPACTION_SEMANTICS_CAPACITY_ROUTE_REQUIRED"
        next_gate = str(routes[0]) if routes else "REVIEW_FULL_SOURCE_CAPACITY_PLAN"
    else:
        status = "PASS_NATIVE_COMPACTION_CANDIDATE"
        next_gate = "REBASE_PARAMETER_IR_V2_ON_TOKEN_LANE_COMPACTION_CHECKPOINT"

    result: dict[str, object] = {
        "schema": "s3.selfhost.compaction-after-token-lane-native-2x2.v1",
        "status": status,
        "native_evidence": True,
        "canonical_source_mutated": False,
        "canonical_commit_allowed": False,
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "compiler": compiler,
        },
        "sources": {
            "S0_token_lane_sha256": _sha256(s0),
            "S0_token_lane_bytes": len(s0),
            "S1_compacted_sha256": _sha256(s1),
            "S1_compacted_bytes": len(s1),
        },
        "builds": {"E0": e0_build, "E1": e1_build},
        "trivial": {
            "E0": "PASS" if trivial0_pass else "FAIL",
            "E1": "PASS" if trivial1_pass else "FAIL",
        },
        "cells": cells,
        "same_input_ast_guards": {"S0": same_s0_ast, "S1": same_s1_ast},
        "same_input_ast_pass": same_input_ast_pass,
        "expected_full_event_counts": expected_events,
        "capped_event_count_guards": event_guards,
        "event_counts_pass": event_counts_pass,
        "input_source_delta_guards": {"E0": input_delta_e0, "E1": input_delta_e1},
        "input_source_delta_pass": input_delta_pass,
        "block_shape_guards": {"S0": block_s0, "S1": block_s1},
        "block_shape_pass_when_applicable": blocks_pass,
        "semantic_compaction_pass": semantic_pass,
        "full_source_capacity_plan": capacity,
        "next": next_gate,
        "qualification_rule": (
            "Native PASS means the same-input AST observations agree, native capped "
            "event counts match the independent full-source model, textual source "
            "deltas are observed on both compilers, and block equality holds whenever "
            "both event streams fit completely. It never turns truncation-induced "
            "block drift into a pass and never promotes canonical source by itself."
        ),
        "general_emitter": "BLOCKED_IR_V2_INCOMPLETE",
        "self_emit": "NOT_STARTED",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
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
    parser.add_argument("--token-native-report", type=Path, default=DEFAULT_TOKEN_NATIVE_REPORT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = qualify(
        token_native_report_path=args.token_native_report,
        report_path=args.report,
    )
    print(f"REPORT={args.report.resolve()}")
    print(f"STATUS={result['status']}")
    print(f"SEMANTIC_COMPACTION_PASS={result['semantic_compaction_pass']}")
    print(f"SAME_INPUT_AST_PASS={result['same_input_ast_pass']}")
    print(f"EVENT_COUNTS_PASS={result['event_counts_pass']}")
    print(f"INPUT_SOURCE_DELTA_PASS={result['input_source_delta_pass']}")
    print(f"BLOCK_SHAPE_PASS_WHEN_APPLICABLE={result['block_shape_pass_when_applicable']}")
    print(f"CAPACITY_ROUTES={','.join(str(item) for item in result['full_source_capacity_plan']['routes'])}")
    print(f"NEXT={result['next']}")
    print("CANONICAL_SOURCE_MUTATED=False")
    print("STAGE2=NOT_STARTED")
    print("STAGE3=NOT_STARTED")
    return 0 if str(result["status"]).startswith("PASS_NATIVE_COMPACTION") else 2


if __name__ == "__main__":
    raise SystemExit(main())
