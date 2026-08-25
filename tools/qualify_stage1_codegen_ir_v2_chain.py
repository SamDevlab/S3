"""Run prepared Stage1 IR-v2 candidate gates in fail-closed sequence.

The chain is read-only with respect to the canonical compiler source. It first
runs focused IR-v2 tooling tests and static storage/block/initializer preflight,
then qualifies compaction capacity and the packed parameter lane. After a real
parameter PASS it computes the native-derived next-phase budget and, when the
parameter report contains full provenance, also runs the exact report-gated
local-metadata candidate preflight.

Local preflight is routing evidence only: it never promotes source or starts a
native local qualification. The chain never starts Stage2/Stage3 or claims
self-hosting.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from tools.patch_stage1_codegen_ir_v2_locals import (
    LocalCandidateError,
    SOURCE as LOCAL_SOURCE,
)
from tools.plan_stage1_codegen_ir_v2_next import (
    DEFAULT_REPORT as DEFAULT_NEXT_PHASE_REPORT,
    build_plan as build_next_phase_plan,
)
from tools.preflight_stage1_codegen_ir_v2_locals import (
    DEFAULT_REPORT as DEFAULT_LOCAL_PREFLIGHT_REPORT,
    build_preflight as build_local_preflight,
)
from tools.preflight_stage1_codegen_ir_v2_static import (
    DEFAULT_REPORT as DEFAULT_STATIC_PREFLIGHT_REPORT,
    run as run_static_preflight,
)
from tools.qualify_stage1_codegen_ir_v2_capacity import (
    DEFAULT_REPORT as DEFAULT_CAPACITY_REPORT,
    qualify as qualify_capacity,
)
from tools.qualify_stage1_codegen_ir_v2_parameters import (
    DEFAULT_REPORT as DEFAULT_PARAMETER_REPORT,
    qualify as qualify_parameters,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHAIN_REPORT = (
    ROOT
    / "reports"
    / "selfhost"
    / "stage1"
    / "codegen-ir-v2-native-chain.json"
)
TOOLING_TEST_FILES = (
    "tests/test_stage1_codegen_ir_contract.py",
    "tests/test_stage1_codegen_ir_capacity_tools.py",
    "tests/test_stage1_codegen_ir_v2_parameters.py",
    "tests/test_stage1_codegen_ir_v2_next_plan.py",
    "tests/test_stage1_codegen_ir_v2_storage_reuse.py",
    "tests/test_stage1_codegen_ir_v2_block_capacity.py",
    "tests/test_stage1_array_initializer_audit.py",
    "tests/test_stage1_codegen_ir_v2_static_preflight.py",
    "tests/test_stage1_codegen_ir_v2_local_metadata.py",
    "tests/test_stage1_codegen_ir_v2_locals.py",
    "tests/test_stage1_codegen_ir_v2_chain.py",
)


def _write(path: Path, value: dict[str, object]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _run_tooling_tests() -> dict[str, object]:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            *TOOLING_TEST_FILES,
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
        "files": list(TOOLING_TEST_FILES),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _has_full_parameter_provenance(parameter: dict[str, object] | None) -> bool:
    if not isinstance(parameter, dict):
        return False
    candidate = parameter.get("candidate")
    self_source = parameter.get("self_source")
    qualification = parameter.get("qualification")
    return bool(
        isinstance(candidate, dict)
        and isinstance(candidate.get("source_sha256"), str)
        and isinstance(candidate.get("source_bytes"), int)
        and isinstance(self_source, dict)
        and isinstance(self_source.get("audit"), dict)
        and isinstance(qualification, dict)
    )


def run_chain(
    *,
    capacity_report_path: Path,
    parameter_report_path: Path,
    next_phase_report_path: Path,
    chain_report_path: Path,
    static_preflight_report_path: Path = DEFAULT_STATIC_PREFLIGHT_REPORT,
    local_preflight_report_path: Path = DEFAULT_LOCAL_PREFLIGHT_REPORT,
    run_tooling_tests: bool = True,
) -> dict[str, object]:
    tooling_tests = (
        _run_tooling_tests()
        if run_tooling_tests
        else {
            "status": "SKIPPED_BY_TEST_HARNESS",
            "returncode": None,
            "files": list(TOOLING_TEST_FILES),
        }
    )
    tooling_pass = tooling_tests.get("status") == "PASS" or not run_tooling_tests

    static_preflight: dict[str, object] | None = None
    if tooling_pass:
        static_preflight = run_static_preflight(report_path=static_preflight_report_path)
    static_pass = bool(
        static_preflight is not None
        and static_preflight.get("native_chain_allowed") is True
    )

    capacity: dict[str, object] | None = None
    if tooling_pass and static_pass:
        capacity = qualify_capacity(
            report_path=capacity_report_path,
            run_contract_tests=True,
        )
    capacity_pass = bool(
        capacity is not None
        and capacity.get("qualification", {}).get("capacity_candidate")
        == "PASS_NATIVE_CANDIDATE"
        and capacity.get("qualification", {}).get("canonical_commit_allowed") is True
    )

    parameter: dict[str, object] | None = None
    if capacity_pass:
        parameter = qualify_parameters(
            capacity_report_path=capacity_report_path,
            report_path=parameter_report_path,
        )

    parameter_pass = bool(
        parameter is not None
        and parameter.get("qualification", {}).get("parameter_ir_v2_candidate")
        == "PASS_NATIVE_CANDIDATE"
    )

    next_phase = build_next_phase_plan(parameter if parameter_pass else None)
    _write(next_phase_report_path, next_phase)

    local_preflight: dict[str, object]
    if parameter_pass and _has_full_parameter_provenance(parameter):
        try:
            local_preflight = build_local_preflight(
                parameter,
                canonical_source=LOCAL_SOURCE.read_text(encoding="utf-8"),
            )
            _write(local_preflight_report_path, local_preflight)
        except (LocalCandidateError, OSError, ValueError) as error:
            local_preflight = {
                "schema": "s3.selfhost.codegen-ir-v2-locals-static-preflight.v1",
                "status": "BLOCKED_LOCAL_PREFLIGHT_ERROR",
                "native_evidence": False,
                "canonical_source_mutated": False,
                "local_native_qualification_allowed": False,
                "canonical_commit_allowed": False,
                "error": str(error),
                "next": "REPAIR_LOCAL_PREFLIGHT_BEFORE_NATIVE_LOCAL_QUALIFICATION",
                "stage2": "NOT_STARTED",
                "stage3": "NOT_STARTED",
                "full_self_hosting": False,
            }
            _write(local_preflight_report_path, local_preflight)
    elif parameter_pass:
        # Existing unit tests intentionally use a compact synthetic parameter
        # report. Do not weaken production validation just to make that harness
        # look like native provenance.
        local_preflight = {
            "status": "NOT_RUN_TEST_HARNESS_INCOMPLETE_PARAMETER_REPORT",
            "native_evidence": False,
            "canonical_source_mutated": False,
            "local_native_qualification_allowed": False,
            "canonical_commit_allowed": False,
            "next": next_phase.get("next"),
        }
    else:
        local_preflight = {
            "status": "NOT_RUN_PARAMETER_GATE_NOT_PASS",
            "native_evidence": False,
            "canonical_source_mutated": False,
            "local_native_qualification_allowed": False,
            "canonical_commit_allowed": False,
            "next": next_phase.get("next"),
        }

    if not tooling_pass:
        chain_status = "BLOCKED_AT_TOOLING_TESTS"
    elif not static_pass:
        chain_status = "BLOCKED_AT_STATIC_PREFLIGHT"
    elif not capacity_pass:
        chain_status = "BLOCKED_AT_CAPACITY_CANDIDATE"
    elif not parameter_pass:
        chain_status = "BLOCKED_AT_PARAMETER_CANDIDATE"
    else:
        chain_status = "PASS_THROUGH_PARAMETER_CANDIDATE"

    block_preflight = (
        static_preflight.get("block_capacity_audit", {})
        if static_preflight is not None
        else {}
    )
    parameter_storage_preflight = (
        static_preflight.get("parameter_candidate_storage_reuse_audit", {})
        if static_preflight is not None
        else {}
    )
    local_candidate = local_preflight.get("local_candidate", {})
    local_projection = local_preflight.get("native_headroom_projection", {}).get(
        "projected_candidate_counts", {}
    )

    result = {
        "schema": "s3.selfhost.codegen-ir-v2-native-chain.v8",
        "canonical_source_mutated": False,
        "tooling_tests": tooling_tests,
        "static_preflight": {
            "status": (
                "PASS"
                if static_pass
                else "FAIL" if static_preflight is not None else "NOT_RUN"
            ),
            "report": str(static_preflight_report_path.resolve()),
            "storage_reuse": (
                static_preflight.get("storage_reuse_audit", {}).get("status")
                if static_preflight is not None
                else None
            ),
            "event_overwrite_frontier": (
                static_preflight.get("storage_reuse_audit", {}).get(
                    "event_overwrite_frontier"
                )
                if static_preflight is not None
                else None
            ),
            "parameter_candidate_storage_reuse": parameter_storage_preflight.get(
                "status"
            ),
            "parameter_candidate_event_overwrite_frontier": parameter_storage_preflight.get(
                "event_overwrite_frontier"
            ),
            "block_capacity_design": block_preflight.get("status"),
            "projected_parameter_blocks": block_preflight.get("projected_parameter_blocks"),
            "static_strict_control_budget": block_preflight.get(
                "strict_additional_control_budget"
            ),
            "array_initializers": (
                static_preflight.get("array_initializer_audit", {}).get("status")
                if static_preflight is not None
                else None
            ),
            "zero_initializer_items": (
                static_preflight.get("array_initializer_audit", {}).get(
                    "zero_initializer_items"
                )
                if static_preflight is not None
                else None
            ),
        },
        "capacity_gate": {
            "status": "PASS" if capacity_pass else "FAIL" if capacity is not None else "NOT_RUN",
            "report": str(capacity_report_path.resolve()),
        },
        "parameter_gate": {
            "status": (
                "PASS" if parameter_pass else "FAIL" if parameter is not None else "NOT_RUN"
            ),
            "report": str(parameter_report_path.resolve()),
        },
        "next_phase_budget": {
            "status": next_phase["status"],
            "local_ir_v2_design_possible": next_phase.get(
                "local_ir_v2_design_possible", False
            ),
            "local_ir_v2_start_allowed": next_phase["local_ir_v2_start_allowed"],
            "local_candidate_control_preflight_required": next_phase.get(
                "local_candidate_control_preflight_required", False
            ),
            "block_capacity_expansion_required": next_phase.get(
                "block_capacity_expansion_required_before_local_metadata", False
            ),
            "unified_value_namespace_start_allowed": next_phase.get(
                "unified_value_namespace_start_allowed", False
            ),
            "next": next_phase.get("next"),
            "report": str(next_phase_report_path.resolve()),
        },
        "local_candidate_preflight": {
            "status": local_preflight.get("status"),
            "report": str(local_preflight_report_path.resolve()),
            "native_parameter_evidence_consumed": local_preflight.get(
                "native_parameter_evidence_consumed", False
            ),
            "required_records": (
                local_candidate.get("required_records_including_candidate_self_source")
                if isinstance(local_candidate, dict)
                else None
            ),
            "selected_capacity": (
                local_candidate.get("selected_capacity")
                if isinstance(local_candidate, dict)
                else None
            ),
            "projected_events": (
                local_projection.get("events")
                if isinstance(local_projection, dict)
                else None
            ),
            "projected_values": (
                local_projection.get("values")
                if isinstance(local_projection, dict)
                else None
            ),
            "projected_blocks": (
                local_projection.get("blocks")
                if isinstance(local_projection, dict)
                else None
            ),
            "projected_calls": (
                local_projection.get("calls")
                if isinstance(local_projection, dict)
                else None
            ),
            "native_qualification_allowed": local_preflight.get(
                "local_native_qualification_allowed", False
            ),
            "next": local_preflight.get("next"),
            "canonical_commit_allowed": False,
        },
        "chain_status": chain_status,
        "canonical_commit_allowed": False,
        "canonical_commit_reason": (
            "Candidate chain intentionally never mutates/promotes the canonical source. "
            "Local preflight is routing evidence only; review native reports first."
        ),
        "general_emitter": "BLOCKED_IR_V2_INCOMPLETE",
        "self_emit": "NOT_STARTED",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }

    _write(chain_report_path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--static-preflight-report", type=Path, default=DEFAULT_STATIC_PREFLIGHT_REPORT
    )
    parser.add_argument("--capacity-report", type=Path, default=DEFAULT_CAPACITY_REPORT)
    parser.add_argument("--parameter-report", type=Path, default=DEFAULT_PARAMETER_REPORT)
    parser.add_argument("--next-phase-report", type=Path, default=DEFAULT_NEXT_PHASE_REPORT)
    parser.add_argument("--local-preflight-report", type=Path, default=DEFAULT_LOCAL_PREFLIGHT_REPORT)
    parser.add_argument("--chain-report", type=Path, default=DEFAULT_CHAIN_REPORT)
    args = parser.parse_args(argv)

    result = run_chain(
        static_preflight_report_path=args.static_preflight_report,
        capacity_report_path=args.capacity_report,
        parameter_report_path=args.parameter_report,
        next_phase_report_path=args.next_phase_report,
        local_preflight_report_path=args.local_preflight_report,
        chain_report_path=args.chain_report,
        run_tooling_tests=True,
    )
    print(f"CHAIN_REPORT={args.chain_report.resolve()}")
    print(f"TOOLING_TESTS={result['tooling_tests']['status']}")
    print(f"STATIC_PREFLIGHT={result['static_preflight']['status']}")
    print(f"STORAGE_REUSE={result['static_preflight']['storage_reuse']}")
    print(f"EVENT_OVERWRITE_FRONTIER={result['static_preflight']['event_overwrite_frontier']}")
    print(
        "PARAMETER_CANDIDATE_STORAGE_REUSE="
        f"{result['static_preflight']['parameter_candidate_storage_reuse']}"
    )
    print(
        "PARAMETER_CANDIDATE_EVENT_OVERWRITE_FRONTIER="
        f"{result['static_preflight']['parameter_candidate_event_overwrite_frontier']}"
    )
    print(f"BLOCK_CAPACITY_DESIGN={result['static_preflight']['block_capacity_design']}")
    print(f"PROJECTED_PARAMETER_BLOCKS={result['static_preflight']['projected_parameter_blocks']}")
    print(f"STATIC_STRICT_CONTROL_BUDGET={result['static_preflight']['static_strict_control_budget']}")
    print(f"ARRAY_INITIALIZERS={result['static_preflight']['array_initializers']}")
    print(f"ZERO_INITIALIZER_ITEMS={result['static_preflight']['zero_initializer_items']}")
    print(f"CAPACITY_GATE={result['capacity_gate']['status']}")
    print(f"PARAMETER_GATE={result['parameter_gate']['status']}")
    print(f"NEXT_PHASE_BUDGET={result['next_phase_budget']['status']}")
    print(f"LOCAL_IR_V2_DESIGN_POSSIBLE={result['next_phase_budget']['local_ir_v2_design_possible']}")
    print(f"LOCAL_IR_V2_START_ALLOWED={result['next_phase_budget']['local_ir_v2_start_allowed']}")
    print(
        "LOCAL_CANDIDATE_CONTROL_PREFLIGHT_REQUIRED="
        f"{result['next_phase_budget']['local_candidate_control_preflight_required']}"
    )
    print(f"BLOCK_CAPACITY_EXPANSION_REQUIRED={result['next_phase_budget']['block_capacity_expansion_required']}")
    print(f"UNIFIED_VALUE_NAMESPACE_START_ALLOWED={result['next_phase_budget']['unified_value_namespace_start_allowed']}")
    print(f"LOCAL_STATIC_PREFLIGHT={result['local_candidate_preflight']['status']}")
    print(f"LOCAL_REQUIRED_RECORDS={result['local_candidate_preflight']['required_records']}")
    print(f"LOCAL_SELECTED_CAPACITY={result['local_candidate_preflight']['selected_capacity']}")
    print(f"LOCAL_PROJECTED_EVENTS={result['local_candidate_preflight']['projected_events']}")
    print(f"LOCAL_PROJECTED_VALUES={result['local_candidate_preflight']['projected_values']}")
    print(f"LOCAL_PROJECTED_BLOCKS={result['local_candidate_preflight']['projected_blocks']}")
    print(f"LOCAL_PROJECTED_CALLS={result['local_candidate_preflight']['projected_calls']}")
    print(
        "LOCAL_NATIVE_QUALIFICATION_ALLOWED="
        f"{result['local_candidate_preflight']['native_qualification_allowed']}"
    )
    print(f"LOCAL_NEXT={result['local_candidate_preflight']['next']}")
    print(f"NEXT={result['next_phase_budget']['next']}")
    print(f"CHAIN_STATUS={result['chain_status']}")
    print("CANONICAL_SOURCE_MUTATED=False")
    print("STAGE2=NOT_STARTED")
    print("STAGE3=NOT_STARTED")
    return 0 if result["chain_status"] == "PASS_THROUGH_PARAMETER_CANDIDATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
