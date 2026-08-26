"""Low-cost hosted preflight for the final Stage1 certification pipeline.

This command deliberately does not run a native Stage1 build, self-emit, T4, or
Stage2/Stage3. It validates the final certification contracts, Python syntax,
and focused hosted gate tests before expensive native work. It then reports
which content-bound evidence files are still absent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "stage1-final-certification-tooling-preflight.json"
)

CONTRACTS = {
    "final_capacity": (
        "reports/selfhost/stage1/final-capacity-contract.json",
        "s3.selfhost.stage1-final-capacity-contract.v1",
    ),
    "final_semantic_ir_verifier": (
        "reports/selfhost/stage1/final-semantic-ir-verifier-contract.json",
        "s3.selfhost.stage1-final-semantic-ir-verifier-contract.v3",
    ),
    "final_self_emit": (
        "reports/selfhost/stage1/final-self-emit-contract.json",
        "s3.selfhost.stage1-final-self-emit-contract.v1",
    ),
    "stage1_certification": (
        "reports/selfhost/stage1/stage1-certification-gate-contract.json",
        "s3.selfhost.stage1-certification-gate-contract.v3",
    ),
    "stage2_stage3": (
        "reports/selfhost/stage2/stage2-stage3-fixed-point-contract.json",
        "s3.selfhost.stage2-stage3-fixed-point-contract.v3",
    ),
}

TOOL_FILES = [
    "tools/qualify_stage1_final_capacity.py",
    "tools/qualify_stage1_final_semantic_ir_verifier.py",
    "tools/qualify_stage1_final_self_emit.py",
    "tools/qualify_stage1_final_self_emit_static.py",
    "tools/emit_stage1_certification_gate.py",
    "tools/stage1_certification_evidence.py",
    "tools/selfhost_static_link.py",
    "tools/qualify_stage2_stage3_certified_strict.py",
    "tools/qualify_stage2_stage3_certified_static.py",
]

TEST_FILES = [
    "tests/test_stage1_final_capacity.py",
    "tests/test_stage1_final_semantic_ir_verifier.py",
    "tests/test_stage1_final_self_emit.py",
    "tests/test_emit_stage1_certification_gate.py",
    "tests/test_stage1_certification_evidence.py",
    "tests/test_stage2_stage3_certified_strict.py",
    "tests/test_selfhost_static_link.py",
    "tests/test_stage2_stage3_certified_static.py",
    "tests/test_stage1_reference_semantic_value_inventory.py",
    "tests/test_stage1_reference_bootstrap_opcodes.py",
    "tests/test_stage1_codegen_fixture_opcode_coverage.py",
    "tests/test_stage1_reference_storage_inventory.py",
    "tests/test_stage1_semantic_def_use_requirements.py",
]

FINAL_EVIDENCE = {
    "native_source_coverage": "reports/selfhost/stage1/packed-token-lane-native-full-coverage.json",
    "reference_opcode_inventory": "reports/selfhost/stage1/reference-bootstrap-opcode-inventory.json",
    "hosted_fixture_opcode_coverage": "reports/selfhost/stage1/stage1-codegen-fixture-opcode-coverage.json",
    "native_codegen_fixtures": "reports/selfhost/stage1/stage1-codegen-complete-fixtures-native.json",
    "final_capacity": "reports/selfhost/stage1/stage1-final-capacity.json",
    "final_semantic_ir_verifier": "reports/selfhost/stage1/stage1-final-semantic-ir-verifier.json",
    "final_self_emit": "reports/selfhost/stage1/stage1-final-self-emit.json",
}


class PreflightError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
        text=True,
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
    }


def _validate_contracts() -> dict[str, Any]:
    entries: dict[str, Any] = {}
    all_pass = True
    for name, (relative, expected_schema) in CONTRACTS.items():
        path = ROOT / relative
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
            actual_schema = document.get("schema") if isinstance(document, dict) else None
            passed = actual_schema == expected_schema
            error = None if passed else f"expected {expected_schema!r}, got {actual_schema!r}"
        except (OSError, json.JSONDecodeError) as exc:
            document = None
            actual_schema = None
            passed = False
            error = str(exc)
        all_pass = all_pass and passed
        entries[name] = {
            "path": relative,
            "expected_schema": expected_schema,
            "actual_schema": actual_schema,
            "sha256": _sha256(path) if path.is_file() else None,
            "status": "PASS" if passed else "FAIL",
            "error": error,
        }
    return {"status": "PASS" if all_pass else "FAIL", "contracts": entries}


def _evidence_readiness() -> dict[str, Any]:
    entries: dict[str, Any] = {}
    missing: list[str] = []
    for role, relative in FINAL_EVIDENCE.items():
        path = ROOT / relative
        exists = path.is_file()
        if not exists:
            missing.append(role)
        entries[role] = {
            "path": relative,
            "exists": exists,
            "sha256": _sha256(path) if exists else None,
        }
    return {
        "all_present": not missing,
        "missing_roles": missing,
        "evidence": entries,
    }


def run_preflight(*, run_tests: bool = True) -> dict[str, Any]:
    contracts = _validate_contracts()
    py_compile = _run([sys.executable, "-m", "py_compile", *TOOL_FILES])
    tests = {
        "status": "SKIPPED",
        "command": None,
        "returncode": None,
        "stdout": "",
        "stderr": "",
    }
    if run_tests and contracts["status"] == "PASS" and py_compile["status"] == "PASS":
        tests = _run([sys.executable, "-m", "pytest", "-q", *TEST_FILES])

    tooling_pass = (
        contracts["status"] == "PASS"
        and py_compile["status"] == "PASS"
        and (not run_tests or tests["status"] == "PASS")
    )
    readiness = _evidence_readiness()
    if not tooling_pass:
        status = "BLOCKED_FINAL_CERTIFICATION_TOOLING"
        next_step = "REPAIR_FINAL_CERTIFICATION_TOOLING_BEFORE_NATIVE_WORK"
    elif readiness["all_present"]:
        status = "PASS_TOOLING_ALL_FINAL_EVIDENCE_PRESENT"
        next_step = "EMIT_STAGE1_CERTIFICATION_GATE_V2"
    else:
        status = "PASS_TOOLING_FINAL_EVIDENCE_PENDING"
        next_step = "RUN_OR_COMPLETE_MISSING_HOSTED_AND_NATIVE_EVIDENCE_IN_DEPENDENCY_ORDER"

    return {
        "schema": "s3.selfhost.stage1-final-certification-tooling-preflight.v1",
        "status": status,
        "native_execution_evidence": False,
        "runs_t4": False,
        "starts_stage2": False,
        "starts_stage3": False,
        "contracts": contracts,
        "python_compile": py_compile,
        "focused_hosted_tests": tests,
        "final_evidence_readiness": readiness,
        "qualification": {
            "tooling_preflight": "PASS" if tooling_pass else "FAIL",
            "stage1_certified_for_stage2": False,
            "full_self_hosting": False,
            "next": next_step,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args(argv)
    result = run_preflight(run_tests=not args.skip_tests)
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"TOOLING_PREFLIGHT={result['qualification']['tooling_preflight']}")
    print("MISSING_FINAL_EVIDENCE=" + ",".join(result["final_evidence_readiness"]["missing_roles"]))
    print("NATIVE_EXECUTION_EVIDENCE=False")
    print("T4_RUN=NO")
    print("STAGE2_STARTED=NO")
    print("STAGE3_STARTED=NO")
    print(f"NEXT={result['qualification']['next']}")
    return 0 if result["qualification"]["tooling_preflight"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
