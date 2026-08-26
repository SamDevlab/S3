"""Bind a final Stage1 semantic-IR report to native call high-water evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEMANTIC_IR = ROOT / "reports" / "selfhost" / "stage1" / "stage1-final-semantic-ir-verifier.json"
DEFAULT_CALLS = ROOT / "reports" / "selfhost" / "stage1" / "stage1-native-call-reconciliation.json"
DEFAULT_CONTRACT = ROOT / "reports" / "selfhost" / "stage1" / "semantic-ir-native-call-boundary-contract.json"
DEFAULT_REPORT = ROOT / "reports" / "selfhost" / "stage1" / "stage1-final-semantic-ir-verifier-call-bound.json"


class SemanticIRCallBoundaryError(RuntimeError):
    pass


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise SemanticIRCallBoundaryError(f"{label} is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise SemanticIRCallBoundaryError(f"{label} is invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise SemanticIRCallBoundaryError(f"{label} must be a JSON object")
    return value


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _binding(document: dict[str, Any], key: str) -> tuple[str, int]:
    value = document.get(key)
    if not isinstance(value, dict) or not isinstance(value.get("sha256"), str):
        raise SemanticIRCallBoundaryError(f"report lacks {key} SHA binding")
    size = value.get("bytes")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise SemanticIRCallBoundaryError(f"report lacks valid {key} byte binding")
    return value["sha256"], size


def bind_reports(
    semantic: dict[str, Any],
    calls: dict[str, Any],
    *,
    contract: dict[str, Any],
    semantic_sha256: str | None = None,
    calls_sha256: str | None = None,
) -> dict[str, Any]:
    if contract.get("schema") != "s3.selfhost.stage1-semantic-ir-native-call-boundary-contract.v1":
        raise SemanticIRCallBoundaryError("semantic/call boundary contract schema mismatch")
    if semantic.get("schema") != contract.get("semantic_ir_schema"):
        raise SemanticIRCallBoundaryError("final semantic IR report schema mismatch")
    if calls.get("schema") != contract.get("native_call_schema"):
        raise SemanticIRCallBoundaryError("native call reconciliation schema mismatch")

    qualification = semantic.get("qualification")
    if not isinstance(qualification, dict):
        raise SemanticIRCallBoundaryError("semantic IR report lacks qualification")
    required_semantic = {
        "semantic_ir": "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET",
        "verifier_v2": "PASS",
        "general_emitter": "PASS_BOOTSTRAP_REQUIRED_OPCODES",
    }
    for key, expected in required_semantic.items():
        if qualification.get(key) != expected:
            raise SemanticIRCallBoundaryError(f"semantic IR prerequisite {key} is not {expected!r}")

    if calls.get("status") != "PASS_NATIVE_CURRENT_SOURCE_CALL_RECONCILIATION" or calls.get("native_evidence") is not True:
        raise SemanticIRCallBoundaryError("native call reconciliation is not PASS native evidence")
    call_qualification = calls.get("qualification")
    if not isinstance(call_qualification, dict):
        raise SemanticIRCallBoundaryError("native call reconciliation lacks qualification")
    if call_qualification.get("native_call_capacity") != "PASS" or call_qualification.get("native_call_argument_capacity") != "PASS":
        raise SemanticIRCallBoundaryError("native call capacities are not PASS")
    if call_qualification.get("semantic_call_linkage_complete_from_this_report_alone") is not False:
        raise SemanticIRCallBoundaryError("native call capacity report must not claim semantic linkage authority")

    semantic_source = _binding(semantic, "canonical_source")
    call_source = _binding(calls, "canonical_source")
    semantic_stage1 = _binding(semantic, "stage1")
    call_stage1 = _binding(calls, "stage1")
    if semantic_source != call_source:
        raise SemanticIRCallBoundaryError("semantic IR and native call reports use different canonical source")
    if semantic_stage1 != call_stage1:
        raise SemanticIRCallBoundaryError("semantic IR and native call reports use different Stage1 artifact")

    counts = semantic.get("inventory_counts")
    native = calls.get("native")
    audit = native.get("audit") if isinstance(native, dict) else None
    if not isinstance(counts, dict) or not isinstance(audit, dict):
        raise SemanticIRCallBoundaryError("semantic/native call inventory is malformed")
    semantic_calls = counts.get("calls")
    semantic_args = counts.get("call_arguments")
    native_calls = audit.get("ir_call_count")
    native_args = audit.get("ir_call_arg_pool_count")
    values = (semantic_calls, semantic_args, native_calls, native_args)
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in values):
        raise SemanticIRCallBoundaryError("call inventory counts must be non-negative integers")
    if semantic_calls != native_calls:
        raise SemanticIRCallBoundaryError(
            f"semantic IR calls disagree with native high-water: {semantic_calls} != {native_calls}"
        )
    if semantic_args != native_args:
        raise SemanticIRCallBoundaryError(
            f"semantic IR call arguments disagree with native high-water: {semantic_args} != {native_args}"
        )

    result = dict(semantic)
    result["authority"] = contract["authority"]["output_authority"]
    result["native_call_capacity_dependency"] = {
        "status": "PASS_NATIVE_CURRENT_SOURCE_CALL_RECONCILIATION",
        "report_sha256": calls_sha256,
        "same_canonical_source": True,
        "same_stage1_artifact": True,
        "semantic_calls_equal_native_high_water": True,
        "semantic_call_arguments_equal_native_high_water": True,
        "calls": native_calls,
        "call_arguments": native_args,
    }
    evidence = dict(result.get("evidence_inputs", {}))
    evidence["unbound_semantic_ir_sha256"] = semantic_sha256
    evidence["native_call_reconciliation_sha256"] = calls_sha256
    result["evidence_inputs"] = evidence
    result["qualification"] = dict(qualification)
    result["qualification"]["native_call_capacity_boundary"] = "PASS"
    result["qualification"]["stage2_allowed_from_this_report_alone"] = False
    result["qualification"]["full_self_hosting"] = False
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semantic-ir", type=Path, default=DEFAULT_SEMANTIC_IR)
    parser.add_argument("--native-calls", type=Path, default=DEFAULT_CALLS)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    try:
        semantic_path = args.semantic_ir.resolve()
        calls_path = args.native_calls.resolve()
        result = bind_reports(
            _load(semantic_path, "semantic IR report"),
            _load(calls_path, "native call reconciliation"),
            contract=_load(args.contract.resolve(), "semantic/call boundary contract"),
            semantic_sha256=_sha(semantic_path),
            calls_sha256=_sha(calls_path),
        )
    except (OSError, SemanticIRCallBoundaryError) as error:
        parser.exit(2, f"Stage1 semantic IR/native call boundary blocked: {error}\n")

    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(f"REPORT={destination}")
    print(f"AUTHORITY={result['authority']}")
    print("NATIVE_CALL_CAPACITY_BOUNDARY=PASS")
    print(f"CALLS={result['native_call_capacity_dependency']['calls']}")
    print(f"CALL_ARGUMENTS={result['native_call_capacity_dependency']['call_arguments']}")
    print("STAGE2_ALLOWED_FROM_THIS_REPORT_ALONE=False")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
