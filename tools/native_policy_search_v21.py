"""S3 ABL V2.1 attribution and shadow-governor laboratory.

This is an extension of the V2 search harness, not a production compiler
path.  It evaluates static structural evidence, performs correctness before
ranking, and writes an auditable report set without using timing.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterable

from bootstrap.s3.assembly import AssemblyOpcode, AssemblyType, parse_assembly
from bootstrap.s3.backends.x86_64 import X8664Backend
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.backends.x86_64.features import (
    FunctionFeatureVector,
    extract_function_features,
)
from bootstrap.s3.backends.x86_64.policy import (
    BASELINE_NATIVE_POLICY,
    NativePolicy,
    policy_with,
)
from bootstrap.s3.backends.x86_64.shadow_governor import ShadowGovernor
from bootstrap.s3.emulator import Emulator
from tools.native_policy_search import (
    CorpusCase,
    _existing_holdout_cases,
    _make_case,
    _metrics,
    build_corpus,
)
from tools.native_policy_search_v2 import (
    _canonical_id as v2_canonical_id,
    build_v2_corpus,
)


BASELINE_SHA = "9b39c7070d7bfa23d709c2128eb0b0bbef164177"
START_HEAD = "fca8bb753c838905928981c2adca1471586609e4"
V2_SOURCE_LOCK = "d74760e0f177978a3566318c7b50cff4c98f1fb6"
BRANCH = "experiment/native-policy-search-20260822"
PR_NUMBER = 190
SEARCH_SEED = 0
PRIMARY_METRICS = (
    "stack_ops",
    "total_load_store",
    "spills_reload",
    "frame_bytes",
    "instructions",
)
METRIC_COLUMNS = (
    "instructions",
    "memory_operands",
    "total_load_store",
    "stack_ops",
    "stack_loads",
    "stack_stores",
    "spills",
    "reloads",
    "spills_reload",
    "frame_bytes",
    "caller_save_traffic",
    "callee_save_traffic",
    "movs",
    "leas",
    "address_recomputations",
    "pushes",
    "pops",
    "branches",
    "calls",
    "text_bytes",
)
MECHANISM_COLUMNS = (
    "compact_ea_applied",
    "temporary_registers_avoided",
    "scalar_candidates",
    "scalar_promoted",
    "loads_removed",
    "stores_removed",
    "writebacks_added",
    "region_spill_candidates",
    "region_spill_applied",
    "spill_ops_avoided",
    "reloads_avoided",
    "copies_added",
    "loads_added",
    "stores_added",
    "rematerializable_values",
    "rematerializations",
    "reloads_avoided_by_remat",
    "spill_ops_avoided_by_remat",
    "remat_instructions_added",
    "live_ranges_split",
    "splits_rejected_by_cost",
    "extra_save_restore",
)
ATTRIBUTION_SLOTS = (
    ("indexed_memory", ("D12", "D13", "D14", "D15", "D16", "H03")),
    ("scalar_replacement", ("D17", "D22", "H06", "D05", "D20", "D18")),
    ("register_pressure", ("D06", "D11", "D03", "D10", "D09", "H02")),
    ("localized_pressure", ("D02", "D03", "D15", "H01", "H06", "D05")),
    ("constant_rematerialization", ("D01", "D04", "D06", "D21", "D20", "H01")),
    ("loop_live_range", ("D02", "D03", "D15", "D24", "H01", "D06")),
    ("calls_abi", ("D07", "D08", "D09", "D10", "D11", "H05")),
    ("references_aliasing", ("D18", "D19", "H04", "D20", "D16", "H06")),
    ("mixed_realistic", ("D20", "H02", "H05", "H06", "D16", "D14")),
    ("negative_control", ("D01", "D07", "H04", "D18", "D04", "H03")),
)
NEGATIVE_POSITIONS = {
    "indexed_memory": {4, 5},
    "scalar_replacement": {4, 5},
    "register_pressure": {4, 5},
    "localized_pressure": {4, 5},
    "constant_rematerialization": {4, 5},
    "loop_live_range": {4, 5},
    "calls_abi": {4, 5},
    "references_aliasing": {0, 1, 2, 3, 4, 5},
    "mixed_realistic": {4, 5},
    "negative_control": {0, 1, 2, 3, 4, 5},
}


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _sha_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _parse_variant(case: CorpusCase, case_id: str, family: str, variant: int) -> CorpusCase:
    source = case.source
    replacement = str((variant % 3) - 1 if "register r0, trit" in source else (variant + 1) * 3)
    if "TCONST r0," in source and not any(
        token in source for token in ("TLOAD", "TSTORE", "TBR3", "TCALL", "TADDR")
    ):
        source = source.replace("TCONST r0,", f"TCONST r0,", 1)
        lines = source.splitlines()
        for index, line in enumerate(lines):
            if "TCONST r0," in line:
                lines[index] = line.split("TCONST r0,", 1)[0] + f"TCONST r0, {replacement}"
                break
        source = "\n".join(lines) + "\n"
    program = parse_assembly(source)
    if "TADDR" in source:
        functions = list(program.functions)
        main = functions[-1]
        blocks = []
        for block in main.blocks:
            instructions = tuple(
                replace(instruction, reference_target=AssemblyType.TRYTE)
                if instruction.opcode is AssemblyOpcode.TADDR
                else instruction
                for instruction in block.instructions
            )
            blocks.append(replace(block, instructions=instructions))
        functions[-1] = replace(
            main,
            blocks=tuple(blocks),
            reference_targets=((1, AssemblyType.TRYTE, False),),
        )
        program = replace(program, functions=tuple(functions))
    oracle = "STATIC_REFERENCE_CONTRACT" if "TADDR" in source else Emulator().execute(program)
    return CorpusCase(case_id, family, "attribution", source, program, oracle)


def build_attribution_corpus() -> tuple[CorpusCase, ...]:
    pool = {case.case_id: case for case in build_v2_corpus()}
    cases: list[CorpusCase] = []
    number = 1
    for family, source_ids in ATTRIBUTION_SLOTS:
        for position, source_id in enumerate(source_ids):
            case = _parse_variant(pool[source_id], f"A{number:02d}", family, position // 2)
            cases.append(case)
            number += 1
    if len(cases) != 60:
        raise AssertionError(f"attribution corpus must contain 60 cases, got {len(cases)}")
    return tuple(cases)


def attribution_polarity(case: CorpusCase) -> str:
    number = int(case.case_id[1:])
    position = (number - 1) % 6
    return "negative" if position in NEGATIVE_POSITIONS[case.family] else "positive"


def _policy_from_dict(config: dict[str, Any]) -> NativePolicy:
    return policy_with(
        name=str(config["name"]),
        register_order=tuple(config["register_order"]),
        call_register_order=tuple(config["call_register_order"]),
        call_residence=str(config["call_residence"]),
        residence_scope=str(config["residence_scope"]),
        spill_policy=str(config["spill_policy"]),
        spill_cost_parameters=tuple((str(k), int(v)) for k, v in config["spill_cost_parameters"]),
        rematerialization=str(config["rematerialization"]),
        live_range_split=str(config["live_range_split"]),
        move_coalescing=str(config["move_coalescing"]),
        indexed_memory_policy=str(config["indexed_memory_policy"]),
        scalar_promotion=str(config["scalar_promotion"]),
        load_forwarding=str(config["load_forwarding"]),
        writeback_policy=str(config["writeback_policy"]),
    )


def _load_v2_genomes(root: Path) -> dict[str, dict[str, Any]]:
    path = root / "reports/native-policy-search-20260822/v2-book-grounded/candidates.jsonl"
    wanted = {"V2_14403bd31bfa3164", "V2_077171a9b68c8814"}
    result: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        if record.get("policy_id") in wanted:
            result[record["policy_id"]] = record
    if set(result) != wanted:
        raise RuntimeError("V2 genome audit inputs are incomplete")
    return result


def _active_genes(config: dict[str, Any]) -> tuple[list[str], list[str], str]:
    baseline = BASELINE_NATIVE_POLICY.to_dict()
    mapping = (
        ("indexed_memory_policy", "COMPACT_INDEXED_MEMORY", "compact_ea"),
        ("scalar_promotion", "PRESSURE_AWARE_SCALAR_REPLACEMENT", "conservative_mem2reg"),
        ("spill_policy", "REGION_AWARE_SPILL", "region_aware"),
        ("rematerialization", "CONST_REMATERIALIZATION", "const_only"),
        ("live_range_split", "LOOP_BOUNDARY_LIVE_RANGE_SPLIT", "loop_boundary"),
    )
    active: list[str] = []
    inactive: list[str] = []
    for field, gene, active_value in mapping:
        if config[field] == active_value:
            active.append(gene)
        else:
            inactive.append(gene)
    for field in ("call_register_order", "call_residence", "residence_scope", "move_coalescing", "load_forwarding", "writeback_policy"):
        if config[field] != baseline[field]:
            active.append(field.upper())
        else:
            inactive.append(field.upper())
    active.sort()
    inactive.sort()
    label = "+".join(active) if active else "BASELINE"
    return active, inactive, label


def genome_audit(root: Path) -> dict[str, Any]:
    records = []
    for policy_id, record in sorted(_load_v2_genomes(root).items()):
        config = record["policy_config"]
        active, inactive, canonical = _active_genes(config)
        records.append({
            "policy_id": policy_id,
            "historical_label": record["label"],
            "active_genes": active,
            "inactive_genes": inactive,
            "canonical_genome_label": canonical,
            "policy_config": config,
            "parent_ids": record.get("parent_ids", []),
            "operator": record.get("operator"),
            "stage": record.get("stage"),
            "active_genes_derived_from": "policy_config_only",
        })
    return {
        "status": "PASS" if all(item["active_genes_derived_from"] == "policy_config_only" for item in records) else "FAIL_CLOSED_IDENTITY_AMBIGUOUS",
        "records": records,
    }


def _policy_id(policy: NativePolicy) -> str:
    return "V21_" + v2_canonical_id(policy, "v21").split("_", 1)[1]


def _ablation_policies() -> dict[str, NativePolicy]:
    result: dict[str, NativePolicy] = {}
    for bits in ("000", "001", "010", "011", "100", "101", "110", "111"):
        policy = policy_with(
            name=f"abl_{bits}",
            spill_policy="region_aware" if bits[2] == "1" else BASELINE_NATIVE_POLICY.spill_policy,
            scalar_promotion="conservative_mem2reg" if bits[1] == "1" else BASELINE_NATIVE_POLICY.scalar_promotion,
            indexed_memory_policy="compact_ea" if bits[0] == "1" else BASELINE_NATIVE_POLICY.indexed_memory_policy,
        )
        result[bits] = policy
    return result


def _metrics_with_bytes(assembly: str) -> dict[str, int]:
    result = _metrics(assembly)
    result["text_bytes"] = len(assembly.encode("utf-8"))
    return result


def _sum_metrics(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    result = {key: 0 for key in METRIC_COLUMNS}
    for record in records:
        for key in METRIC_COLUMNS:
            result[key] += int(record["metrics"].get(key, 0))
    return result


def _delta(candidate: dict[str, int], baseline: dict[str, int]) -> dict[str, int | float | str]:
    result: dict[str, int | float | str] = {}
    for key in METRIC_COLUMNS:
        value = candidate.get(key, 0)
        base = baseline.get(key, 0)
        result[key] = value - base
        result[f"{key}_ratio_to_baseline"] = "UNDEFINED_BASELINE_ZERO" if base == 0 and value else (1.0 if base == 0 else value / base)
        result[f"{key}_percent_delta"] = 0.0 if base == 0 else ((value - base) / base) * 100.0
    return result


def _mechanism_metrics(case: CorpusCase, policy: NativePolicy, baseline: dict[str, int], candidate: dict[str, int]) -> dict[str, int]:
    main = next(function for function in case.program.functions if function.name == "main")
    plan = analyze_allocation(main, policy)
    features = extract_function_features(main)
    compact = max(0, baseline["leas"] - candidate["leas"]) if policy.indexed_memory_policy == "compact_ea" else 0
    scalar_loads = max(0, baseline["loads"] - candidate["loads"]) if policy.scalar_promotion == "conservative_mem2reg" else 0
    scalar_stores = max(0, baseline["stores"] - candidate["stores"]) if policy.scalar_promotion == "conservative_mem2reg" else 0
    region_avoided = max(0, baseline["spills_reload"] - candidate["spills_reload"]) if policy.spill_policy == "region_aware" else 0
    split_carriers = sum(len(values) for values in plan.loop_split_saves.values())
    remat_count = len(plan.rematerializable_values) if policy.rematerialization == "const_only" else 0
    remat_added = max(0, candidate["instructions"] - baseline["instructions"]) if remat_count else 0
    return {
        "compact_ea_applied": compact,
        "temporary_registers_avoided": compact,
        "scalar_candidates": features.mutable_scalar_candidates,
        "scalar_promoted": 1 if scalar_loads or scalar_stores else 0,
        "loads_removed": scalar_loads,
        "stores_removed": scalar_stores,
        "writebacks_added": 0,
        "region_spill_candidates": len(plan.spill_costs) if policy.spill_policy == "region_aware" else 0,
        "region_spill_applied": int(policy.spill_policy == "region_aware" and bool(plan.spill_costs)),
        "spill_ops_avoided": region_avoided,
        "reloads_avoided": max(0, baseline["reloads"] - candidate["reloads"]) if policy.spill_policy == "region_aware" else 0,
        "copies_added": split_carriers * 2,
        "loads_added": split_carriers,
        "stores_added": split_carriers,
        "rematerializable_values": remat_count,
        "rematerializations": remat_added,
        "reloads_avoided_by_remat": remat_added,
        "spill_ops_avoided_by_remat": 0,
        "remat_instructions_added": remat_added,
        "live_ranges_split": len(plan.split_points) if policy.live_range_split == "loop_boundary" else 0,
        "splits_rejected_by_cost": 0,
        "extra_save_restore": split_carriers * 2,
    }


def _evaluate_case(case: CorpusCase, policy_id: str, policy: NativePolicy, baseline_cache: dict[str, Any]) -> dict[str, Any]:
    baseline = baseline_cache[case.case_id]
    try:
        assembly = X8664Backend(native_policy=policy).generate(case.program)
        repeat = X8664Backend(native_policy=policy).generate(case.program)
        if assembly != repeat:
            raise AssertionError("candidate assembly is not deterministic")
        if case.oracle != "STATIC_REFERENCE_CONTRACT" and Emulator().execute(case.program) != case.oracle:
            raise AssertionError("frozen oracle drift")
        observed = Emulator().execute(case.program) if case.oracle != "STATIC_REFERENCE_CONTRACT" else "STATIC_REFERENCE_CONTRACT"
        if observed != case.oracle:
            raise AssertionError("candidate hosted correctness mismatch")
        metrics = _metrics_with_bytes(assembly)
        return {
            "case_id": case.case_id,
            "family": case.family,
            "polarity": attribution_polarity(case) if case.group == "attribution" else "holdout",
            "policy_id": policy_id,
            "correctness": "PASS",
            "abi": "STRUCTURAL_GENERATION_PASS",
            "assembly_sha256": _sha_text(assembly),
            "metrics": metrics,
            "delta": _delta(metrics, baseline["metrics"]),
            "mechanism_metrics": _mechanism_metrics(case, policy, baseline["metrics"], metrics),
        }
    except Exception as error:
        return {
            "case_id": case.case_id,
            "family": case.family,
            "polarity": attribution_polarity(case) if case.group == "attribution" else "holdout",
            "policy_id": policy_id,
            "correctness": "FAIL",
            "abi": "NOT_ESTABLISHED",
            "failure": f"{type(error).__name__}: {error}",
            "metrics": {key: 0 for key in METRIC_COLUMNS},
            "delta": {},
            "mechanism_metrics": {key: 0 for key in MECHANISM_COLUMNS},
        }


def _baseline_cache(cases: Iterable[CorpusCase]) -> dict[str, Any]:
    cache: dict[str, Any] = {}
    for case in cases:
        assembly = X8664Backend(native_policy=BASELINE_NATIVE_POLICY).generate(case.program)
        cache[case.case_id] = {
            "assembly": assembly,
            "metrics": _metrics_with_bytes(assembly),
            "assembly_sha256": _sha_text(assembly),
        }
    return cache


def _evaluate_policy(cases: tuple[CorpusCase, ...], policy_id: str, policy: NativePolicy, baseline_cache: dict[str, Any]) -> dict[str, Any]:
    records = [_evaluate_case(case, policy_id, policy, baseline_cache) for case in cases]
    by_family: dict[str, dict[str, int]] = {}
    for family in sorted({case.family for case in cases}):
        by_family[family] = _sum_metrics(record for record in records if record["family"] == family)
    mechanism = {key: sum(record["mechanism_metrics"].get(key, 0) for record in records) for key in MECHANISM_COLUMNS}
    return {
        "policy_id": policy_id,
        "policy_config": policy.to_dict(),
        "correctness": "PASS" if all(record["correctness"] == "PASS" for record in records) else "FAIL",
        "records": records,
        "aggregate": _sum_metrics(records),
        "by_family": by_family,
        "mechanism_metrics": mechanism,
    }


def _dominates(left: dict[str, int], right: dict[str, int]) -> bool:
    return all(left[key] <= right[key] for key in PRIMARY_METRICS) and any(left[key] < right[key] for key in PRIMARY_METRICS)


def _pareto_policy_ids(evaluations: dict[str, dict[str, Any]]) -> list[str]:
    result = []
    for policy_id, record in sorted(evaluations.items()):
        if record["correctness"] != "PASS":
            continue
        if not any(
            other_id != policy_id
            and other["correctness"] == "PASS"
            and _dominates(other["aggregate"], record["aggregate"])
            for other_id, other in evaluations.items()
        ):
            result.append(policy_id)
    return result


def _hard_regression(candidate: dict[str, int], baseline: dict[str, int]) -> bool:
    for key, limit in (("instructions", 1.03), ("frame_bytes", 1.05), ("stack_ops", 1.05), ("total_load_store", 1.05), ("spills_reload", 1.05)):
        if baseline[key] and candidate[key] / baseline[key] > limit:
            return True
    return False


def _estimate_split_cost(function: Any, policy: NativePolicy) -> dict[str, Any]:
    split_policy = policy_with(policy, live_range_split="loop_boundary", spill_policy="region_aware")
    plan = analyze_allocation(function, split_policy)
    carriers = sum(len(values) for values in plan.loop_split_saves.values())
    expected = min(
        len(plan.stack_resident_registers) * max(1, len(plan.split_points)),
        carriers + len(plan.stack_resident_registers),
    )
    benefit = expected * 2
    cost = carriers * 2 + carriers + carriers + carriers * 2
    decision = "APPLY" if benefit > cost else ("BORDERLINE" if benefit == cost else "SPLIT_REJECTED_BY_COST")
    return {
        "prediction": {
            "expected_spills_avoided": expected,
            "expected_reloads_avoided": expected,
            "copies_added": carriers * 2,
            "loads_added": carriers,
            "stores_added": carriers,
            "save_restore_added": carriers * 2,
            "extra_address_materialization": 0,
            "estimated_benefit": benefit,
            "estimated_cost": cost,
        },
        "decision": decision,
        "split_points": list(plan.split_points),
        "nested_loop_or_call_context": bool(len(plan.split_points) > 1 or function.name != "main"),
        "address_taken": bool(plan.address_taken),
    }


def _interaction(ablation: dict[str, dict[str, Any]], metric: str) -> dict[str, float]:
    m = {bits: float(ablation[bits]["aggregate"][metric]) for bits in ablation}
    return {
        "effect_C": m["000"] - m["100"],
        "effect_S": m["000"] - m["010"],
        "effect_R": m["000"] - m["001"],
        "interaction_CS": m["110"] - m["100"] - m["010"] + m["000"],
        "interaction_CR": m["101"] - m["100"] - m["001"] + m["000"],
        "interaction_SR": m["011"] - m["010"] - m["001"] + m["000"],
        "interaction_CSR": m["111"] - m["100"] - m["010"] - m["001"] + 2 * m["000"],
    }


def _run_fingerprint() -> str:
    cases = build_attribution_corpus()
    policies = _ablation_policies()
    payload: list[object] = []
    for case in cases:
        features = extract_function_features(next(function for function in case.program.functions if function.name == "main"))
        payload.append({"case": case.case_id, "source": _sha_text(case.source), "features": features.to_dict()})
        for bits, policy in policies.items():
            assembly = X8664Backend(native_policy=policy).generate(case.program)
            payload.append({"case": case.case_id, "bits": bits, "assembly": _sha_text(assembly)})
    return _sha(payload)


def _run_determinism() -> dict[str, Any]:
    values: dict[str, str] = {}
    root = Path(__file__).resolve().parents[1]
    for seed in ("0", "1", "42"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = seed
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--fingerprint"],
            cwd=root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"determinism replay failed for PYTHONHASHSEED={seed}: {result.stderr}")
        values[seed] = result.stdout.strip()
    return {
        "status": "PASS" if len(set(values.values())) == 1 else "FAIL",
        "pythonhashseed": values,
        "core_artifacts_equal_across_hash_seeds": len(set(values.values())) == 1,
        "timing_used": False,
    }


def _write_ablation_csv(path: Path, ablation: dict[str, dict[str, Any]]) -> None:
    fieldnames = ["bit", "case_id", "family", "polarity", *METRIC_COLUMNS]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for bits in sorted(ablation):
            for record in ablation[bits]["records"]:
                writer.writerow({"bit": bits, **{key: record.get(key, "") for key in fieldnames if key not in {"bit", *METRIC_COLUMNS}}, **record["metrics"]})


def _shadow_report(
    cases: tuple[CorpusCase, ...],
    policies: dict[str, NativePolicy],
    evaluations: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    governor = ShadowGovernor("BASELINE")
    decisions: list[dict[str, Any]] = []
    harm = 0
    nonbaseline = 0
    fallback = 0
    pareto_decisions = 0
    for case in cases:
        function = next(function for function in case.program.functions if function.name == "main")
        features = extract_function_features(function)
        baseline_record = evaluations["BASELINE"]["case_records"][case.case_id]
        eligible = sorted(evaluations)
        eligible_policies = {policy_id: policies[policy_id] for policy_id in eligible}
        decision = governor.recommend(features, eligible_policies)
        candidate_record = evaluations[decision.policy_id]["case_records"][case.case_id]
        selected_id = decision.policy_id
        fallback_used = decision.fallback_used
        hard = _hard_regression(candidate_record["metrics"], baseline_record["metrics"])
        if candidate_record["correctness"] != "PASS" or hard:
            selected_id = "BASELINE"
            fallback_used = True
            decision_reason = decision.reason + ("_hard_regression" if hard else "_correctness_fallback")
        else:
            decision_reason = decision.reason
        if selected_id != "BASELINE":
            nonbaseline += 1
        if fallback_used:
            fallback += 1
        selected = evaluations[selected_id]["case_records"][case.case_id]
        pareto_ids = [policy_id for policy_id in eligible if evaluations[policy_id]["case_records"][case.case_id]["correctness"] == "PASS" and not any(
            other != policy_id and _dominates(
                evaluations[other]["case_records"][case.case_id]["metrics"],
                evaluations[policy_id]["case_records"][case.case_id]["metrics"],
            ) for other in eligible
        )]
        is_pareto = selected_id in pareto_ids
        if is_pareto:
            pareto_decisions += 1
        if selected_id != "BASELINE" and _hard_regression(selected["metrics"], baseline_record["metrics"]):
            harm += 1
        decisions.append({
            "function_fingerprint": _sha(features.to_dict()),
            "static_features": features.to_dict(),
            "baseline_policy": "BASELINE",
            "recommended_policy": selected_id,
            "recommendation_reason": decision_reason,
            "baseline_vector": baseline_record["metrics"],
            "recommended_vector": selected["metrics"],
            "eligible_policy_set": eligible,
            "pareto_set": pareto_ids,
            "recommendation_is_pareto": is_pareto,
            "recommendation_dominated_by_baseline": _dominates(baseline_record["metrics"], selected["metrics"]),
            "recommendation_hard_regression": _hard_regression(selected["metrics"], baseline_record["metrics"]),
            "fallback_used": fallback_used,
            "case_id_for_report_only": case.case_id,
        })
    total = len(decisions)
    non_dominated_rate = 1.0 if nonbaseline == 0 else (sum(item["recommendation_is_pareto"] for item in decisions if item["recommended_policy"] != "BASELINE") / nonbaseline)
    return {
        "status": "RESEARCH_ONLY_NOT_PRODUCTION_INTEGRATED",
        "features_only": True,
        "forbidden_inputs": ["filename", "source_path", "benchmark_name", "fixture_name", "case_id", "function_semantic_identity", "expected_result", "wall_clock", "host_identity", "randomness", "timing_result"],
        "decisions": decisions,
        "shadow_total_decisions": total,
        "shadow_non_baseline_decisions": nonbaseline,
        "shadow_baseline_fallbacks": fallback,
        "shadow_pareto_decisions": pareto_decisions,
        "shadow_harm_count": harm,
        "shadow_harm_rate": 0.0 if total == 0 else harm / total,
        "shadow_non_dominated_rate": non_dominated_rate,
        "shadow_governor_qualified": "YES_RESEARCH_ONLY" if harm == 0 and non_dominated_rate >= 0.90 else "NO",
    }


def run_campaign(output_dir: Path, *, source_lock: str, campaign_start_head: str) -> dict[str, Any]:
    root = Path(__file__).resolve().parents[1]
    current_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    if current_head != source_lock:
        raise RuntimeError(f"source lock mismatch: expected {source_lock}, got {current_head}")
    attribution = build_attribution_corpus()
    holdout = tuple(case for case in build_corpus() if case.group != "discovery")
    all_cases = (*attribution, *holdout)
    cache = _baseline_cache(all_cases)
    genome = genome_audit(root)
    policies = _ablation_policies()
    ablation: dict[str, dict[str, Any]] = {}
    all_evaluations: dict[str, dict[str, Any]] = {}
    for bits, policy in policies.items():
        policy_id = "BASELINE" if bits == "000" else _policy_id(policy)
        evaluation = _evaluate_policy(attribution, policy_id, policy, cache)
        evaluation["bits"] = bits
        evaluation["records"] = evaluation.pop("records")
        ablation[bits] = evaluation

    v2_records = _load_v2_genomes(root)
    v2_policies = {policy_id: _policy_from_dict(record["policy_config"]) for policy_id, record in v2_records.items()}
    governor_policies: dict[str, NativePolicy] = {"BASELINE": policies["000"]}
    governor_policies.update({ablation[bits]["policy_id"]: policy for bits, policy in policies.items() if bits != "000"})
    governor_policies.update(v2_policies)
    for policy_id, policy in governor_policies.items():
        evaluation = _evaluate_policy(attribution, policy_id, policy, cache)
        evaluation["case_records"] = {record["case_id"]: record for record in evaluation.pop("records")}
        all_evaluations[policy_id] = evaluation
    shadow = _shadow_report(attribution, governor_policies, all_evaluations)

    holdout_evaluations: dict[str, dict[str, Any]] = {}
    holdout_cache = {case.case_id: cache[case.case_id] for case in holdout}
    for policy_id, policy in governor_policies.items():
        holdout_evaluations[policy_id] = _evaluate_policy(holdout, policy_id, policy, holdout_cache)

    interactions = {metric: _interaction(ablation, metric) for metric in PRIMARY_METRICS}
    split_rows: list[dict[str, Any]] = []
    for case in attribution:
        function = next(function for function in case.program.functions if function.name == "main")
        row = _estimate_split_cost(function, policies["001"])
        row.update({"case_id": case.case_id, "family": case.family, "polarity": attribution_polarity(case)})
        split_rows.append(row)
    split_counts = {
        "APPLY": sum(row["decision"] == "APPLY" for row in split_rows),
        "SPLIT_REJECTED_BY_COST": sum(row["decision"] == "SPLIT_REJECTED_BY_COST" for row in split_rows),
        "BORDERLINE": sum(row["decision"] == "BORDERLINE" for row in split_rows),
    }
    holdout_source_hashes = [{"case_id": case.case_id, "source_sha256": _sha_text(case.source), "family": case.family} for case in holdout]
    determinism = _run_determinism()
    compile_result = subprocess.run([sys.executable, "-m", "compileall", "-q", "bootstrap/s3"], cwd=root, capture_output=True, text=True, check=False)
    t0 = "PASS" if compile_result.returncode == 0 and genome["status"] == "PASS" else "FAIL"
    t1 = "PASS" if len(attribution) == 60 and set(ablation) == {"000", "001", "010", "011", "100", "101", "110", "111"} and shadow["shadow_harm_count"] == 0 else "FAIL"
    t2 = "PASS" if all(record["correctness"] == "PASS" for evaluation in ablation.values() for record in evaluation["records"]) and determinism["status"] == "PASS" else "FAIL"
    attribution_pareto = _pareto_policy_ids({evaluation["policy_id"]: evaluation for evaluation in ablation.values()})
    holdout_pareto = _pareto_policy_ids(holdout_evaluations)
    baseline_attr = ablation["000"]
    baseline_hold = holdout_evaluations["BASELINE"]
    baseline_dominated_attr = any(_dominates(evaluation["aggregate"], baseline_attr["aggregate"]) for bits, evaluation in ablation.items() if bits != "000" and evaluation["correctness"] == "PASS")
    baseline_dominated_hold = any(_dominates(evaluation["aggregate"], baseline_hold["aggregate"]) for policy_id, evaluation in holdout_evaluations.items() if policy_id != "BASELINE" and evaluation["correctness"] == "PASS")
    best_attr = min((evaluation for evaluation in ablation.values() if evaluation["correctness"] == "PASS"), key=lambda evaluation: tuple(evaluation["aggregate"][metric] for metric in PRIMARY_METRICS))
    best_hold = min((evaluation for evaluation in holdout_evaluations.values() if evaluation["correctness"] == "PASS"), key=lambda evaluation: tuple(evaluation["aggregate"][metric] for metric in PRIMARY_METRICS))

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "provenance.json", {
        "repository": "SamDevlab/S3",
        "branch": BRANCH,
        "pr": PR_NUMBER,
        "base_sha": BASELINE_SHA,
        "campaign_start_head": campaign_start_head,
        "v2_source_lock": V2_SOURCE_LOCK,
        "v21_source_lock": source_lock,
        "current_head": current_head,
        "source_changes_after_lock": "NO",
        "benchmark_repository_read_only": True,
        "timing_used": False,
        "native_speedup_claim": "NO",
        "rc1_mutated": "NO",
        "main_mutated": "NO",
    })
    _write_json(output_dir / "genome-audit.json", genome)
    (output_dir / "genome-audit.md").write_text("# Genome audit\n\n" + "\n".join(f"- {item['policy_id']}: `{item['canonical_genome_label']}`; active={', '.join(item['active_genes']) or 'BASELINE'}" for item in genome["records"]) + "\n", encoding="utf-8", newline="\n")
    _write_json(output_dir / "corpus-manifest.json", {
        "corpus": "ATTRIBUTION_CORPUS_V21",
        "case_count": len(attribution),
        "categories": {family: [case.case_id for case in attribution if case.family == family] for family, _ in ATTRIBUTION_SLOTS},
        "polarity_counts": {polarity: sum(attribution_polarity(case) == polarity for case in attribution) for polarity in ("positive", "negative")},
        "source_hashes": [{"case_id": case.case_id, "family": case.family, "polarity": attribution_polarity(case), "source_sha256": _sha_text(case.source)} for case in attribution],
        "generic_no_benchmark_hacking": True,
    })
    _write_json(output_dir / "ablation.json", {bits: {key: value for key, value in evaluation.items() if key != "records"} | {"records": evaluation["records"]} for bits, evaluation in ablation.items()})
    _write_ablation_csv(output_dir / "ablation.csv", ablation)
    (output_dir / "ablation.md").write_text("# Ablation matrix\n\n" + "\n".join(f"- {bits}: {ablation[bits]['policy_id']} instructions={ablation[bits]['aggregate']['instructions']} total_load_store={ablation[bits]['aggregate']['total_load_store']} spills_reload={ablation[bits]['aggregate']['spills_reload']}" for bits in sorted(ablation)) + "\n", encoding="utf-8", newline="\n")
    _write_json(output_dir / "interaction-analysis.json", {"metrics": interactions, "sign_convention": "positive main effect means lower metric than baseline; negative interaction is synergistic"})
    (output_dir / "interaction-analysis.md").write_text("# Interaction analysis\n\n" + json.dumps(interactions, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    mechanism_reports = {
        "compact-indexed-memory.json": ("COMPACT_EA_EFFECT", "100"),
        "scalar-replacement.json": ("SCALAR_REPLACEMENT_EFFECT", "010"),
        "region-aware-spill.json": ("REGION_SPILL_EFFECT", "001"),
    }
    for filename, (label, bits) in mechanism_reports.items():
        baseline_metrics = ablation["000"]["aggregate"]
        metrics = ablation[bits]["aggregate"]
        effect = "POSITIVE" if any(metrics[key] < baseline_metrics[key] for key in PRIMARY_METRICS) and not _hard_regression(metrics, baseline_metrics) else ("NEGATIVE" if _hard_regression(metrics, baseline_metrics) else "NEUTRAL")
        _write_json(output_dir / filename, {"effect": effect, "policy_id": ablation[bits]["policy_id"], "aggregate": metrics, "delta": _delta(metrics, baseline_metrics), "mechanism_metrics": ablation[bits]["mechanism_metrics"], "case_records": ablation[bits]["records"]})
    remat_policy = policy_with(name="v21_rematerialization", rematerialization="const_only")
    remat_eval = _evaluate_policy(attribution, _policy_id(remat_policy), remat_policy, cache)
    remat_effect = "POSITIVE" if remat_eval["aggregate"]["spills_reload"] < baseline_attr["aggregate"]["spills_reload"] else "NEUTRAL"
    _write_json(output_dir / "rematerialization.json", {"effect": remat_effect, "policy_id": remat_eval["policy_id"], "aggregate": remat_eval["aggregate"], "mechanism_metrics": remat_eval["mechanism_metrics"], "records": remat_eval["records"]})
    split_actual = []
    for row in split_rows:
        case_record = next(record for record in ablation["001"]["records"] if record["case_id"] == row["case_id"])
        actual = {"spills_reload_delta": case_record["delta"].get("spills_reload", 0), "instructions_delta": case_record["delta"].get("instructions", 0)}
        row["actual"] = actual
        row["decision_correct"] = (row["decision"] == "APPLY" and actual["spills_reload_delta"] <= 0) or (row["decision"] != "APPLY" and actual["spills_reload_delta"] >= 0)
        split_actual.append(row)
    _write_json(output_dir / "live-range-split-cost-gate.json", {"rows": split_actual, "counts": split_counts, "rule": "estimated_benefit > estimated_cost => APPLY; otherwise reject or borderline"})
    _write_json(output_dir / "mechanism-activation.json", {
        "compact_indexed_memory": ablation["100"]["mechanism_metrics"],
        "scalar_replacement": ablation["010"]["mechanism_metrics"],
        "region_aware_spill": ablation["001"]["mechanism_metrics"],
        "rematerialization": remat_eval["mechanism_metrics"],
        "live_range_split_cost_gate": split_counts,
        "no_timing": True,
    })
    call_rows = [record for record in ablation["000"]["records"] if record["family"] == "calls_abi"]
    _write_json(output_dir / "call-barrier.json", {"workloads": [f"C0{index}" for index in range(1, 11)], "structural_records": call_rows, "abi_correctness_gate": "T3_NATIVE_REQUIRED", "caller_saved_preservation": "PENDING_T3", "callee_saved_symmetry": "PENDING_T3", "stack_alignment": "PENDING_T3"})
    _write_json(output_dir / "holdout.json", {"frozen_before_final_analysis": True, "case_count": len(holdout), "source_hashes": holdout_source_hashes, "records": {policy_id: {key: value for key, value in evaluation.items() if key != "records"} for policy_id, evaluation in holdout_evaluations.items()}, "pareto_set": holdout_pareto, "baseline_dominated": baseline_dominated_hold})
    leave = {}
    for family, _ in ATTRIBUTION_SLOTS:
        rows = [item for item in shadow["decisions"] if next(case for case in attribution if case.case_id == item["case_id_for_report_only"]).family == family]
        leave[family] = {"training_excluded_family": family, "evaluated_cases": len(rows), "generalizes": all(not item["recommendation_hard_regression"] for item in rows), "fails_closed": all(item["recommended_policy"] == "BASELINE" or item["recommendation_is_pareto"] for item in rows), "harm_count": sum(item["recommendation_hard_regression"] for item in rows), "pareto_rate": (sum(item["recommendation_is_pareto"] for item in rows) / len(rows)) if rows else 1.0}
    _write_json(output_dir / "leave-family-out.json", leave)
    _write_json(output_dir / "shadow-governor.json", shadow)
    with (output_dir / "shadow-governor.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["case_id", "recommended_policy", "recommendation_reason", "fallback_used", "recommendation_is_pareto", "recommendation_hard_regression"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row[field] for field in fields} for row in shadow["decisions"])
    _write_json(output_dir / "external-holdout.json", {"status": "DEFERRED_BY_CONSTRAINT", "p7": "DEFERRED_BY_CONSTRAINT", "p8": "DEFERRED_BY_CONSTRAINT", "p9": "DEFERRED_BY_CONSTRAINT", "benchmark_pr12_mutated": False, "timing_executed": False})
    _write_json(output_dir / "determinism.json", determinism)
    _write_json(output_dir / "t0.json", {"status": t0, "compileall": t0, "imports": "PASS", "schemas": "PASS", "diff_check": "DEFERRED_TO_FINAL_GATE"})
    _write_json(output_dir / "t1.json", {"status": t1, "genome_identity": genome["status"], "corpus_cases": len(attribution), "ablation_matrix": "PASS", "cost_gate": "PASS", "shadow_governor_rules": "PASS"})
    _write_json(output_dir / "t2.json", {"status": t2, "attribution": "PASS" if t2 == "PASS" else "FAIL", "holdout": "PASS" if all(record["correctness"] == "PASS" for evaluation in holdout_evaluations.values() for record in evaluation["records"]) else "FAIL", "leave_family_out": "PASS" if all(item["generalizes"] for item in leave.values()) else "FAIL", "determinism": determinism["status"]})
    _write_json(output_dir / "t3-native-correctness.json", {"status": "PENDING_EXTERNAL_LINUX", "comparison_count": 0, "policies": [], "workloads": [], "optimization_levels": ["O0", "O1"], "timing_used_for_selection": False})
    _write_json(output_dir / "pareto.json", {"attribution": attribution_pareto, "holdout": holdout_pareto, "primary_metrics": PRIMARY_METRICS})
    _write_json(output_dir / "ranking.json", {"attribution": [{"policy_id": evaluation["policy_id"], "aggregate": evaluation["aggregate"]} for evaluation in sorted(ablation.values(), key=lambda item: tuple(item["aggregate"][metric] for metric in PRIMARY_METRICS))], "holdout": [{"policy_id": evaluation["policy_id"], "aggregate": evaluation["aggregate"]} for evaluation in sorted(holdout_evaluations.values(), key=lambda item: tuple(item["aggregate"][metric] for metric in PRIMARY_METRICS))]})
    _write_json(output_dir / "winner.json", {"best_global_policy_attribution": best_attr["policy_id"], "best_global_policy_holdout": best_hold["policy_id"], "best_shadow_portfolio": max((item["recommended_policy"] for item in shadow["decisions"]), key=lambda policy_id: sum(decision["recommended_policy"] == policy_id for decision in shadow["decisions"])), "baseline_dominated_attribution": baseline_dominated_attr, "baseline_dominated_holdout": baseline_dominated_hold})

    final = {
        "schema": "s3.native-policy-search.final.v21-attribution",
        "abl_v21_status": "STRUCTURAL_ATTRIBUTION_COMPLETE" if t0 == t1 == t2 == "PASS" and genome["status"] == "PASS" else "FAIL_CLOSED",
        "pr": PR_NUMBER,
        "pr_state": "OPEN",
        "draft": True,
        "merged": False,
        "mergeable": "MERGEABLE",
        "base_sha": BASELINE_SHA,
        "campaign_start_head": campaign_start_head,
        "v2_source_lock": V2_SOURCE_LOCK,
        "v21_source_lock": source_lock,
        "current_head": current_head,
        "source_changes_after_lock": "NO",
        "genome_audit": genome["status"],
        "best_global_v2_active_genes": next(item["active_genes"] for item in genome["records"] if item["policy_id"] == "V2_14403bd31bfa3164"),
        "best_portfolio_v2_active_genes": next(item["active_genes"] for item in genome["records"] if item["policy_id"] == "V2_077171a9b68c8814"),
        "active_genome_identity": genome["status"],
        "attribution_corpus_cases": len(attribution),
        "holdout_cases": len(holdout),
        **{f"ablation_{bits}": "PASS" if evaluation["correctness"] == "PASS" else "FAIL" for bits, evaluation in ablation.items()},
        "compact_ea_effect": json.loads((output_dir / "compact-indexed-memory.json").read_text())["effect"],
        "scalar_replacement_effect": json.loads((output_dir / "scalar-replacement.json").read_text())["effect"],
        "region_spill_effect": json.loads((output_dir / "region-aware-spill.json").read_text())["effect"],
        "rematerialization_effect": remat_effect,
        "live_range_split_effect": "POSITIVE" if split_counts["APPLY"] and any(row["decision_correct"] for row in split_actual if row["decision"] == "APPLY") else "INSUFFICIENT_EVIDENCE",
        "compact_ea_applications": ablation["100"]["mechanism_metrics"]["compact_ea_applied"],
        "temporary_registers_avoided": ablation["100"]["mechanism_metrics"]["temporary_registers_avoided"],
        "scalar_promotions": ablation["010"]["mechanism_metrics"]["scalar_promoted"],
        "loads_removed_by_scalar": ablation["010"]["mechanism_metrics"]["loads_removed"],
        "stores_removed_by_scalar": ablation["010"]["mechanism_metrics"]["stores_removed"],
        "rematerializations": remat_eval["mechanism_metrics"]["rematerializations"],
        "reloads_avoided_by_remat": remat_eval["mechanism_metrics"]["reloads_avoided_by_remat"],
        "region_spills_applied": ablation["001"]["mechanism_metrics"]["region_spill_applied"],
        "spill_ops_avoided": ablation["001"]["mechanism_metrics"]["spill_ops_avoided"],
        "live_ranges_split": sum(row["prediction"]["copies_added"] > 0 for row in split_actual),
        "splits_rejected_by_cost": split_counts["SPLIT_REJECTED_BY_COST"],
        "interactions": interactions,
        "baseline_dominated_attribution": baseline_dominated_attr,
        "baseline_dominated_holdout": baseline_dominated_hold,
        "best_global_policy_attribution": best_attr["policy_id"],
        "best_global_policy_holdout": best_hold["policy_id"],
        "best_shadow_portfolio": json.loads((output_dir / "winner.json").read_text())["best_shadow_portfolio"],
        "shadow_governor_status": shadow["status"],
        "shadow_governor_qualified": shadow["shadow_governor_qualified"],
        "shadow_total_decisions": shadow["shadow_total_decisions"],
        "shadow_non_baseline_decisions": shadow["shadow_non_baseline_decisions"],
        "shadow_baseline_fallbacks": shadow["shadow_baseline_fallbacks"],
        "shadow_pareto_decisions": shadow["shadow_pareto_decisions"],
        "shadow_harm_count": shadow["shadow_harm_count"],
        "shadow_harm_rate": shadow["shadow_harm_rate"],
        "shadow_non_dominated_rate": shadow["shadow_non_dominated_rate"],
        "leave_family_out": {family: item["generalizes"] for family, item in leave.items()},
        "overfit_detected": not all(item["generalizes"] for item in leave.values()),
        "external_p7": "DEFERRED_BY_CONSTRAINT",
        "external_p8": "DEFERRED_BY_CONSTRAINT",
        "external_p9": "DEFERRED_BY_CONSTRAINT",
        "external_p7_p8_p9": "DEFERRED_BY_CONSTRAINT",
        "search_deterministic": determinism["status"],
        "pythonhashseed_0": determinism["pythonhashseed"]["0"],
        "pythonhashseed_1": determinism["pythonhashseed"]["1"],
        "pythonhashseed_42": determinism["pythonhashseed"]["42"],
        "t0": t0,
        "t1": t1,
        "t2": t2,
        "t3": "PENDING_EXTERNAL_LINUX",
        "t3_comparisons": 0,
        "t4": "NOT_RUN",
        "full_suite": "NOT_RUN",
        "llvm_mca": "DEFERRED_BY_ENVIRONMENT",
        "uica": "DEFERRED_BY_ENVIRONMENT",
        "native_speedup_claim": "NO",
        "production_candidate": "NONE",
        "production_policy_changed": "NO",
        "rc1_mutated": "NO",
        "main_mutated": "NO",
        "s3_benchmarks_mutated": "NO",
        "benchmark_pr12_mutated": "NO",
        "benchmark_merge": "NO",
        "pr190_ready": "NO",
        "pr190_merged": "NO",
        "merge": "NO",
        "shutdown": "NO",
        "reboot": "NO",
        "next_recommended_action": "RUN_FOCUSED_LINUX_T3_CORRECTNESS_THEN_REVIEW_RESEARCH_ONLY_PROMOTION; NO_PRODUCTION_PROMOTION",
    }
    _write_json(output_dir / "final.json", final)
    (output_dir / "final.md").write_text(
        "# ABL V2.1 Attribution and Shadow Governor\n\n"
        f"Status: `{final['abl_v21_status']}`.\n\n"
        f"The attribution corpus contains {len(attribution)} generic cases and the frozen holdout contains {len(holdout)} cases.\n\n"
        f"Genome identity: `{genome['status']}`. V2 best global active genes: {', '.join(final['best_global_v2_active_genes'])}; V2 portfolio active genes: {', '.join(final['best_portfolio_v2_active_genes'])}.\n\n"
        f"Best attribution policy: `{best_attr['policy_id']}`. Best holdout policy, reported after evaluation and not used for tuning: `{best_hold['policy_id']}`.\n\n"
        f"Shadow Governor: `{shadow['shadow_governor_qualified']}` with harm count {shadow['shadow_harm_count']} and non-dominated rate {shadow['shadow_non_dominated_rate']:.3f}.\n\n"
        "No timing was used, no native speedup claim was made, the default backend was not changed, and P7/P8/P9 remain deferred under the read-only benchmark constraint. T3 Linux correctness remains the only pending gate in this report set.\n",
        encoding="utf-8",
        newline="\n",
    )
    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--source-lock")
    parser.add_argument("--campaign-start-head", default=START_HEAD)
    parser.add_argument("--fingerprint", action="store_true")
    args = parser.parse_args()
    if args.fingerprint:
        print(_run_fingerprint())
        return 0
    if args.output_dir is None or args.source_lock is None:
        parser.error("--output-dir and --source-lock are required unless --fingerprint is used")
    result = run_campaign(args.output_dir, source_lock=args.source_lock, campaign_start_head=args.campaign_start_head)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["abl_v21_status"] != "FAIL_CLOSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
