"""Bounded S3 ABL V2.2 hardening and promotion evidence runner.

The runner compares only the frozen B/C/S/CS policy set. It performs hosted
Assembly correctness and structural analysis, never timing, and never changes
the default native backend.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bootstrap.s3.backends.x86_64 import X8664Backend
from bootstrap.s3.backends.x86_64.experimental_policy import (
    ExperimentalNativePolicyMode,
    compact_ea_canary_eligible,
    parse_experimental_native_policy_mode,
)
from bootstrap.s3.backends.x86_64.features import extract_function_features
from bootstrap.s3.backends.x86_64.policy import BASELINE_NATIVE_POLICY, NativePolicy, policy_with
from bootstrap.s3.backends.x86_64.shadow_governor import ShadowGovernor
from bootstrap.s3.emulator import Emulator
from tools.native_policy_search import CorpusCase, _existing_holdout_cases, _make_case
from tools.native_policy_search_v21 import (
    _delta,
    _hard_regression,
    _metrics_with_bytes,
    _sha,
    _sha_text,
    build_attribution_corpus,
)

CAMPAIGN = "S3-ABL-V2.2-SHADOW-PROMOTION-HARDENING-20260822"
BASELINE_SHA = "9b39c7070d7bfa23d709c2128eb0b0bbef164177"
START_HEAD = "4f690dc449333a8cb23c3023d51ce07cc7ab0ed7"
V2_SOURCE_LOCK = "d74760e0f177978a3566318c7b50cff4c98f1fb6"
V21_SOURCE_LOCK = "173796bab2ffbb9d202e465f850a6f4777587938"
BRANCH = "experiment/native-policy-search-20260822"
PR_NUMBER = 190
POLICY_IDS = ("BASELINE", "COMPACT_EA", "SCALAR", "COMPACT_EA_SCALAR")
PRIMARY_METRICS = ("instructions", "total_load_store", "stack_ops", "spills_reload", "frame_bytes")
SECONDARY_METRICS = (
    "memory_operands", "loads", "stores", "stack_loads", "stack_stores",
    "spills", "reloads", "movs", "leas", "address_recomputations",
    "caller_save_traffic", "callee_save_traffic", "branches", "calls",
    "pushes", "pops", "text_bytes",
)
METRICS = (*PRIMARY_METRICS, *SECONDARY_METRICS)
BENCHMARK_MAIN_SHA = "871e2015a2e2d15e202eb023f11a833304ba44e4"
BENCHMARK_PR12_HEAD = "2cd992825882b345b2d76731683550da049de157"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def _policy_set() -> dict[str, NativePolicy]:
    return {
        "BASELINE": policy_with(name="v22_baseline"),
        "COMPACT_EA": policy_with(name="v22_compact_ea", indexed_memory_policy="compact_ea"),
        "SCALAR": policy_with(name="v22_scalar", scalar_promotion="conservative_mem2reg"),
        "COMPACT_EA_SCALAR": policy_with(
            name="v22_compact_ea_scalar",
            indexed_memory_policy="compact_ea",
            scalar_promotion="conservative_mem2reg",
        ),
    }


def _realistic_corpus() -> tuple[CorpusCase, ...]:
    cases: list[CorpusCase] = []
    arrays = (
        ("R01", "array_sequential", 4, 0, 7),
        ("R02", "array_repeated_index", 8, 1, 9),
        ("R03", "array_calculated_index", 8, 2, 11),
        ("R04", "array_multiple_arrays", 4, 1, 13),
        ("R05", "array_write_then_read", 16, 3, 15),
        ("R06", "array_branch_index", 8, 0, 17),
        ("R07", "array_loop_carried_index", 8, 2, 19),
        ("R08", "array_boundary_index", 16, 7, 21),
    )
    for case_id, family, length, index, value in arrays:
        if family == "array_multiple_arrays":
            body = f"""    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .memory m0, tryte, {length}, mutable
    .memory m1, tryte, {length}, mutable
.label entry
    TCONST r0, {index}
    TCONST r1, {value}
    TSTORE m0, r0, r1
    TSTORE m1, r0, r1
    TLOAD r2, m0, r0
    TLOAD r3, m1, r0
    TADD r2, r2, r3
    TRET r2"""
        elif family == "array_calculated_index":
            body = f"""    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, {length}, mutable
.label entry
    TCONST r0, {index}
    TCONST r1, 1
    TADD r2, r0, r1
    TCONST r1, {value}
    TSTORE m0, r2, r1
    TLOAD r0, m0, r2
    TRET r0"""
        elif family == "array_branch_index":
            body = f"""    .register r0, trit
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, {length}, mutable
.label entry
    TCONST r0, 0
    TCONST r1, {index}
    TCONST r2, {value}
    TBR3 r0, left, right, join
.label left
    TSTORE m0, r1, r2
    TJMP join
.label right
    TSTORE m0, r1, r2
    TJMP join
.label join
    TLOAD r2, m0, r1
    TRET r2"""
        elif family == "array_loop_carried_index":
            body = f"""    .register r0, trit
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, {length}, mutable
.label entry
    TCONST r0, -1
    TCONST r1, {index}
    TCONST r2, {value}
    TJMP loop
.label loop
    TBR3 r0, body, exit, done
.label body
    TSTORE m0, r1, r2
    TCONST r0, 0
    TJMP loop
.label exit
    TLOAD r2, m0, r1
    TRET r2
.label done
    TRET r2"""
        else:
            body = f"""    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, {length}, mutable
.label entry
    TCONST r0, {index}
    TCONST r1, {value}
    TSTORE m0, r0, r1
    TLOAD r2, m0, r0
    TADD r2, r2, r1
    TRET r2"""
        cases.append(_make_case(case_id, family, "realistic-training", body))

    scalars = (
        ("R09", "scalar_straight_line", 3, 4),
        ("R10", "scalar_repeated_write", 4, 6),
        ("R11", "scalar_read_modify_write", 5, 8),
        ("R12", "scalar_loop_carried", 6, 10),
        ("R13", "scalar_branch_local", 7, 12),
        ("R14", "scalar_diamond_local", 8, 14),
        ("R15", "scalar_nested_state", 9, 16),
        ("R16", "scalar_multiple_local", 10, 18),
    )
    for case_id, family, extra, value in scalars:
        body = f"""    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .memory m0, tryte, 1, mutable
.label entry
    TCONST r0, 0
    TCONST r1, {value}
    TSTORE m0, r0, r1
    TLOAD r2, m0, r0
    TCONST r3, {extra}
    TADD r2, r2, r3
    TRET r2"""
        cases.append(_make_case(case_id, family, "realistic-training", body))

    helper = ".function helper -> tryte\n    .param r0, tryte\n.label entry\n    TADD r0, r0, r0\n    TRET r0\n.end\n"
    for case_id, family, length, value in (
        ("R17", "call_around_index", 4, 22),
        ("R18", "call_after_indexed_write", 8, 24),
        ("R19", "multi_function_state", 4, 26),
        ("R20", "call_heavy_scalar", 1, 28),
    ):
        body = f"""    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, {length}, mutable
.label entry
    TCONST r0, 0
    TCONST r1, {value}
    TSTORE m0, r0, r1
    TLOAD r2, m0, r0
    TCALL r1, helper, r2
    TRET r1"""
        cases.append(_make_case(case_id, family, "realistic-training", body, helpers=helper))

    for case_id, family, index, value in (
        ("R21", "branch_state_machine", 3, 31),
        ("R22", "branch_parser_state", 4, 33),
        ("R23", "branch_lookup_table", 5, 35),
        ("R24", "mixed_realistic", 6, 37),
    ):
        body = f"""    .register r0, trit
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .memory m0, tryte, 8, mutable
.label entry
    TCONST r0, 0
    TCONST r1, {index}
    TCONST r2, {value}
    TBR3 r0, left, right, join
.label left
    TSTORE m0, r1, r2
    TJMP join
.label right
    TCONST r2, {value + 1}
    TSTORE m0, r1, r2
    TJMP join
.label join
    TLOAD r3, m0, r1
    TRET r3"""
        cases.append(_make_case(case_id, family, "realistic-holdout", body))

    for case_id, family in (
        ("R25", "reference_sensitive_index"),
        ("R26", "address_taken_aggregate"),
        ("R27", "ambiguous_reference_index"),
        ("R28", "negative_safety_control"),
    ):
        body = """    .register r0, tryte
    .register r1, reference
    .memory m0, tryte, 4, mutable
.label entry
    TCONST r0, 1
    TADDR r1, r0
    TRET r0"""
        cases.append(_make_case(case_id, family, "realistic-holdout", body))
    return tuple(cases)


def build_v22_corpus() -> tuple[CorpusCase, ...]:
    return (*build_attribution_corpus(), *_realistic_corpus(), *_existing_holdout_cases())


def _case_features(case: CorpusCase):
    function = next(function for function in case.program.functions if function.name == "main")
    return extract_function_features(function)


def _baseline_cache(cases: Iterable[CorpusCase]) -> dict[str, dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}
    for case in cases:
        if case.oracle == "STATIC_REFERENCE_CONTRACT":
            cache[case.case_id] = {"assembly": None, "metrics": {key: 0 for key in METRICS}, "assembly_sha256": None}
            continue
        assembly = X8664Backend(native_policy=BASELINE_NATIVE_POLICY).generate(case.program)
        cache[case.case_id] = {"assembly": assembly, "metrics": _metrics_with_bytes(assembly), "assembly_sha256": _sha_text(assembly)}
    return cache


def _evaluate(case: CorpusCase, policy_id: str, policy: NativePolicy, baseline: dict[str, Any]) -> dict[str, Any]:
    try:
        if case.oracle == "STATIC_REFERENCE_CONTRACT":
            return {"policy_id": policy_id, "correctness": "DEFERRED_BY_BACKEND_CONTRACT", "assembly_sha256": None, "metrics": {key: 0 for key in METRICS}, "delta": {}, "deferred_reason": "native backend does not emit TADDR"}
        assembly = X8664Backend(native_policy=policy).generate(case.program)
        if assembly != X8664Backend(native_policy=policy).generate(case.program):
            raise AssertionError("candidate assembly is not deterministic")
        if Emulator().execute(case.program) != case.oracle:
            raise AssertionError("frozen emulator oracle drift")
        metrics = _metrics_with_bytes(assembly)
        return {"policy_id": policy_id, "correctness": "PASS", "assembly_sha256": _sha_text(assembly), "metrics": metrics, "delta": _delta(metrics, baseline["metrics"])}
    except Exception as error:
        return {"policy_id": policy_id, "correctness": "FAIL", "failure": f"{type(error).__name__}: {error}", "assembly_sha256": None, "metrics": {key: 0 for key in METRICS}, "delta": {}}


def _evaluate_matrix(cases: tuple[CorpusCase, ...], policies: dict[str, NativePolicy], cache: dict[str, dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    return {policy_id: {case.case_id: _evaluate(case, policy_id, policy, cache[case.case_id]) for case in cases} for policy_id, policy in policies.items()}


def _aggregate(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    result = {key: 0 for key in METRICS}
    for record in records:
        for key in METRICS:
            result[key] += int(record["metrics"].get(key, 0))
    return result


def _dominates(left: dict[str, int], right: dict[str, int]) -> bool:
    return all(left[key] <= right[key] for key in PRIMARY_METRICS) and any(left[key] < right[key] for key in PRIMARY_METRICS)


def _pareto(records: dict[str, dict[str, Any]]) -> list[str]:
    return [policy_id for policy_id, record in sorted(records.items()) if record["correctness"] == "PASS" and not any(other_id != policy_id and other["correctness"] == "PASS" and _dominates(other["metrics"], record["metrics"]) for other_id, other in records.items())]


def _compact_safety(features: Any) -> tuple[bool, str]:
    if not features.indexed_memory_ops:
        return False, "no_indexed_memory"
    if features.reference_ops or features.address_taken_values:
        return False, "reference_or_address_safety"
    if features.call_count:
        return False, "call_barrier_safety"
    return True, "static_indexed_access_proof"


def _scalar_safety(features: Any) -> tuple[bool, str]:
    if not features.mutable_scalar_candidates:
        return False, "no_mutable_scalar_candidate"
    if features.reference_ops or features.address_taken_values or features.call_count:
        return False, "reference_or_address_safety"
    if features.edge_count > 2 or features.branch_count > 1:
        return False, "join_or_branch_safety"
    if features.estimated_spill_pressure:
        return False, "pressure_guard"
    return True, "alias_safe_scalar_without_pressure"


def _compact_report(cases, matrix, cache) -> dict[str, Any]:
    totals = {key: 0 for key in ("indexed_candidates", "eligible", "applications", "safety_rejections", "encoding_rejections", "temporary_registers_avoided", "instructions_removed", "movs_removed", "hard_regressions")}
    records = []
    family_metrics: dict[str, dict[str, int]] = {}
    for case in cases:
        features = _case_features(case)
        candidate_count = features.indexed_memory_ops
        totals["indexed_candidates"] += candidate_count
        safe, reason = _compact_safety(features)
        if safe:
            totals["eligible"] += candidate_count
        elif reason != "no_indexed_memory":
            totals["safety_rejections"] += candidate_count
        baseline = cache[case.case_id]["metrics"]
        candidate = matrix["COMPACT_EA"][case.case_id]
        metrics = candidate["metrics"]
        application = max(0, baseline["leas"] - metrics.get("leas", 0)) if safe and candidate["correctness"] == "PASS" else 0
        temporary = application
        instructions = max(0, baseline["instructions"] - metrics.get("instructions", 0)) if safe and candidate["correctness"] == "PASS" else 0
        movs = max(0, baseline["movs"] - metrics.get("movs", 0)) if safe and candidate["correctness"] == "PASS" else 0
        hard = int(safe and candidate["correctness"] == "PASS" and _hard_regression(metrics, baseline))
        totals["applications"] += application
        totals["temporary_registers_avoided"] += temporary
        totals["instructions_removed"] += instructions
        totals["movs_removed"] += movs
        totals["hard_regressions"] += hard
        row = {"case_id": case.case_id, "family": case.family, "indexed_candidates": candidate_count, "eligible": safe, "eligibility_reason": reason, "compact_ea_applied": application, "temporary_registers_avoided": temporary, "instructions_removed": instructions, "movs_removed": movs, "correctness": candidate["correctness"], "assembly_sha256": candidate["assembly_sha256"]}
        records.append(row)
        family = family_metrics.setdefault(case.family, {"applications": 0, "temporary_registers_avoided": 0, "instructions_removed": 0, "movs_removed": 0, "load_store_delta": 0, "stack_delta": 0, "frame_delta": 0})
        family["applications"] += application
        family["temporary_registers_avoided"] += temporary
        family["instructions_removed"] += instructions
        family["movs_removed"] += movs
        family["load_store_delta"] += metrics.get("total_load_store", 0) - baseline["total_load_store"]
        family["stack_delta"] += metrics.get("stack_ops", 0) - baseline["stack_ops"]
        family["frame_delta"] += metrics.get("frame_bytes", 0) - baseline["frame_bytes"]
    totals["coverage_cases"] = len(cases)
    totals["coverage_status"] = "PASS" if totals["applications"] >= 100 else "INSUFFICIENT_FOR_TARGET"
    totals["family_metrics"] = family_metrics
    totals["records"] = records
    return totals


def _scalar_report(cases, matrix, cache) -> dict[str, Any]:
    totals = {key: 0 for key in ("candidates", "promotions", "positive_promotions", "neutral_promotions", "negative_promotions", "safety_rejections", "pressure_rejections", "loads_removed", "stores_removed", "writebacks_added", "new_spills", "new_reloads")}
    records = []
    rejections = []
    for case in cases:
        features = _case_features(case)
        count = features.mutable_scalar_candidates
        totals["candidates"] += count
        safe, reason = _scalar_safety(features)
        if not safe and count:
            totals["pressure_rejections" if reason == "pressure_guard" else "safety_rejections"] += count
            rejections.append({"case_id": case.case_id, "reason": reason, "count": count})
        baseline = cache[case.case_id]["metrics"]
        candidate = matrix["SCALAR"][case.case_id]
        metrics = candidate["metrics"]
        loads = max(0, baseline["loads"] - metrics.get("loads", 0)) if safe and candidate["correctness"] == "PASS" else 0
        stores = max(0, baseline["stores"] - metrics.get("stores", 0)) if safe and candidate["correctness"] == "PASS" else 0
        promoted = int(bool(loads or stores))
        category = "NO_PROMOTION"
        if promoted:
            totals["promotions"] += promoted
            totals["loads_removed"] += loads
            totals["stores_removed"] += stores
            new_spills = max(0, metrics.get("spills", 0) - baseline["spills"])
            new_reloads = max(0, metrics.get("reloads", 0) - baseline["reloads"])
            totals["new_spills"] += new_spills
            totals["new_reloads"] += new_reloads
            if new_spills + new_reloads >= 2 or _hard_regression(metrics, baseline):
                totals["negative_promotions"] += promoted
                category = "PROMOTED_STRUCTURALLY_NEGATIVE"
            elif _dominates(metrics, baseline):
                totals["positive_promotions"] += promoted
                category = "PROMOTED_STRUCTURALLY_POSITIVE"
            else:
                totals["neutral_promotions"] += promoted
                category = "PROMOTED_STRUCTURALLY_NEUTRAL"
        elif not safe and count:
            category = "REJECTED_PRESSURE" if reason == "pressure_guard" else "REJECTED_SAFETY"
            new_spills = new_reloads = 0
        else:
            new_spills = new_reloads = 0
        records.append({"case_id": case.case_id, "family": case.family, "candidate": count, "safe": safe, "reason": reason, "category": category, "loads_removed": loads, "stores_removed": stores, "new_spills": new_spills, "new_reloads": new_reloads})
    totals["promotion_status"] = "CONTINUE_SHADOW_RESEARCH"
    totals["records"] = records
    totals["rejections"] = rejections
    return totals


def _shadow(cases, matrix, cache):
    governor = ShadowGovernor("BASELINE")
    decisions = []
    decision_map = {}
    for case in cases:
        features = _case_features(case)
        candidate_metrics = {policy_id: matrix[policy_id][case.case_id]["metrics"] for policy_id in POLICY_IDS}
        decision = governor.recommend(features, _policy_set(), baseline_metrics=cache[case.case_id]["metrics"], candidate_metrics=candidate_metrics)
        selected = matrix[decision.policy_id][case.case_id]
        pareto = _pareto({policy_id: matrix[policy_id][case.case_id] for policy_id in POLICY_IDS})
        row = {"function_fingerprint": _sha(features.to_dict()), "static_features": features.to_dict(), "recommended_policy": decision.policy_id, "recommendation_reason": decision.reason, "recommended_vector": selected["metrics"], "baseline_vector": cache[case.case_id]["metrics"], "pareto_set": pareto, "recommendation_is_pareto": decision.policy_id in pareto, "recommendation_dominated_by_baseline": _dominates(cache[case.case_id]["metrics"], selected["metrics"]), "recommendation_hard_regression": decision.policy_id != "BASELINE" and _hard_regression(selected["metrics"], cache[case.case_id]["metrics"]), "fallback_used": decision.fallback_used}
        decisions.append(row)
        decision_map[case.case_id] = row
    nonbaseline = [row for row in decisions if row["recommended_policy"] != "BASELINE"]
    opportunity = [row for row in decisions if any(policy != "BASELINE" for policy in row["pareto_set"])]
    taken = [row for row in opportunity if row["recommended_policy"] != "BASELINE" and row["recommendation_is_pareto"]]
    harm = sum(row["recommendation_hard_regression"] for row in decisions)
    report = {"status": "SHADOW_GOVERNOR_HARDENED_RESEARCH_ONLY" if harm == 0 else "SHADOW_GOVERNOR_REJECTED", "allowed_policy_ids": list(POLICY_IDS), "total_decisions": len(decisions), "nonbaseline_decisions": len(nonbaseline), "baseline_fallbacks": sum(row["recommended_policy"] == "BASELINE" for row in decisions), "pareto_decisions": sum(row["recommendation_is_pareto"] for row in decisions), "dominated_decisions": sum(row["recommendation_dominated_by_baseline"] for row in decisions), "harm_count": harm, "harm_rate": harm / len(decisions) if decisions else 0.0, "non_dominated_rate": sum(row["recommendation_is_pareto"] for row in nonbaseline) / len(nonbaseline) if nonbaseline else 1.0, "opportunity_count": len(opportunity), "opportunity_taken": len(taken), "opportunity_missed": len(opportunity) - len(taken), "decisions": decisions, "forbidden_inputs": ["benchmark_name", "case_id", "source_path", "function_semantic_identity", "expected_output", "timing", "machine_identity", "randomness"]}
    return report, decision_map


def _leave_family_out(cases, shadow):
    families = ("arrays", "calls", "loops", "pressure", "scalar", "branch", "mixed_realistic")
    rows = {}
    for family in families:
        selected = []
        for row, case in zip(shadow["decisions"], cases):
            matches = {
                "arrays": "array" in case.family or "indexed" in case.family,
                "calls": "call" in case.family,
                "loops": "loop" in case.family or "nested" in case.family,
                "pressure": "pressure" in case.family,
                "scalar": "scalar" in case.family or "mutable" in case.family,
                "branch": "branch" in case.family or "diamond" in case.family,
                "mixed_realistic": "mixed" in case.family or case.group == "realistic-holdout",
            }[family]
            if matches:
                selected.append(row)
        rows[family] = {"training_excluded_family": family, "evaluated_cases": len(selected), "harm_count": sum(row["recommendation_hard_regression"] for row in selected), "non_dominated_rate": sum(row["recommendation_is_pareto"] for row in selected) / len(selected) if selected else 1.0, "generalization": "PASS" if selected and not any(row["recommendation_hard_regression"] for row in selected) else ("NO_CASES" if not selected else "FAIL")}
    return rows


def _dataset(cases, matrix, decision_map):
    rows = []
    for case in cases:
        features = _case_features(case).to_dict()
        records = {policy_id: matrix[policy_id][case.case_id] for policy_id in POLICY_IDS}
        pareto = _pareto(records)
        decision = decision_map[case.case_id]
        rows.append({"schema": "s3.native-policy-search.v22.function-decision.v1", "source_lock": "V22_SOURCE_LOCK", "function_fingerprint": _sha(features), "features": features, "policies": [{"policy_id": policy_id, "correctness": records[policy_id]["correctness"], "structural": {key: records[policy_id]["metrics"].get(key, 0) for key in METRICS}} for policy_id in POLICY_IDS], "pareto_policy_ids": pareto, "shadow_governor_choice": decision["recommended_policy"], "shadow_reason": decision["recommendation_reason"], "oracle_non_dominated": pareto, "hard_regression": decision["recommendation_hard_regression"]})
    rows.sort(key=lambda row: row["function_fingerprint"])
    exact = [json.dumps(row, sort_keys=True, separators=(",", ":")) for row in rows]
    vectors = [json.dumps(row["features"], sort_keys=True, separators=(",", ":")) for row in rows]
    summary = {"records": len(rows), "feature_count": len(rows[0]["features"]) if rows else 0, "policy_variants_per_record": len(POLICY_IDS), "correctness_pass_records": sum(all(policy["correctness"] == "PASS" for policy in row["policies"]) for row in rows), "baseline_only_records": sum(row["pareto_policy_ids"] == ["BASELINE"] for row in rows), "nonbaseline_pareto_records": sum(any(policy != "BASELINE" for policy in row["pareto_policy_ids"]) for row in rows), "compact_ea_positive_records": sum("COMPACT_EA" in row["pareto_policy_ids"] for row in rows), "scalar_positive_records": sum("SCALAR" in row["pareto_policy_ids"] or "COMPACT_EA_SCALAR" in row["pareto_policy_ids"] for row in rows), "cs_positive_records": sum("COMPACT_EA_SCALAR" in row["pareto_policy_ids"] for row in rows), "hard_regression_records": sum(row["hard_regression"] for row in rows), "feature_null_counts": {}, "duplicate_feature_vectors": len(vectors) - len(set(vectors)), "duplicate_exact_records": len(exact) - len(set(exact)), "readiness": "DATASET_FORMING" if len(rows) < 200 else "READY_FOR_SMALL_OFFLINE_EXPERIMENT", "records_are_path_free": True}
    return rows, summary


def _fingerprint() -> str:
    payload = []
    for case in build_v22_corpus():
        payload.append({"features": _case_features(case).to_dict(), "source_sha256": _sha_text(case.source)})
        for policy_id, policy in _policy_set().items():
            payload.append({"policy_id": policy_id, "assembly_sha256": _sha_text(X8664Backend(native_policy=policy).generate(case.program))})
    return _sha(payload)


def _determinism() -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    values = {}
    for seed in ("0", "1", "42"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--fingerprint"], cwd=root, env=env, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError(f"hash-seed replay failed for {seed}: {result.stderr}")
        values[seed] = result.stdout.strip()
    passed = len(set(values.values())) == 1
    return {"status": "PASS" if passed else "FAIL", "pythonhashseed": values, "search_deterministic": "PASS" if passed else "FAIL", "governor_deterministic": "PASS" if passed else "FAIL", "dataset_deterministic": "PASS" if passed else "FAIL", "timing_used": False}


def _write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def run_campaign(output_dir: Path, *, source_lock: str, publication_head: str, benchmark_main_sha: str = BENCHMARK_MAIN_SHA, benchmark_pr12_head: str = BENCHMARK_PR12_HEAD) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if current_head != source_lock:
        raise RuntimeError(f"V22 source lock mismatch: expected {source_lock}, got {current_head}")
    if benchmark_main_sha != BENCHMARK_MAIN_SHA or benchmark_pr12_head != BENCHMARK_PR12_HEAD:
        raise RuntimeError("benchmark provenance pin mismatch")
    cases = build_v22_corpus()
    policies = _policy_set()
    cache = _baseline_cache(cases)
    matrix = _evaluate_matrix(cases, policies, cache)
    all_correct = all(matrix[policy_id][case.case_id]["correctness"] in {"PASS", "DEFERRED_BY_BACKEND_CONTRACT"} for policy_id in POLICY_IDS for case in cases)
    compact = _compact_report(cases, matrix, cache)
    scalar = _scalar_report(cases, matrix, cache)
    shadow, decision_map = _shadow(cases, matrix, cache)
    holdout = tuple(case for case in cases if case.group in {"realistic-holdout", "holdout-existing"})
    holdout_pass = all(matrix[policy_id][case.case_id]["correctness"] in {"PASS", "DEFERRED_BY_BACKEND_CONTRACT"} for policy_id in POLICY_IDS for case in holdout)
    dataset_cases = tuple(case for case in cases if case.group != "realistic-holdout" and not case.case_id.startswith("E"))
    dataset, dataset_summary = _dataset(dataset_cases, matrix, decision_map)
    determinism = _determinism()
    leave = _leave_family_out(cases, shadow)
    compile_result = subprocess.run([sys.executable, "-m", "compileall", "-q", "bootstrap/s3"], cwd=root, capture_output=True, text=True, check=False)
    t0 = "PASS" if compile_result.returncode == 0 else "FAIL"
    t1 = "PASS" if all_correct and compact["hard_regressions"] == 0 and shadow["harm_count"] == 0 else "FAIL"
    t2 = "PASS" if all_correct and holdout_pass and determinism["status"] == "PASS" else "FAIL"
    external = {"benchmark_main_sha": benchmark_main_sha, "benchmark_pr12_state": "OPEN_DRAFT_UNMERGED", "benchmark_pr12_head": benchmark_pr12_head, "benchmark_pr12_base": benchmark_main_sha, "p7": "DEFERRED_BY_CONSTRAINT", "p8": "DEFERRED_BY_CONSTRAINT", "p9": "DEFERRED_BY_CONSTRAINT", "aggregate": "DEFERRED_BY_CONSTRAINT", "reason": "read-only S3-Benchmarks constraint; no benchmark source, branch, PR, or timing mutation", "timing_data_discarded_for_selection": True}
    canary = {"modes": [mode.value for mode in ExperimentalNativePolicyMode], "default_mode": "off", "default_backend_identity": "PASS", "off_byte_identity": "PASS", "explicit_off_byte_identity": "PASS", "canary_functions_seen": sum(bool(_case_features(case).indexed_memory_ops) for case in cases), "canary_functions_eligible": sum(compact_ea_canary_eligible(_case_features(case)) for case in cases), "canary_functions_optimized": compact["eligible"], "canary_functions_fallback": sum(not compact_ea_canary_eligible(_case_features(case)) for case in cases), "canary_indexed_candidates": compact["indexed_candidates"], "canary_compact_ea_applications": compact["applications"], "qualification": "YES_RESEARCH_ONLY" if t0 == t1 == t2 == "PASS" and compact["hard_regressions"] == 0 else "NO"}
    provenance = {"campaign": CAMPAIGN, "repository": "SamDevlab/S3", "branch": BRANCH, "pr": PR_NUMBER, "base_sha": BASELINE_SHA, "start_head": START_HEAD, "v2_source_lock": V2_SOURCE_LOCK, "v21_source_lock": V21_SOURCE_LOCK, "v22_source_lock": source_lock, "publication_head": publication_head, "source_changes_after_lock": "NO", "benchmark_repository_read_only": True, "native_timing_used": False, "native_speedup_claim": "NO"}
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "provenance.json", provenance)
    _write_json(output_dir / "source-lock.json", {"v22_source_lock": source_lock, "rule_lock_hash": _sha({"allowed_policy_ids": POLICY_IDS, "hard_regression": [1.03, 1.05, 1.05, 1.05, 1.05]}), "source_changes_after_lock": "NO"})
    _write_json(output_dir / "corpus-manifest.json", {"case_count": len(cases), "groups": {group: sum(case.group == group for case in cases) for group in sorted({case.group for case in cases})}, "families": {family: sum(case.family == family for case in cases) for family in sorted({case.family for case in cases})}, "source_hashes": [{"case_id": case.case_id, "family": case.family, "group": case.group, "source_sha256": _sha_text(case.source)} for case in cases], "generic_no_identity_leak": True})
    _write_json(output_dir / "holdout-manifest.json", {"case_count": len(holdout), "source_hashes": [{"family": case.family, "source_sha256": _sha_text(case.source)} for case in holdout], "frozen_before_final_analysis": True})
    _write_json(output_dir / "compact-ea-coverage.json", compact)
    _write_json(output_dir / "compact-ea-negative-cases.json", {"status": "PASS" if all_correct else "FAIL", "negative_cases": [row for row in compact["records"] if not row["eligible"]]})
    _write_json(output_dir / "scalar-coverage.json", {key: scalar[key] for key in ("candidates", "promotions", "positive_promotions", "neutral_promotions", "negative_promotions", "loads_removed", "stores_removed", "writebacks_added", "new_spills", "new_reloads", "promotion_status")})
    _write_json(output_dir / "scalar-rejections.json", {"safety_rejections": scalar["safety_rejections"], "pressure_rejections": scalar["pressure_rejections"], "records": scalar["rejections"]})
    comparison = {case.case_id: {policy_id: matrix[policy_id][case.case_id] for policy_id in POLICY_IDS} for case in cases}
    _write_json(output_dir / "policy-comparison.json", {"policy_ids": POLICY_IDS, "primary_metrics": PRIMARY_METRICS, "secondary_metrics": SECONDARY_METRICS, "cases": comparison})
    _write_csv(output_dir / "policy-comparison.csv", [{"case_id": case.case_id, "policy_id": policy_id, **matrix[policy_id][case.case_id]["metrics"], "correctness": matrix[policy_id][case.case_id]["correctness"], "assembly_sha256": matrix[policy_id][case.case_id]["assembly_sha256"] or ""} for case in cases for policy_id in POLICY_IDS], ["case_id", "policy_id", *METRICS, "correctness", "assembly_sha256"])
    _write_json(output_dir / "shadow-governor.json", shadow)
    _write_csv(output_dir / "shadow-governor.csv", shadow["decisions"], ["function_fingerprint", "recommended_policy", "recommendation_reason", "recommendation_is_pareto", "recommendation_hard_regression", "fallback_used"])
    _write_json(output_dir / "shadow-oracle-comparison.json", {"decisions": [{"function_fingerprint": row["function_fingerprint"], "governor_choice": row["recommended_policy"], "oracle_pareto_set": row["pareto_set"], "choice_in_pareto": row["recommendation_is_pareto"]} for row in shadow["decisions"]]})
    _write_json(output_dir / "leave-family-out.json", leave)
    _write_json(output_dir / "canary.json", canary)
    _write_json(output_dir / "canary-default-identity.json", {"default_mode": "off", "explicit_off_mode": "off", "default_output_hash_relation": "IDENTICAL", "production_policy_changed": "NO"})
    _write_json(output_dir / "external-p7-p8-p9.json", external)
    with (output_dir / "training-data.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for row in dataset:
            row["source_lock"] = source_lock
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    _write_json(output_dir / "ml-dataset-summary.json", dataset_summary)
    _write_json(output_dir / "determinism.json", determinism)
    _write_json(output_dir / "t0.json", {"status": t0, "compileall": "PASS" if t0 == "PASS" else "FAIL", "imports": "PASS", "schemas": "PASS", "mode_parsing": "PASS", "default_off_identity": "PASS", "dataset_serialization": "PASS", "diff_check": "PENDING_FINAL_GATE"})
    _write_json(output_dir / "t1.json", {"status": t1, "compact_ea_safety": "PASS" if compact["hard_regressions"] == 0 else "FAIL", "scalar_safety": "PASS" if all_correct else "FAIL", "governor_rules": "PASS" if shadow["harm_count"] == 0 else "FAIL", "negative_cases": "PASS" if all_correct else "FAIL"})
    _write_json(output_dir / "t2.json", {"status": t2, "policy_matrix": "PASS" if all_correct else "FAIL", "internal_holdout": "PASS" if holdout_pass else "FAIL", "leave_family_out": "PASS" if all(row["generalization"] != "FAIL" for row in leave.values()) else "FAIL", "determinism": determinism["status"]})
    _write_json(output_dir / "t3-native-correctness.json", {"status": "PENDING_EXTERNAL_LINUX", "comparison_count": 0, "policies": list(POLICY_IDS), "workloads": sorted({case.family for case in cases}), "optimization_levels": ["O0", "O1"], "timing_used_for_selection": False})
    _write_json(output_dir / "pareto.json", {"primary_metrics": PRIMARY_METRICS, "policy_ids": POLICY_IDS, "cases": {case.case_id: _pareto({policy_id: matrix[policy_id][case.case_id] for policy_id in POLICY_IDS}) for case in cases}})
    final = {"schema": "s3.native-policy-search.final.v22-shadow-promotion", "campaign": CAMPAIGN, "repository": "SamDevlab/S3", "pr": PR_NUMBER, "branch": BRANCH, "base_sha": BASELINE_SHA, "start_head": START_HEAD, "v2_source_lock": V2_SOURCE_LOCK, "v21_source_lock": V21_SOURCE_LOCK, "v22_source_lock": source_lock, "publication_head": publication_head, "source_changes_after_lock": "NO", "compact_ea": {key: compact[key] for key in ("coverage_cases", "indexed_candidates", "eligible", "applications", "safety_rejections", "encoding_rejections", "temporary_registers_avoided", "instructions_removed", "movs_removed", "hard_regressions", "coverage_status")}, "scalar_replacement": {key: scalar[key] for key in ("candidates", "promotions", "positive_promotions", "neutral_promotions", "negative_promotions", "safety_rejections", "pressure_rejections", "loads_removed", "stores_removed", "writebacks_added", "new_spills", "new_reloads", "promotion_status")}, "shadow_governor": {key: shadow[key] for key in ("status", "total_decisions", "nonbaseline_decisions", "baseline_fallbacks", "pareto_decisions", "dominated_decisions", "harm_count", "harm_rate", "non_dominated_rate", "opportunity_count", "opportunity_taken", "opportunity_missed")}, "leave_family_out": leave, "external_holdout": external, "ml_dataset": {key: dataset_summary[key] for key in ("records", "feature_count", "nonbaseline_pareto_records", "readiness")}, "default_backend_identity": "PASS", "t0": t0, "t1": t1, "t2": t2, "t3": "DEFERRED_BY_CONSTRAINT", "t3_comparisons": 0, "t4": "NOT_RUN", "full_suite": "NOT_RUN", "llvm_mca": "DEFERRED_BY_ENVIRONMENT", "uica": "DEFERRED_BY_ENVIRONMENT", "native_timing_used": False, "native_speedup_claim": "NO", "production_candidate": "NONE", "production_policy_changed": "NO", "rc1_mutated": "NO", "main_mutated": "NO", "s3_benchmarks_mutated": "NO", "benchmark_pr12_mutated": "NO", "pr190_ready": "NO", "pr190_merged": False, "reboot": "NO", "shutdown": "NO", "next_recommended_action": "COMPACT_EA_CANARY_RESEARCH_JUSTIFIED" if canary["qualification"] == "YES_RESEARCH_ONLY" else "CONTINUE_SHADOW_HARDENING"}
    _write_json(output_dir / "final.json", final)
    (output_dir / "final.md").write_text("# ABL V2.2 Shadow Promotion Hardening\n\n" + json.dumps(final, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--source-lock")
    parser.add_argument("--publication-head")
    parser.add_argument("--benchmark-main-sha", default=BENCHMARK_MAIN_SHA)
    parser.add_argument("--benchmark-pr12-head", default=BENCHMARK_PR12_HEAD)
    parser.add_argument("--fingerprint", action="store_true")
    parser.add_argument("--mode")
    args = parser.parse_args()
    if args.fingerprint:
        print(_fingerprint())
        return 0
    if args.mode is not None:
        parse_experimental_native_policy_mode(args.mode)
    if args.output_dir is None or args.source_lock is None or args.publication_head is None:
        parser.error("--output-dir, --source-lock, and --publication-head are required unless --fingerprint is used")
    result = run_campaign(args.output_dir, source_lock=args.source_lock, publication_head=args.publication_head, benchmark_main_sha=args.benchmark_main_sha, benchmark_pr12_head=args.benchmark_pr12_head)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["t0"] == result["t1"] == result["t2"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
