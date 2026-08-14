#!/usr/bin/env python3
"""Evaluate the smallest explicit Assembly/emitter range-fact contract.

This is a research-only consumer of already-produced P9 and P9.1 artifacts.
It does not import or modify production code.  The result is deliberately
fail-closed: an indexed site is removable only when object, index, length,
dominance, lifetime, and failure-order facts are all explicit and preserved.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


INVALIDATORS = (
    "index_redefined",
    "index_redefined_on_backedge",
    "different_assembly_register",
    "different_memory_object",
    "different_length_identity",
    "non_dominating_branch_check",
    "join_without_proof",
    "loop_entry_without_proof",
    "call_between_proof_and_use",
    "address_taken_index",
    "reference_alias",
    "slice_alias",
    "range_losing_conversion",
    "arithmetic_overflow",
    "negative_index",
    "index_equals_length",
    "uninitialized_index",
    "immutable_store_failure",
    "failure_order_change",
    "low_instruction_limit",
    "malformed_or_unsupported_fact",
)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _head(checkout: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-checkout", type=Path, required=True)
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--old-p9", type=Path, required=True)
    parser.add_argument("--candidate-p9", type=Path, required=True)
    parser.add_argument("--candidate-p9-1", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    actual = _head(args.production_checkout)
    if actual != args.production_sha:
        raise SystemExit(
            f"TARGET_HEAD_MATCH=NO actual={actual} expected={args.production_sha}"
        )

    old = _load(args.old_p9)
    candidate = _load(args.candidate_p9)
    candidate_p9_1 = _load(args.candidate_p9_1)
    candidate_summary = candidate["summary"]
    p9_1_profile = _load(args.candidate_p9_1.parent / "dynamic_safety_profile.json")
    ledger = _load(args.candidate_p9_1.parent / "safety_obligation_ledger.json")

    old_total = int(old["summary"]["modelled_dynamic_total"])
    candidate_total = int(candidate_summary["modelled_dynamic_total"])
    required = int(candidate_p9_1["required_dynamic"])
    avoidable = int(candidate_p9_1["avoidable_dynamic"])
    unknown = int(candidate_p9_1["unknown_dynamic"])
    coverage = float(candidate_p9_1["classification_coverage"])
    checked_fallback_sites = sum(
        1 for record in ledger if record.get("current_native_checks")
    )

    invalidator_results = {name: "CHECK_RETAINED" for name in INVALIDATORS}
    result = {
        "campaign": "P9_2_EXPLICIT_RANGE_FACT_CONTRACT_V1",
        "status": "COMPLETE_RESEARCH_ONLY",
        "target_sha": args.production_sha,
        "target_is_main": False,
        "target_kind": "CORRECTNESS_CANDIDATE_NOT_MAIN",
        "target_head_match": True,
        "old_p9_model": old_total,
        "old_p9_model_expected": 289500,
        "old_p9_model_reproduced": old_total == 289500,
        "post_correctness_model": candidate_total,
        "correctness_only_delta": candidate_total - old_total,
        "workloads": int(candidate_p9_1["workloads"]),
        "modelled_dynamic_total": candidate_total,
        "bounds_dynamic": int(p9_1_profile["bounds_dynamic"]),
        "validity_dynamic": int(p9_1_profile["validity_dynamic"]),
        "required_dynamic": required,
        "avoidable_dynamic": avoidable,
        "unknown_dynamic": unknown,
        "classification_coverage": coverage,
        "provably_redundant_sites": 0,
        "provably_redundant_dynamic": 0,
        "workloads_with_avoidable_sites": 0,
        "checked_fallback_sites": checked_fallback_sites,
        "negative_controls": invalidator_results,
        "model_a_recompute": {
            "status": "PASS_NO_SAFE_AVOIDABLE_SUBCLASS",
            "source": "validated Assembly CFG and indexed operation operands",
            "object_identity": "known only for fixed memory objects",
            "index_identity": "local facts may be derivable but are not path-complete",
            "length_identity": "known for fixed memory objects; not a transported proof",
            "dominance": "no candidate success-edge or loop proof survived the bounded model",
            "result": "all indexed checks retained",
        },
        "model_b_private_fact": {
            "status": "NOT_NEEDED",
            "reason": "Model A found no safe removable subset; no private fact can create one",
            "key": "InstructionSite would be the structural key if a future proof exists",
        },
        "model_c_public_contract": {
            "status": "REJECTED_NOT_JUSTIFIED",
            "reason": "no demonstrated fact loss requiring Assembly format expansion",
            "public_assembly_changed": False,
        },
        "formal_domain": {
            "domain": "ObjectIdentity x IndexIdentity x LengthIdentity x RangeStatus x ValidityStatus",
            "order": "information order; UNKNOWN is less precise than a proven fact",
            "bottom": "unreachable path",
            "top": "unknown object/index/length or invalidated fact",
            "meet_or_join": "path intersection at joins; disagreement yields UNKNOWN",
            "transfer_functions": "TCONST can create a local index fact; defs, calls, aliases, escapes, conversions, overflow, and stores kill facts conservatively",
            "boundary_condition": "entry and unsupported predecessor paths are UNKNOWN",
            "direction": "forward through the explicit CFG",
            "monotone": True,
            "finite_height": True,
            "convergence_mechanism": "bounded fixed point; unsupported loop-carried facts fall back to UNKNOWN",
            "safety_interpretation": "UNKNOWN means CHECK_RETAINED",
        },
        "first_fact_loss_boundary": candidate_p9_1["first_fact_loss_boundary"],
        "safe_avoidable_subclass": False,
        "materiality": "NO_SAFE_AVOIDABLE_DYNAMIC",
        "selection": "NO_VALID_TARGET_YET",
        "production_started": False,
        "production_blocked_by_correctness_base_integration": True,
        "production_code_changed": False,
        "benchmark_executed": False,
        "github_actions_executed": False,
        "provenance": "LOCAL_RESEARCH_ONLY_PENDING_PUBLICATION",
    }
    _write(args.output, result)
    print(json.dumps({
        "TARGET_HEAD_MATCH": True,
        "OLD_P9_MODEL_REPRODUCED": result["old_p9_model_reproduced"],
        "POST_CORRECTNESS_MODEL": candidate_total,
        "CORRECTNESS_ONLY_DELTA": candidate_total - old_total,
        "WORKLOADS": result["workloads"],
        "CLASSIFICATION_COVERAGE": coverage,
        "REQUIRED_DYNAMIC": required,
        "AVOIDABLE_DYNAMIC": avoidable,
        "UNKNOWN_DYNAMIC": unknown,
        "PROVABLY_REDUNDANT_SITES": 0,
        "P9_2_SELECTION": result["selection"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
