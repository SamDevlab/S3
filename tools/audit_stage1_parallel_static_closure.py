"""Run every host/static PR #268 parallel-closure audit in one fail-closed pass.

This entry point performs no native build, no source transform, no Stage2
creation and no T4. It exists so the independent design work prepared while a
Linux scratch candidate is running can be validated together later.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.audit_stage1_call_terminator_contracts import audit as audit_call_terminator
from tools.audit_stage1_checkpoint_consistency import audit as audit_checkpoint
from tools.audit_stage1_codegen_ir_v2_value_namespace import audit as audit_value_namespace
from tools.audit_stage1_compact_block_capacity import audit as audit_blocks
from tools.audit_stage1_instruction_stream_contract import audit as audit_instructions
from tools.audit_stage1_ir_closure_dependencies import build_matrix
from tools.audit_stage1_local_namespace_rebase import audit as audit_local_rebase
from tools.audit_stage2_serialized_ir_envelope import audit as audit_stage2_envelope

ROOT = Path(__file__).resolve().parents[1]
STAGE1 = ROOT / "reports" / "selfhost" / "stage1"
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
REQUIREMENTS = STAGE1 / "semantic-ir-requirements.json"
VALUE_CONTRACT = STAGE1 / "codegen-ir-v2-value-namespace-contract.json"
LOCAL_TRANSFORM = ROOT / "tools" / "patch_stage1_codegen_ir_v2_locals.py"
INSTRUCTION_CONTRACT = STAGE1 / "ir-v2-instruction-stream-contract.json"
CALL_CONTRACT = STAGE1 / "ir-v2-call-linkage-contract.json"
TERMINATOR_CONTRACT = STAGE1 / "ir-v2-terminator-contract.json"
STAGE2_CONTRACT = STAGE1 / "stage2-serialized-ir-envelope-contract.json"
FINAL_REPORT = STAGE1 / "FINAL_STAGE1_REPORT.md"
HANDOFF = STAGE1 / "FINAL_AUTONOMOUS_HANDOFF.txt"
BLOCKER = STAGE1 / "GENERAL_EMITTER_CLOSURE_BLOCKER_20260826.md"
DEFAULT_REPORT = STAGE1 / "parallel-static-closure-report.json"

EXPECTED = {
    "compact_blocks": {"STATIC_COMPACT_BLOCK_CAPACITY_CONTRACT_PASS"},
    "dependency_matrix": {"STATIC_PARALLEL_WORKSTREAM_MATRIX_PASS"},
    "checkpoint": {
        "CURRENT_CHECKPOINT_IDENTIFIED_HISTORICAL_HANDOFFS_PRESENT",
        "CURRENT_CHECKPOINT_DOCUMENTS_CONSISTENT",
    },
    "value_namespace": {"STATIC_VALUE_NAMESPACE_DESIGN_PASS"},
    "local_namespace": {
        "LOCAL_TRANSFORM_REBASE_REQUIRED",
        "LOCAL_TRANSFORM_NAMESPACE_CONSISTENT",
    },
    "instruction_stream": {"STATIC_INSTRUCTION_STREAM_DESIGN_PASS"},
    "call_terminator": {"STATIC_CALL_TERMINATOR_DESIGN_PASS"},
    "stage2_envelope": {"STATIC_STAGE2_ENVELOPE_DESIGN_PASS_FAIL_CLOSED"},
}


def run() -> dict[str, Any]:
    source_bytes = SOURCE.read_bytes()
    source = source_bytes.decode("utf-8")
    requirements = json.loads(REQUIREMENTS.read_text(encoding="utf-8"))
    value_contract = json.loads(VALUE_CONTRACT.read_text(encoding="utf-8"))
    instruction_contract = json.loads(INSTRUCTION_CONTRACT.read_text(encoding="utf-8"))
    call_contract = json.loads(CALL_CONTRACT.read_text(encoding="utf-8"))
    terminator_contract = json.loads(TERMINATOR_CONTRACT.read_text(encoding="utf-8"))
    stage2_contract = json.loads(STAGE2_CONTRACT.read_text(encoding="utf-8"))
    local_transform = LOCAL_TRANSFORM.read_text(encoding="utf-8")

    results: dict[str, dict[str, Any]] = {
        "compact_blocks": audit_blocks(source),
        "dependency_matrix": build_matrix(requirements),
        "checkpoint": audit_checkpoint(
            source_bytes=source_bytes,
            requirements=requirements,
            final_report=FINAL_REPORT.read_text(encoding="utf-8"),
            handoff=HANDOFF.read_text(encoding="utf-8"),
            blocker=BLOCKER.read_text(encoding="utf-8"),
        ),
        "value_namespace": audit_value_namespace(source, value_contract),
        "local_namespace": audit_local_rebase(
            source=source,
            local_transform=local_transform,
            value_contract=value_contract,
        ),
        "instruction_stream": audit_instructions(requirements, instruction_contract),
        "call_terminator": audit_call_terminator(
            requirements,
            call_contract,
            terminator_contract,
        ),
        "stage2_envelope": audit_stage2_envelope(requirements, stage2_contract),
    }

    gates = {
        name: result.get("status") in EXPECTED[name]
        for name, result in results.items()
    }
    all_expected = all(gates.values())
    return {
        "schema": "s3.selfhost.stage1-parallel-static-closure.v1",
        "status": (
            "STATIC_PARALLEL_CLOSURE_PREPARED"
            if all_expected
            else "STATIC_PARALLEL_CLOSURE_RECONCILIATION_REQUIRED"
        ),
        "native_evidence": False,
        "canonical_source_mutated": False,
        "results": {
            name: {
                "status": result.get("status"),
                "expected": sorted(EXPECTED[name]),
                "gate": gates[name],
            }
            for name, result in results.items()
        },
        "expected_rebase_blockers": {
            "local_namespace": results["local_namespace"].get("status")
            == "LOCAL_TRANSFORM_REBASE_REQUIRED",
            "historical_handoffs": bool(
                results["checkpoint"].get("historical_or_stale_handoffs")
            ),
        },
        "native_actions_performed": 0,
        "stage2_created": False,
        "stage3_started": False,
        "t4_runs": 0,
        "full_self_hosting": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = run()
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    for name, gate in result["results"].items():
        print(f"{name.upper()}={gate['status']}")
    print("NATIVE_ACTIONS_PERFORMED=0")
    print("STAGE2_CREATED=False")
    print("T4_RUNS=0")
    return 0 if result["status"] == "STATIC_PARALLEL_CLOSURE_PREPARED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
