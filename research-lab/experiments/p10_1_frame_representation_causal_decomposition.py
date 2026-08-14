#!/usr/bin/env python3
"""Research-only decomposition of the broad P10 frame class.

The exact P9 sidecar exposes two trustworthy frame measurements: logical
frame-value lines and the remaining FRAME_CANONICALIZATION lines.  It also
exposes stack residency as an overlay.  This probe preserves that boundary:
it never calls stack residency a spill, never invents liveness/pressure, and
does not construct a production allocation or frame-layout change.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _head(checkout: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def _is_ancestor(ancestor: str, checkout: Path) -> bool:
    return subprocess.run(
        ["git", "-C", str(checkout), "merge-base", "--is-ancestor", ancestor, "HEAD"],
        check=False,
    ).returncode == 0


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _site_row(workload: str, optimization: str, site_id: str, meta: dict,
              family: str, dynamic_weight: int, stack_resident: bool) -> dict:
    if "id(" in site_id or "0x" in site_id:
        raise ValueError(f"non-structural site identity: {site_id}")
    locations = meta.get("physical_registers", {})
    location = "STACK_RESIDENT" if stack_resident else ",".join(
        f"v{register}->{physical}" for register, physical in sorted(locations.items())
        if physical is not None
    )
    return {
        "workload": workload,
        "optimization": optimization,
        "function": meta["function"],
        "block": meta["block"],
        "instruction_index": int(meta["instruction_index"]),
        "assembly_opcode": meta["opcode"],
        "site": site_id,
        "dynamic_weight": dynamic_weight,
        "current_cause": family,
        "stack_or_register": location or "UNKNOWN_NOT_SEPARATELY_MEASURED",
        "load_or_store_or_address": "UNKNOWN_NOT_SEPARATELY_MEASURED",
        "live_pressure": "UNKNOWN_NOT_MEASURED",
        "call_context": "UNKNOWN_NOT_MEASURED",
        "first_causal_boundary": "FRAME_LAYOUT_OR_EMITTER_LOCAL_DECISION_NOT_SEPARATED",
        "avoidability_status": "ATTRIBUTION_LIMIT_ONLY",
        "live_before": "UNKNOWN_NOT_MEASURED",
        "live_after": "UNKNOWN_NOT_MEASURED",
        "virtual_register": meta.get("registers", "UNKNOWN_NOT_MEASURED"),
        "physical_location_before": location or "UNKNOWN_NOT_MEASURED",
        "physical_location_after": location or "UNKNOWN_NOT_MEASURED",
        "frame_slot": "UNKNOWN_NOT_MEASURED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-checkout", type=Path, required=True)
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--research-head-start", required=True)
    parser.add_argument("--candidate-p9", type=Path, required=True)
    parser.add_argument("--p10", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    actual = _head(args.production_checkout)
    if actual != args.production_sha:
        raise SystemExit(
            f"TARGET_HEAD_MATCH=NO actual={actual} expected={args.production_sha}"
        )

    candidate = _load(args.candidate_p9)
    p10 = _load(args.p10)
    if int(candidate["summary"]["modelled_dynamic_total"]) != 289512:
        raise SystemExit("P10_1_BASELINE_IDENTITY=FAIL")
    if int(p10["baseline_actual"]) != 289512 or not p10["baseline_reproduced"]:
        raise SystemExit("P10 baseline is not a reproduced exact input")
    if p10["correctness_candidate_sha"] != args.production_sha:
        raise SystemExit("P10 candidate identity mismatch")
    if int(p10["primary_class_totals"]["FRAME_CANONICALIZATION"]["modelled_dynamic"]) != 39081:
        raise SystemExit("FRAME_REPRESENTATION_BROAD_IDENTITY=FAIL")

    subfamilies = Counter()
    static_subfamilies = Counter()
    workloads_by_subfamily: dict[str, set[str]] = {"LOGICAL_FRAME_VALUE_TRAFFIC": set(), "OTHER_FRAME_REPRESENTATION": set()}
    top_sites: list[dict] = []
    stack_dynamic = 0
    stack_static = 0
    frame_dynamic = 0
    frame_static = 0
    tmov_dynamic = 0
    tmov_static = 0
    frame_site_count = 0

    for workload, workload_data in candidate["workloads"].items():
        for optimization, data in workload_data["optimizations"].items():
            dynamic_counts = data["dynamic_site_counts"]
            for site_id, meta in data["static_sites"].items():
                frame_lines = int(meta["class_counts"].get("FRAME_CANONICALIZATION", 0))
                if not frame_lines:
                    continue
                frame_site_count += 1
                execution_count = int(dynamic_counts.get(site_id, 0))
                value_lines = int(meta.get("frame_value_line_count", 0))
                stack_lines = int(meta.get("stack_frame_value_line_count", 0))
                if value_lines > frame_lines or stack_lines > value_lines:
                    raise SystemExit(f"FRAME_SUBPARTITION=FAIL site={site_id}")
                other_lines = frame_lines - value_lines
                frame_static += frame_lines
                frame_dynamic += frame_lines * execution_count
                static_subfamilies["LOGICAL_FRAME_VALUE_TRAFFIC"] += value_lines
                static_subfamilies["OTHER_FRAME_REPRESENTATION"] += other_lines
                subfamilies["LOGICAL_FRAME_VALUE_TRAFFIC"] += value_lines * execution_count
                subfamilies["OTHER_FRAME_REPRESENTATION"] += other_lines * execution_count
                workloads_by_subfamily["LOGICAL_FRAME_VALUE_TRAFFIC"].add(workload)
                workloads_by_subfamily["OTHER_FRAME_REPRESENTATION"].add(workload)
                stack_static += stack_lines
                stack_dynamic += stack_lines * execution_count
                if meta["opcode"] == "TMOV":
                    tmov_static += frame_lines
                    tmov_dynamic += frame_lines * execution_count
                if value_lines:
                    top_sites.append(_site_row(
                        workload, optimization, site_id, meta,
                        "LOGICAL_FRAME_VALUE_TRAFFIC", value_lines * execution_count,
                        bool(meta.get("stack_resident_registers")),
                    ))
                if other_lines:
                    top_sites.append(_site_row(
                        workload, optimization, site_id, meta,
                        "OTHER_FRAME_REPRESENTATION", other_lines * execution_count,
                        bool(meta.get("stack_resident_registers")),
                    ))

    if frame_static != int(p10["primary_class_totals"]["FRAME_CANONICALIZATION"]["static_count"]):
        raise SystemExit("FRAME_STATIC_RECONCILIATION=FAIL")
    if frame_dynamic != 39081 or sum(subfamilies.values()) != 39081:
        raise SystemExit("FRAME_DYNAMIC_RECONCILIATION=FAIL")
    if stack_dynamic != int(candidate["summary"]["stack_resident_frame_value_modelled_dynamic"]):
        raise SystemExit("STACK_OVERLAY_RECONCILIATION=FAIL")

    top_sites.sort(key=lambda row: (-row["dynamic_weight"], row["workload"], row["site"], row["current_cause"]))
    top_families = []
    for family, dynamic in sorted(subfamilies.items(), key=lambda item: (-item[1], item[0])):
        top_families.append({
            "family": family,
            "static": static_subfamilies[family],
            "dynamic": dynamic,
            "share_of_frame_class": dynamic / 39081,
            "workloads": len(workloads_by_subfamily[family]),
            "first_causal_boundary": "FRAME_LAYOUT_OR_EMITTER_LOCAL_DECISION_NOT_SEPARATED",
            "semantically_required": 0,
            "abi_required": 0,
            "safety_required": 0,
            "implementation_choice": 0,
            "attribution_limit_only": dynamic,
            "avoidability": "ATTRIBUTION_LIMIT_ONLY",
            "counterfactual": "NONE_CONSTRUCTED; sidecar lacks exact live intervals and an equivalent alternative",
        })

    result = {
        "campaign": "P10_1_FRAME_REPRESENTATION_CAUSAL_DECOMPOSITION_V1",
        "status": "COMPLETE_RESEARCH_ONLY",
        "initial_main": args.main_sha,
        "correctness_candidate_sha": args.production_sha,
        "research_head_start": args.research_head_start,
        "target_sha": args.production_sha,
        "target_is_main": False,
        "target_is_validated_correctness_candidate": True,
        "target_head_match": True,
        "target_main_ancestry": _is_ancestor(args.main_sha, args.production_checkout),
        "target_checkout": str(args.production_checkout),
        "production_imports": "NONE; JSON-only sidecar consumer",
        "baseline_expected": 289512,
        "baseline_reproduced": True,
        "baseline_actual": 289512,
        "workloads": 15,
        "frame_representation_broad_expected": 39081,
        "frame_representation_broad_actual": frame_dynamic,
        "causal_classification_coverage": sum(subfamilies.values()) / frame_dynamic,
        "avoidability_classification_coverage": 1.0,
        "subfamilies": top_families,
        "top_25_frame_representation_sites": top_sites[:25],
        "logical_frame_value_dynamic": subfamilies["LOGICAL_FRAME_VALUE_TRAFFIC"],
        "logical_frame_value_static": static_subfamilies["LOGICAL_FRAME_VALUE_TRAFFIC"],
        "physical_stack_value_dynamic": stack_dynamic,
        "physical_stack_value_static": stack_static,
        "true_spill_store_dynamic": 0,
        "true_spill_reload_dynamic": 0,
        "true_spill_causality_established": False,
        "true_reload_causality_established": False,
        "non_spill_stack_dynamic": "UNKNOWN_NOT_ESTABLISHED",
        "abi_save_dynamic": 0,
        "abi_restore_dynamic": 0,
        "parameter_home_dynamic": "NOT_SEPARATELY_MEASURED",
        "return_value_dynamic": "NOT_SEPARATELY_MEASURED",
        "frame_address_calculation_dynamic": "NOT_SEPARATELY_MEASURED",
        "stack_slot_access_dynamic": "NOT_SEPARATELY_MEASURED",
        "register_to_frame_materialization_dynamic": "NOT_SEPARATELY_MEASURED",
        "frame_to_register_materialization_dynamic": "NOT_SEPARATELY_MEASURED",
        "tmov_copy_materialization_static": tmov_static,
        "tmov_copy_materialization_dynamic": tmov_dynamic,
        "representation_required_dynamic": 0,
        "representation_implementation_choice_dynamic": 0,
        "other_frame_dynamic": subfamilies["OTHER_FRAME_REPRESENTATION"],
        "provably_required_dynamic": 0,
        "provably_avoidable_dynamic": 0,
        "potentially_avoidable_unproven_dynamic": 0,
        "attribution_limit_only_dynamic": frame_dynamic,
        "max_theoretical_removable_dynamic": 0,
        "max_theoretical_share_of_model": 0.0,
        "max_theoretical_share_of_frame_class": 0.0,
        "max_register_pressure_observed": "UNKNOWN_NOT_MEASURED",
        "sites_pressure_exceeds_capacity": "UNKNOWN_NOT_MEASURED",
        "workloads_with_pressure_exceedance": "UNKNOWN_NOT_MEASURED",
        "pressure_causality_proven": False,
        "oracle_used": False,
        "oracle_scope": "NONE; no exact bounded allocation model constructed",
        "oracle_solution_exact": "NOT_APPLICABLE",
        "current_traffic": frame_dynamic,
        "oracle_minimum_traffic": "UNKNOWN_NOT_COMPUTED",
        "oracle_gap": "UNKNOWN_NOT_COMPUTED",
        "concrete_spill_example_found": False,
        "concrete_non_spill_avoidable_example_found": False,
        "p10_1_selection": "NO_VALID_TARGET_YET",
        "target_subclass": "NONE",
        "target_dynamic": 0,
        "target_workloads": 0,
        "first_causal_boundary": "FRAME_LAYOUT_OR_EMITTER_LOCAL_DECISION_NOT_SEPARATED",
        "frame_line_status": "CLOSE",
        "next_experiment": "NONE_WITHIN_FRAME",
        "next_discriminating_question": "NONE_WITHOUT_CAUSAL_EXAMPLE",
        "production_optimization_started": False,
        "correctness_integration_status": "STILL_BLOCKED_BY_PROVENANCE",
        "correctness_integrated": False,
        "lab_consistency": "PENDING_VALIDATION",
        "remote_write_provenance": "PENDING_VALIDATION",
        "github_actions_executed": False,
        "benchmark_executed": False,
        "shutdown_authorized": False,
        "negative_results": [
            "STACK_RESIDENCY_IS_NOT_TRUE_SPILL_PROOF",
            "TRUE_SPILL_CAUSALITY_NOT_ESTABLISHED",
            "LOGICAL_FRAME_LOAD_STORE_SPLIT_NOT_SEPARATELY_MEASURED",
            "LIVE_PRESSURE_NOT_PRESENT_IN_SIDEcar",
            "NO_VALID_COUNTERFACTUAL_ALLOCATION_MODEL",
            "TMOV_COPY_SEMANTICS_NOT_REOPENED",
        ],
    }
    _write(args.output, result)
    print(json.dumps({
        "TARGET_HEAD_MATCH": True,
        "BASELINE_REPRODUCED": True,
        "BASELINE_ACTUAL": 289512,
        "FRAME_REPRESENTATION_BROAD_ACTUAL": frame_dynamic,
        "CAUSAL_CLASSIFICATION_COVERAGE": result["causal_classification_coverage"],
        "AVOIDABILITY_CLASSIFICATION_COVERAGE": result["avoidability_classification_coverage"],
        "LOGICAL_FRAME_VALUE_DYNAMIC": result["logical_frame_value_dynamic"],
        "PHYSICAL_STACK_VALUE_DYNAMIC": stack_dynamic,
        "TRUE_SPILL_DYNAMIC": 0,
        "TMOV_COPY_MATERIALIZATION_DYNAMIC": tmov_dynamic,
        "P10_1_SELECTION": result["p10_1_selection"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
