#!/usr/bin/env python3
"""Attribute the P9.2 UNKNOWN population without strengthening range analysis.

This is a research-only consumer of the validated P9 sidecar, the P9.1 result,
and its obligation ledger.  The ledger already records the complete P9.1
classification.  P9.3 verifies that the UNKNOWN denominator is exactly the
register-initialization class, then removes that existing P8 mechanism from
the P9 bounds/validity question.  It does not import production modules or
construct a new proof oracle.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


UNKNOWN_CLASSES = (
    "UNKNOWN_P8_REGISTER_INIT",
    "UNKNOWN_OBJECT_IDENTITY",
    "UNKNOWN_INDEX_IDENTITY",
    "UNKNOWN_LENGTH_IDENTITY",
    "UNKNOWN_ALIAS",
    "UNKNOWN_CALL_EFFECT",
    "UNKNOWN_MUTATION",
    "UNKNOWN_LIFETIME",
    "UNKNOWN_OVERFLOW",
    "UNKNOWN_CFG_PATH",
    "UNKNOWN_LOOP_CARRIED_FACT",
    "UNKNOWN_REFERENCE",
    "UNKNOWN_SLICE",
    "UNKNOWN_FAILURE_ORDER",
    "UNKNOWN_INSTRUCTION_LIMIT_INTERACTION",
    "UNKNOWN_OTHER",
)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _head(checkout: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _site_record(record: dict, dynamic_weight: int) -> dict:
    site_id = str(record["site_id"])
    if "id(" in site_id or "0x" in site_id:
        raise ValueError(f"non-structural site identity: {site_id}")
    return {
        "workload": record["workload"],
        "optimization": record["optimization"],
        "function": record["function"],
        "block": record["block"],
        "instruction_site": site_id,
        "opcode": record["opcode"],
        "dynamic_weight": dynamic_weight,
        "static_register_init_lines": int(
            record["native_line_counts"]["REGISTER_INITIALIZATION_CHECK"]
        ),
        "execution_count": int(record["execution_count"]),
        "current_check": "REGISTER_INITIALIZATION_CHECK",
        "why_unknown": (
            "P9.1 assigns this population to REGISTER_INITIALIZATION_CHECK; "
            "it is an existing P8 safety mechanism, not a P9 bounds/validity "
            "range fact."
        ),
        "possible_redundancy": "NOT_A_P9_BOUNDS_CLAIM",
        "counterexample": (
            "Range facts do not prove register initialization. Removing the "
            "check on that basis would conflate P8 observer/initialization "
            "semantics with P9 range validity."
        ),
        "minimum_required_proof": (
            "P8-specific observer-aware register-initialization proof with "
            "an exact native checked fallback; outside this P9.3 experiment."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-checkout", type=Path, required=True)
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--candidate-p9", type=Path, required=True)
    parser.add_argument("--candidate-p9-1", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    actual = _head(args.production_checkout)
    if actual != args.production_sha:
        raise SystemExit(
            f"TARGET_HEAD_MATCH=NO actual={actual} expected={args.production_sha}"
        )

    candidate_p9 = _load(args.candidate_p9)
    p9_1 = _load(args.candidate_p9_1)
    ledger = _load(args.candidate_p9_1.parent / "safety_obligation_ledger.json")

    model_total = int(candidate_p9["summary"]["modelled_dynamic_total"])
    if model_total != 289512:
        raise SystemExit(f"P9_3_BASELINE_IDENTITY=FAIL actual={model_total}")

    unknown_expected = int(p9_1["unknown_dynamic"])
    if float(p9_1["classification_coverage"]) != 1.0:
        raise SystemExit("P9_3_CLASSIFICATION_COVERAGE=FAIL")

    register_static = 0
    register_dynamic = 0
    register_sites = 0
    register_workloads: set[str] = set()
    by_workload: Counter[str] = Counter()
    by_opcode: Counter[str] = Counter()
    sites: list[dict] = []
    for record in ledger:
        static_lines = int(record["native_line_counts"].get("REGISTER_INITIALIZATION_CHECK", 0))
        if static_lines == 0:
            continue
        execution_count = int(record["execution_count"])
        dynamic_weight = static_lines * execution_count
        register_static += static_lines
        register_dynamic += dynamic_weight
        register_sites += 1
        register_workloads.add(str(record["workload"]))
        by_workload[str(record["workload"])] += dynamic_weight
        by_opcode[str(record["opcode"])] += dynamic_weight
        sites.append(_site_record(record, dynamic_weight))

    if register_dynamic != unknown_expected:
        raise SystemExit(
            "P9_3_UNKNOWN_IDENTITY=FAIL "
            f"register_init={register_dynamic} p9_1_unknown={unknown_expected}"
        )

    sites.sort(key=lambda row: (-row["dynamic_weight"], row["workload"], row["instruction_site"]))
    category_totals = {name: 0 for name in UNKNOWN_CLASSES}
    category_totals["UNKNOWN_P8_REGISTER_INIT"] = register_dynamic
    if sum(category_totals.values()) != unknown_expected:
        raise SystemExit("P9_3_UNKNOWN_PARTITION=FAIL")

    zero_category_rows = [
        {
            "name": name,
            "dynamic": category_totals[name],
            "classification": "NOT_OBSERVED_IN_P9_1_UNKNOWN_POPULATION",
            "p9_relevant": False,
        }
        for name in UNKNOWN_CLASSES
        if name != "UNKNOWN_P8_REGISTER_INIT"
    ]
    category_rows = [
        {
            "name": "UNKNOWN_P8_REGISTER_INIT",
            "dynamic": register_dynamic,
            "static": register_static,
            "sites": register_sites,
            "workloads": len(register_workloads),
            "classification": "OUT_OF_SCOPE_EXISTING_MECHANISM",
            "p9_relevant": False,
            "out_of_scope_for_p9_bounds": True,
            "check": "REGISTER_INITIALIZATION_CHECK",
            "hot": register_dynamic > 0,
            "cause": "P8_REGISTER_INITIALIZATION_EXISTING_MECHANISM",
            "proof_gap": "P9 range facts do not transport register-initialization state",
        },
        *zero_category_rows,
    ]

    top_sites = sites[:10]
    top_family = {
        "family": "UNKNOWN_P8_REGISTER_INIT",
        "dynamic_weight": register_dynamic,
        "share_of_total_unknown": register_dynamic / unknown_expected if unknown_expected else 0.0,
        "workload_count": len(register_workloads),
        "cause": "P8_REGISTER_INITIALIZATION_EXISTING_MECHANISM",
        "likely_required": True,
        "potentially_avoidable": False,
        "proof_cost": "OUT_OF_SCOPE_FOR_P9; requires the P8-specific safety proof boundary",
    }

    result = {
        "campaign": "P9_3_UNKNOWN_CAUSAL_ATTRIBUTION_V1",
        "status": "COMPLETE_RESEARCH_ONLY",
        "target_sha": args.production_sha,
        "target_is_main": False,
        "target_is_validated_correctness_candidate": True,
        "target_head_match": True,
        "target_main_sha": args.main_sha,
        "modelled_dynamic_total": model_total,
        "baseline_expected": 289512,
        "baseline_reproduced": True,
        "total_unknown_dynamic": unknown_expected,
        "unknown_classification_coverage": float(p9_1["classification_coverage"]),
        "unknown_partition_sum": sum(category_totals.values()),
        "unknown_classes": category_totals,
        "unknown_class_details": category_rows,
        "p8_register_init_unknown_static": register_static,
        "p8_register_init_unknown_sites": register_sites,
        "p8_register_init_unknown_dynamic": register_dynamic,
        "p8_register_init_unknown_workloads": sorted(register_workloads),
        "p8_register_init_dynamic_by_workload": dict(sorted(by_workload.items())),
        "p8_register_init_dynamic_by_opcode": dict(sorted(by_opcode.items())),
        "p9_relevant_unknown_dynamic": unknown_expected - register_dynamic,
        "inherently_required_dynamic": 0,
        "out_of_scope_existing_mechanism_dynamic": register_dynamic,
        "attribution_limit_only_dynamic": 0,
        "potentially_avoidable_unproven_dynamic": 0,
        "provably_avoidable_dynamic": 0,
        "max_theoretical_avoidable_dynamic": 0,
        "max_theoretical_share_of_model": 0.0,
        "top_unknown_sites": top_sites,
        "top_unknown_p9_relevant_sites": [],
        "top_unknown_families": [top_family],
        "top_unknown_p9_relevant_families": [],
        "concrete_redundant_example_found": False,
        "material_p9_class_found": False,
        "p9_3_selection": "NO_P9_BOUNDS_OPPORTUNITY",
        "p9_production_started": False,
        "p9_4_authorized_by_evidence": False,
        "p9_4_recommended_target": "NONE",
        "bounds_validity_line_status": "CLOSE",
        "next_global_optimization_question": "NO_NEW_TARGET_YET",
        "next_smallest_experiment": "NONE_WITHIN_P9_BOUNDS",
        "negative_results": [
            "UNKNOWN_DYNAMIC_IS_EXACTLY_P8_REGISTER_INIT",
            "NO_P9_RELEVANT_UNKNOWN_DYNAMIC_REMAINS",
            "NO_CONCRETE_REDUNDANT_P9_EXAMPLE",
            "NO_P9_4_GATE_SATISFIED",
        ],
        "production_code_changed": False,
        "benchmark_executed": False,
        "github_actions_executed": False,
        "shutdown_authorized": False,
        "provenance": "LOCAL_RESEARCH_ONLY_PENDING_PUBLICATION",
    }
    _write(args.output, result)
    print(json.dumps({
        "TARGET_HEAD_MATCH": True,
        "P9_3_BASELINE_REPRODUCED": True,
        "P9_3_BASELINE_ACTUAL": model_total,
        "TOTAL_UNKNOWN_DYNAMIC": unknown_expected,
        "UNKNOWN_CLASSIFICATION_COVERAGE": float(p9_1["classification_coverage"]),
        "P8_REGISTER_INIT_UNKNOWN_STATIC": register_static,
        "P8_REGISTER_INIT_UNKNOWN_DYNAMIC": register_dynamic,
        "P9_RELEVANT_UNKNOWN_DYNAMIC": unknown_expected - register_dynamic,
        "MAX_THEORETICAL_AVOIDABLE_DYNAMIC": 0,
        "P9_3_SELECTION": result["p9_3_selection"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
