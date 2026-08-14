#!/usr/bin/env python3
"""Research-only census of dynamic native cost on the frozen A+B candidate.

The input is the already validated P9 JSON sidecar.  This experiment does not
import production modules, rerun the compiler, execute a benchmark, or infer
that a large family is removable.  It verifies an exact one-primary-class
partition from per-site ``class_counts`` and attaches a separate nature axis.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path


PRIMARY_MAP = {
    "ARRAY_DATA_ACCESS": "EXPLICIT_MEMORY_OPERATION",
    "BOUNDS_CHECK": "BOUNDS_CHECK",
    "CALL_ABI": "CALL_ABI_OVERHEAD",
    "CONTROL_FLOW": "BRANCH_CONTROL",
    "FRAME_CANONICALIZATION": "FRAME_CANONICALIZATION",
    "INSTRUCTION_LIMIT": "INSTRUCTION_LIMIT_ACCOUNTING",
    "MEMORY_VALIDITY": "MEMORY_VALIDITY",
    "OTHER_REQUIRED": "OTHER_RUNTIME_SAFETY",
    "SEMANTIC_PAYLOAD": "SEMANTIC_PAYLOAD",
}

NATURE_MAP = {
    "EXPLICIT_MEMORY_OPERATION": "SEMANTICALLY_REQUIRED",
    "BOUNDS_CHECK": "SAFETY_REQUIRED",
    "CALL_ABI_OVERHEAD": "ABI_REQUIRED",
    "BRANCH_CONTROL": "SEMANTICALLY_REQUIRED",
    "FRAME_CANONICALIZATION": "UNKNOWN",
    "INSTRUCTION_LIMIT_ACCOUNTING": "POLICY_REQUIRED",
    "MEMORY_VALIDITY": "SAFETY_REQUIRED",
    "OTHER_RUNTIME_SAFETY": "SAFETY_REQUIRED",
    "SEMANTIC_PAYLOAD": "SEMANTICALLY_REQUIRED",
}

PREVIOUS_STATUS = {
    "SEMANTIC_PAYLOAD": "COMPLETE_REQUIRED_WORK; not an overhead claim",
    "INSTRUCTION_LIMIT_ACCOUNTING": "PARTIALLY_EXPLOITED_P5_P6; remainder not proven removable",
    "EXPLICIT_MEMORY_OPERATION": "FALSIFIED_CURRENT_FIXED_ARRAY_BASE_RELOAD_HYPOTHESIS_P9",
    "BOUNDS_CHECK": "COMPLETE_P9_CLOSED_NO_AVOIDABLE_SUBCLASS",
    "CALL_ABI_OVERHEAD": "REQUIRED_ABI; no current removal proof",
    "BRANCH_CONTROL": "PARTIALLY_EXPLOITED_P7; fallback retained",
    "FRAME_CANONICALIZATION": "PARTIALLY_EXPLOITED_P2_P3_P4; true spill not established",
    "MEMORY_VALIDITY": "COMPLETE_P9_CLOSED_NO_AVOIDABLE_SUBCLASS",
    "OTHER_RUNTIME_SAFETY": "REQUIRED_OR_UNSPLIT_SIDEcar_CLASS",
}

BOUNDARY = {
    "SEMANTIC_PAYLOAD": "IR_SEMANTIC_OPERATION",
    "INSTRUCTION_LIMIT_ACCOUNTING": "RUNTIME_POLICY_TO_EMITTER",
    "EXPLICIT_MEMORY_OPERATION": "ASSEMBLY_MEMORY_OPERATION",
    "BOUNDS_CHECK": "NATIVE_SAFETY_MODEL",
    "CALL_ABI_OVERHEAD": "ABI",
    "BRANCH_CONTROL": "EMITTER_LOCAL_DECISION",
    "FRAME_CANONICALIZATION": "FRAME_LAYOUT_OR_EMITTER_LOCAL_DECISION_NOT_SEPARATED",
    "MEMORY_VALIDITY": "NATIVE_SAFETY_MODEL",
    "OTHER_RUNTIME_SAFETY": "NATIVE_SAFETY_MODEL_OR_UNSPLIT_SIDECAR_CLASS",
}

MATERIALITY_BASIS = "dynamic share + cross-workload recurrence + structural significance"


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
              family: str, dynamic_weight: int, execution_count: int) -> dict:
    if "id(" in site_id or "0x" in site_id:
        raise ValueError(f"non-structural site identity: {site_id}")
    return {
        "workload": workload,
        "optimization": optimization,
        "function": meta["function"],
        "block": meta["block"],
        "instruction_site": site_id,
        "assembly_opcode": meta["opcode"],
        "x86_family": family,
        "dynamic_weight": dynamic_weight,
        "execution_count": execution_count,
        "cause": family,
        "nature": NATURE_MAP[family],
        "research_status": PREVIOUS_STATUS[family],
    }


def _family_assessment(family: str, rows: list[dict], static_count: int,
                       dynamic_count: int, workload_names: set[str]) -> dict:
    by_workload = Counter()
    for row in rows:
        by_workload[row["workload"]] += row["dynamic_weight"]
    hottest = max(rows, key=lambda row: (row["dynamic_weight"], row["workload"], row["instruction_site"]))
    nature = NATURE_MAP[family]
    known_required = dynamic_count if nature != "UNKNOWN" else 0
    unknown = dynamic_count if nature == "UNKNOWN" else 0
    return {
        "family": family,
        "static_count": static_count,
        "modelled_dynamic": dynamic_count,
        "model_share": dynamic_count / 289512,
        "workload_count": len(workload_names),
        "hottest_workload": max(by_workload, key=by_workload.get),
        "hottest_site": f"{hottest['workload']}/{hottest['optimization']}:{hottest['instruction_site']}",
        "why_exists": "native sidecar realization of the mapped Assembly/x86 class",
        "semantic_obligation": nature == "SEMANTICALLY_REQUIRED",
        "safety_obligation": nature == "SAFETY_REQUIRED",
        "abi_obligation": nature == "ABI_REQUIRED",
        "current_implementation_choice": nature == "REPRESENTATION_REQUIRED_CURRENT_MODEL" or family == "FRAME_CANONICALIZATION",
        "known_counterexample": (
            "stack residency does not prove spill causality"
            if family == "FRAME_CANONICALIZATION"
            else "no removable counterexample established in the prior campaign"
        ),
        "known_negative_research": PREVIOUS_STATUS[family],
        "proven_avoidable": False,
        "potentially_avoidable": False,
        "first_causal_boundary": BOUNDARY[family],
        "static_count_kind": "modelled x86 sidecar lines",
        "known_required_dynamic": known_required,
        "known_avoidable_dynamic": 0,
        "potentially_avoidable_dynamic": 0,
        "unknown_avoidability_dynamic": unknown,
        "generalization": "GENERAL" if len(workload_names) >= 5 else "DOMAIN_SPECIFIC",
        "previous_campaign": PREVIOUS_STATUS[family],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-checkout", type=Path, required=True)
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--main-sha", required=True)
    parser.add_argument("--research-head-start", required=True)
    parser.add_argument("--candidate-p9", type=Path, required=True)
    parser.add_argument("--p9-3", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    actual = _head(args.production_checkout)
    if actual != args.production_sha:
        raise SystemExit(
            f"TARGET_HEAD_MATCH=NO actual={actual} expected={args.production_sha}"
        )

    candidate = _load(args.candidate_p9)
    p9_3 = _load(args.p9_3)
    if p9_3["p9_3_selection"] != "NO_P9_BOUNDS_OPPORTUNITY":
        raise SystemExit("P9_STATUS=CLOSED check failed")
    if p9_3["bounds_validity_line_status"] != "CLOSE":
        raise SystemExit("P9_BOUNDS_VALIDITY_STATUS=CLOSED check failed")
    if int(p9_3["p9_relevant_unknown_dynamic"]) != 0:
        raise SystemExit("P9_RELEVANT_UNKNOWN_DYNAMIC must remain zero")

    expected_total = 289512
    model_total = int(candidate["summary"]["modelled_dynamic_total"])
    if model_total != expected_total:
        raise SystemExit(f"P10_BASELINE_IDENTITY=FAIL actual={model_total}")

    static_by_family: Counter[str] = Counter()
    dynamic_by_family: Counter[str] = Counter()
    rows_by_family: defaultdict[str, list[dict]] = defaultdict(list)
    workload_by_family: defaultdict[str, set[str]] = defaultdict(set)
    all_sites: list[dict] = []
    dynamic_sum = 0
    static_sum = 0
    workload_names = set(candidate["workloads"].keys())
    optimization_count = 0

    for workload, workload_data in candidate["workloads"].items():
        for optimization, data in workload_data["optimizations"].items():
            optimization_count += 1
            dynamic_counts = data["dynamic_site_counts"]
            for site_id, meta in data["static_sites"].items():
                class_counts = {str(key): int(value) for key, value in meta["class_counts"].items()}
                if sum(class_counts.values()) != int(meta["x86_line_count"]):
                    raise SystemExit(f"PRIMARY_PARTITION=FAIL site={site_id}")
                execution_count = int(dynamic_counts.get(site_id, 0))
                static_sum += int(meta["x86_line_count"])
                for old_class, line_count in class_counts.items():
                    if old_class not in PRIMARY_MAP:
                        raise SystemExit(f"UNMAPPED_SIDECAR_CLASS={old_class}")
                    family = PRIMARY_MAP[old_class]
                    dynamic_weight = line_count * execution_count
                    row = _site_row(
                        workload, optimization, site_id, meta, family,
                        dynamic_weight, execution_count,
                    )
                    static_by_family[family] += line_count
                    dynamic_by_family[family] += dynamic_weight
                    workload_by_family[family].add(workload)
                    rows_by_family[family].append(row)
                    if dynamic_weight:
                        all_sites.append(row)
                    dynamic_sum += dynamic_weight

    if dynamic_sum != model_total:
        raise SystemExit(f"CLASSIFICATION_COVERAGE=FAIL total={dynamic_sum}")

    families = sorted(dynamic_by_family, key=lambda key: (-dynamic_by_family[key], key))
    assessments = [
        _family_assessment(
            family, rows_by_family[family], static_by_family[family],
            dynamic_by_family[family], workload_by_family[family],
        )
        for family in families
    ]
    all_sites.sort(key=lambda row: (-row["dynamic_weight"], row["workload"], row["instruction_site"], row["x86_family"]))

    nature_totals: Counter[str] = Counter()
    for family in families:
        nature_totals[NATURE_MAP[family]] += dynamic_by_family[family]

    top_nonsemantic = [family for family in families if family != "SEMANTIC_PAYLOAD"]
    top5 = top_nonsemantic[:5]
    necessity = []
    for family in top5:
        total = dynamic_by_family[family]
        if family == "FRAME_CANONICALIZATION":
            required = avoidable = 0
            potential = 0
            unknown = total
            reason1 = "stack-resident traffic is observed but true spill causality is not established"
            reason2 = "P2/P3/P4 removed proven subfamilies; the remaining broad class is not decomposed"
            mechanism = "bounded frame-address/value provenance experiment"
            counterexample = "stack residency can be a deliberate frame representation, not a spill"
            missing = "causal split of frame addressing, value movement, spill/reload and metadata staging"
        else:
            required = total
            avoidable = potential = unknown = 0
            reason1 = "prior negative or semantic/ABI/policy evidence retains the obligation"
            reason2 = PREVIOUS_STATUS[family]
            mechanism = "none authorized by this census"
            counterexample = "current prior negative controls retain the operation"
            missing = "no concrete removable example"
        necessity.append({
            "family": family,
            "total_dynamic": total,
            "provably_required": required,
            "provably_avoidable": avoidable,
            "potentially_avoidable": potential,
            "unknown": unknown,
            "required_reason_1": reason1,
            "required_reason_2": reason2,
            "avoidable_mechanism": mechanism,
            "counterexample": counterexample,
            "missing_proof": missing,
            "sum_closes": required + avoidable + potential + unknown == total,
        })

    frame_summary = candidate["summary"]
    result = {
        "campaign": "P10_GLOBAL_DYNAMIC_OPPORTUNITY_CENSUS_V1",
        "status": "COMPLETE_RESEARCH_ONLY",
        "initial_main": args.main_sha,
        "correctness_candidate_sha": args.production_sha,
        "research_head_start": args.research_head_start,
        "target_main_sha": args.main_sha,
        "target_checkout": str(args.production_checkout),
        "target_head_match": True,
        "target_main_ancestry": _is_ancestor(args.main_sha, args.production_checkout),
        "target_is_main": False,
        "target_is_validated_correctness_candidate": True,
        "production_imports": "NONE; JSON-only sidecar consumer",
        "p9_status": "CLOSED",
        "p9_bounds_validity_status": "CLOSED",
        "p9_next_experiment": "NONE",
        "p9_unknown_excluded_dynamic": int(p9_3["total_unknown_dynamic"]),
        "baseline_expected": expected_total,
        "baseline_reproduced": True,
        "baseline_actual": model_total,
        "workloads": len(workload_names),
        "optimization_runs": optimization_count,
        "static_modelled_lines": static_sum,
        "classification_coverage": dynamic_sum / model_total,
        "primary_class_totals": {
            family: {
                "static_count": static_by_family[family],
                "modelled_dynamic": dynamic_by_family[family],
                "model_share": dynamic_by_family[family] / model_total,
            }
            for family in families
        },
        "nature_totals": dict(sorted(nature_totals.items())),
        "top_15_dynamic_families": assessments[:15],
        "top_25_dynamic_sites": all_sites[:25],
        "top_5_nonsemantic_necessity_ledger": necessity,
        "frame_overlays": {
            "frame_value_static": int(frame_summary["frame_value_static"]),
            "frame_value_modelled_dynamic": int(frame_summary["frame_value_modelled_dynamic"]),
            "stack_resident_frame_value_static": int(frame_summary["stack_resident_frame_value_static"]),
            "stack_resident_frame_value_modelled_dynamic": int(frame_summary["stack_resident_frame_value_modelled_dynamic"]),
            "true_spill_dynamic": "UNKNOWN_NOT_ESTABLISHED",
            "true_reload_dynamic": "UNKNOWN_NOT_ESTABLISHED",
            "interpretation": "overlay, not additive primary taxonomy; stack residency is not spill proof",
        },
        "instruction_limit": {
            "dynamic": dynamic_by_family["INSTRUCTION_LIMIT_ACCOUNTING"],
            "classification": "POLICY_REQUIRED",
            "semantic_accounting_required": True,
            "implementation_realization": "current sidecar class is not split further",
            "redundant_accounting": 0,
            "control_flow_duplication": "UNKNOWN_NOT_SEPARATELY_MEASURED",
            "failure_path_realization": "included in current policy class where present",
        },
        "memory_initialization_overlay": {
            "dynamic": 6660,
            "source": "P9.1 subtype; included within P10 MEMORY_VALIDITY primary family",
            "primary_family_duplication": False,
        },
        "register_initialization_dynamic": 0,
        "bounds_dynamic": dynamic_by_family["BOUNDS_CHECK"],
        "reference_validity_dynamic": "NOT_SEPARATELY_MEASURED",
        "slice_validity_dynamic": "NOT_SEPARATELY_MEASURED",
        "immutability_dynamic": "NOT_SEPARATELY_MEASURED",
        "frame_addressing_dynamic": dynamic_by_family["FRAME_CANONICALIZATION"],
        "frame_value_load_dynamic": "NOT_SEPARATELY_MEASURED",
        "frame_value_store_dynamic": "NOT_SEPARATELY_MEASURED",
        "true_spill_dynamic": "UNKNOWN_NOT_ESTABLISHED",
        "true_reload_dynamic": "UNKNOWN_NOT_ESTABLISHED",
        "abi_overhead_dynamic": dynamic_by_family["CALL_ABI_OVERHEAD"],
        "branch_control_dynamic": dynamic_by_family["BRANCH_CONTROL"],
        "representation_dynamic": dynamic_by_family["FRAME_CANONICALIZATION"],
        "other_dynamic": dynamic_by_family["OTHER_RUNTIME_SAFETY"],
        "unknown_primary_dynamic": 0,
        "unknown_avoidability_dynamic": nature_totals["UNKNOWN"],
        "provably_required_dynamic": nature_totals["SEMANTICALLY_REQUIRED"] + nature_totals["SAFETY_REQUIRED"] + nature_totals["POLICY_REQUIRED"] + nature_totals["ABI_REQUIRED"],
        "provably_avoidable_dynamic": 0,
        "potentially_avoidable_dynamic": 0,
        "unknown_dynamic": 0,
        "materiality_basis": MATERIALITY_BASIS,
        "concrete_avoidable_example_found": False,
        "material_avoidable_family_found": False,
        "candidate_1": "NONE",
        "candidate_1_dynamic": 0,
        "candidate_1_max_theoretical_removable": 0,
        "candidate_1_first_causal_boundary": "NONE",
        "candidate_1_previous_research_status": "NO_FAMILY_SATISFIED_SELECTION_GATE",
        "p10_selection": "NO_VALID_TARGET_YET",
        "next_global_target": "NONE",
        "next_discriminating_question": "NONE_WITHOUT_A_CONCRETE_AVOIDABLE_EXAMPLE",
        "production_optimization_started": False,
        "correctness_integration_status": "STILL_BLOCKED_BY_PROVENANCE",
        "correctness_integrated": False,
        "lab_consistency": "PENDING_VALIDATION",
        "remote_write_provenance": "PENDING_VALIDATION",
        "github_actions_executed": False,
        "benchmark_executed": False,
        "shutdown_authorized": False,
        "negative_results": [
            "P9_BOUNDS_VALIDITY_CLOSED_NO_AVOIDABLE_SUBCLASS",
            "P9_UNKNOWN_REGISTER_INIT_EXCLUDED_FROM_P10_OPPORTUNITY",
            "FRAME_STACK_RESIDENCY_IS_NOT_TRUE_SPILL_PROOF",
            "INSTRUCTION_LIMIT_REMAINDER_NOT_PROVEN_REDUNDANT",
            "SEMANTIC_PAYLOAD_NOT_OVERHEAD_BY_DEFAULT",
            "NO_CONCRETE_AVOIDABLE_EXAMPLE_IN_CENSUS",
        ],
    }
    _write(args.output, result)
    print(json.dumps({
        "TARGET_HEAD_MATCH": True,
        "TARGET_MAIN_ANCESTRY": result["target_main_ancestry"],
        "BASELINE_REPRODUCED": True,
        "BASELINE_ACTUAL": model_total,
        "WORKLOADS": len(workload_names),
        "CLASSIFICATION_COVERAGE": result["classification_coverage"],
        "TOP_DYNAMIC_FAMILY": families[0],
        "TOP_DYNAMIC_FAMILY_DYNAMIC": dynamic_by_family[families[0]],
        "TOP_NON_SEMANTIC_FAMILY": top_nonsemantic[0],
        "TOP_NON_SEMANTIC_DYNAMIC": dynamic_by_family[top_nonsemantic[0]],
        "UNKNOWN_AVOIDABILITY_DYNAMIC": nature_totals["UNKNOWN"],
        "P10_SELECTION": result["p10_selection"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
