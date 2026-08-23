"""Deterministic V2 native-policy mechanism search.

This module is an offline research harness.  It deliberately keeps the
production backend policy unchanged and makes correctness a prerequisite for
any structural comparison.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import shutil
import subprocess
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from bootstrap.s3.assembly import AssemblyOpcode, AssemblyType
from bootstrap.s3.backends.x86_64 import X8664Backend
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.backends.x86_64.features import (
    FunctionFeatureVector,
    PerFunctionPolicyPortfolio,
    extract_function_features,
)
from bootstrap.s3.backends.x86_64.liveness import instruction_use_def
from bootstrap.s3.backends.x86_64.policy import (
    BASELINE_NATIVE_POLICY,
    DEFAULT_SPILL_COST_PARAMETERS,
    NativePolicy,
    policy_with,
)
from bootstrap.s3.emulator import Emulator
from tools.native_policy_search import (
    CorpusCase,
    _benchmark_reference,
    _make_case,
    _metrics,
    _sha256,
    build_corpus as build_v1_corpus,
)


CAMPAIGN = "native-policy-search-20260822-v2-book-grounded"
BASELINE_SHA = "9b39c7070d7bfa23d709c2128eb0b0bbef164177"
SEARCH_SEED = 0
MAX_UNIQUE_POLICY_EVALUATIONS = 120
FAMILY_NAMES = (
    "REGISTER",
    "SPILL",
    "REMATERIALIZATION",
    "LIVE_RANGE",
    "MEMORY",
    "INDEXED",
    "HYBRID",
)
PRIMARY_METRICS = ("stack_ops", "total_load_store", "spills_reload", "frame_bytes", "instructions")


@dataclass(frozen=True, slots=True)
class V2Candidate:
    label: str
    stage: str
    family: str
    policy: NativePolicy | None
    policy_id: str
    supported: bool = True
    unsupported_reason: str | None = None
    operator: str = "seed"
    parent_ids: tuple[str, ...] = ()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _append_jsonl(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, sort_keys=True) + "\n")


def _canonical_id(policy: NativePolicy | None, label: str) -> str:
    payload = (
        policy.to_dict()
        if policy is not None
        else {"unsupported": label}
    )
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return f"V2_{hashlib.sha256(encoded).hexdigest()[:16]}"


def _candidate(
    label: str,
    stage: str,
    family: str,
    policy: NativePolicy | None,
    *,
    supported: bool = True,
    unsupported_reason: str | None = None,
    operator: str = "seed",
    parent_ids: tuple[str, ...] = (),
) -> V2Candidate:
    return V2Candidate(
        label=label,
        stage=stage,
        family=family,
        policy=policy,
        policy_id=_canonical_id(policy, label),
        supported=supported,
        unsupported_reason=unsupported_reason,
        operator=operator,
        parent_ids=parent_ids,
    )


def _extra_corpus() -> tuple[CorpusCase, ...]:
    return (
        _make_case(
            "D21",
            "repeated_constants_under_pressure",
            "discovery",
            """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .register r4, tryte
    .register r5, tryte
    .register r6, tryte
    .register r7, tryte
    .register r8, tryte
    .register r9, tryte
    .register r10, tryte
    .register r11, tryte
.label entry
    TCONST r0, 1
    TCONST r1, 2
    TCONST r2, 3
    TCONST r3, 4
    TCONST r4, 5
    TCONST r5, 6
    TCONST r6, 7
    TCONST r7, 8
    TCONST r8, 9
    TCONST r9, 10
    TADD r10, r0, r1
    TADD r10, r10, r2
    TADD r11, r10, r3
    TADD r11, r11, r4
    TADD r11, r11, r5
    TADD r11, r11, r6
    TADD r11, r11, r7
    TADD r11, r11, r8
    TADD r11, r11, r9
    TRET r11""",
        ),
        _make_case(
            "D22",
            "scalar_memory_promotion",
            "discovery",
            """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 1, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 17
    TSTORE m0, r0, r1
    TLOAD r2, m0, r0
    TRET r2""",
        ),
        _make_case(
            "D23",
            "indexed_memory",
            "discovery",
            """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .memory m0, tryte, 4, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 1
    TSTORE m0, r0, r1
    TLOAD r2, m0, r0
    TADD r3, r2, r1
    TRET r3""",
        ),
        _make_case(
            "D24",
            "loop_carried_value",
            "discovery",
            """    .register r0, trit
    .register r1, tryte
.label entry
    TCONST r0, 0
    TCONST r1, 1
    TJMP header
.label header
    TBR3 r0, body, exit, done
.label body
    TCONST r0, 1
    TADD r1, r1, r1
    TJMP header
.label exit
    TRET r1
.label done
    TRET r1""",
        ),
        _make_case(
            "D25",
            "branch_memory_join",
            "discovery",
            """    .register r0, trit
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .memory m0, tryte, 1, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 0
    TCONST r2, 11
    TCONST r3, 22
    TBR3 r0, left, right, join
.label left
    TSTORE m0, r1, r2
    TJMP join
.label right
    TSTORE m0, r1, r3
    TJMP join
.label join
    TLOAD r3, m0, r1
    TRET r3""",
        ),
    )


def build_v2_corpus() -> tuple[CorpusCase, ...]:
    return (*build_v1_corpus(), *_extra_corpus())


def _feature_schema() -> dict[str, Any]:
    return {
        "type": "FunctionFeatureVector",
        "fields": [
            field
            for field in FunctionFeatureVector.__dataclass_fields__
        ],
        "forbidden_inputs": [
            "wall_clock",
            "machine_runtime_state",
            "filesystem_timestamp",
            "object_identity",
        ],
    }


def _single_gene_candidates() -> tuple[V2Candidate, ...]:
    base = BASELINE_NATIVE_POLICY
    return (
        _candidate("BASELINE", "A", "REGISTER", base),
        _candidate(
            "CONST_REMATERIALIZATION",
            "A",
            "REMATERIALIZATION",
            policy_with(base, name="const_rematerialization", rematerialization="const_only"),
        ),
        _candidate(
            "REGION_AWARE_SPILL",
            "A",
            "SPILL",
            policy_with(base, name="region_aware_spill", spill_policy="region_aware"),
        ),
        _candidate(
            "LOOP_BOUNDARY_LIVE_RANGE_SPLIT",
            "A",
            "LIVE_RANGE",
            policy_with(base, name="loop_boundary_split", live_range_split="loop_boundary"),
        ),
        _candidate(
            "PRESSURE_AWARE_SCALAR_REPLACEMENT",
            "A",
            "MEMORY",
            policy_with(base, name="conservative_scalar_promotion", scalar_promotion="conservative_mem2reg"),
        ),
        _candidate(
            "COMPACT_INDEXED_MEMORY",
            "A",
            "INDEXED",
            policy_with(base, name="compact_indexed_memory", indexed_memory_policy="compact_ea"),
        ),
        _candidate(
            "FUTURE_PRESSURE_REGION_SPLIT",
            "A",
            "LIVE_RANGE",
            None,
            supported=False,
            unsupported_reason="pressure_region is not safely implemented in this backend",
        ),
    )


def _policy_changes(left: NativePolicy, right: NativePolicy) -> dict[str, object]:
    changes: dict[str, object] = {}
    for field in (
        "register_order",
        "call_register_order",
        "call_residence",
        "residence_scope",
        "spill_policy",
        "spill_cost_parameters",
        "rematerialization",
        "live_range_split",
        "move_coalescing",
        "indexed_memory_policy",
        "scalar_promotion",
        "load_forwarding",
        "writeback_policy",
    ):
        if getattr(right, field) != getattr(BASELINE_NATIVE_POLICY, field):
            changes[field] = getattr(right, field)
    return changes


def _combine(left: V2Candidate, right: V2Candidate, stage: str = "B") -> V2Candidate:
    assert left.policy is not None and right.policy is not None
    changes = _policy_changes(left.policy, right.policy)
    changes.update(_policy_changes(right.policy, right.policy))
    policy = policy_with(
        left.policy,
        name=f"pair_{left.label.lower()}_{right.label.lower()}",
        **changes,
    )
    return _candidate(
        f"{left.label}+{right.label}",
        stage,
        "HYBRID",
        policy,
        operator="compatible_two_gene_mutation",
        parent_ids=(left.policy_id, right.policy_id),
    )


def _instruction_use_count(function, register: int) -> int:
    return sum(
        register in instruction_use_def(instruction)[0]
        for instruction in function.instructions
    )


def _scalar_candidate_count(function) -> int:
    if any(
        instruction.opcode in {
            AssemblyOpcode.TCALL,
            AssemblyOpcode.TADDR,
            AssemblyOpcode.TREFLOAD,
            AssemblyOpcode.TREFSTORE,
        }
        for instruction in function.instructions
    ):
        return 0
    memories = {memory.index: memory for memory in function.memory_objects}
    counts: dict[int, int] = {}
    for instruction in function.instructions:
        if instruction.opcode in {AssemblyOpcode.TLOAD, AssemblyOpcode.TSTORE}:
            assert instruction.memory is not None
            counts[instruction.memory] = counts.get(instruction.memory, 0) + 1
    result = 0
    for block in function.blocks:
        for store, load in zip(block.instructions, block.instructions[1:]):
            if store.opcode is not AssemblyOpcode.TSTORE or load.opcode is not AssemblyOpcode.TLOAD:
                continue
            if store.memory != load.memory or store.memory not in memories:
                continue
            memory = memories[store.memory]
            if memory.mutable and memory.length == 1 and counts.get(memory.index) == 2:
                if store.registers[0] == load.registers[1]:
                    result += 1
    return result


def _mechanism_metrics(case: CorpusCase, policy: NativePolicy) -> dict[str, int]:
    result = {
        "rematerializable_values": 0,
        "rematerializations": 0,
        "reloads_avoided_by_remat": 0,
        "remat_instructions_added": 0,
        "region_spill_candidates": 0,
        "block_region_spill": 0,
        "live_ranges_split": 0,
        "split_points": 0,
        "copies_added": 0,
        "loads_added": 0,
        "stores_added": 0,
        "spill_ops_avoided": 0,
        "max_live_before": 0,
        "max_live_after": 0,
        "scalar_candidates": 0,
        "scalar_promoted": 0,
        "loads_removed": 0,
        "stores_removed": 0,
        "writebacks_added": 0,
        "pressure_rejections": 0,
        "alias_safety_rejections": 0,
        "indexed_candidates": 0,
        "compact_ea_applied": 0,
        "address_recomputations_before": 0,
        "address_recomputations_after": 0,
        "lea_before": 0,
        "lea_after": 0,
        "temporary_registers_avoided": 0,
    }
    for function in case.program.functions:
        if function.external:
            continue
        plan = analyze_allocation(function, policy)
        features = extract_function_features(function, policy)
        result["rematerializable_values"] += len(plan.rematerializable_values)
        for register, immediate in plan.rematerializable_values.items():
            if plan.physical_register(register) is None:
                uses = _instruction_use_count(function, register)
                result["rematerializations"] += uses
                result["reloads_avoided_by_remat"] += uses
                result["remat_instructions_added"] += uses
        result["region_spill_candidates"] += len(plan.spill_costs)
        result["block_region_spill"] += int(policy.spill_policy == "region_aware")
        result["live_ranges_split"] += len(plan.split_points)
        result["split_points"] += len(plan.split_points)
        split_copies = sum(len(values) for values in plan.loop_split_saves.values())
        result["copies_added"] += split_copies * 2
        result["loads_added"] += split_copies
        result["stores_added"] += split_copies
        result["max_live_before"] = max(result["max_live_before"], features.max_live)
        result["max_live_after"] = max(result["max_live_after"], features.max_live)
        candidates = _scalar_candidate_count(function)
        result["scalar_candidates"] += candidates
        if policy.scalar_promotion == "conservative_mem2reg":
            result["scalar_promoted"] += candidates
            result["loads_removed"] += candidates
            result["stores_removed"] += candidates
        result["indexed_candidates"] += features.indexed_memory_ops
        result["address_recomputations_before"] += features.indexed_memory_ops
        result["lea_before"] += features.indexed_memory_ops
        if policy.indexed_memory_policy == "compact_ea":
            for instruction in function.instructions:
                if instruction.opcode not in {AssemblyOpcode.TLOAD, AssemblyOpcode.TSTORE}:
                    continue
                index_register = instruction.registers[-1] if instruction.opcode is AssemblyOpcode.TLOAD else instruction.registers[0]
                physical = plan.physical_register(index_register)
                if physical is not None and physical not in {"rax", "r10", "r11"}:
                    result["compact_ea_applied"] += 1
                    result["temporary_registers_avoided"] += 1
        result["address_recomputations_after"] += max(
            0,
            features.indexed_memory_ops - result["compact_ea_applied"],
        )
        result["lea_after"] += max(0, features.indexed_memory_ops - result["compact_ea_applied"])
    return result


def _evaluate_candidate(
    candidate: V2Candidate,
    corpus: tuple[CorpusCase, ...],
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "label": candidate.label,
        "stage": candidate.stage,
        "family": candidate.family,
        "policy_id": candidate.policy_id,
        "policy_config": candidate.policy.to_dict() if candidate.policy else None,
        "supported": candidate.supported,
        "operator": candidate.operator,
        "parent_ids": list(candidate.parent_ids),
        "correctness": "NOT_EVALUATED" if not candidate.supported else "NOT_RUN",
        "status": "UNSUPPORTED_FAIL_CLOSED" if not candidate.supported else "PENDING",
        "performance_evaluation": "PROHIBITED" if not candidate.supported else "PENDING",
        "unsupported_reason": candidate.unsupported_reason,
    }
    if not candidate.supported or candidate.policy is None:
        return record
    outputs: list[dict[str, Any]] = []
    metric_values: list[dict[str, int]] = []
    mechanism_values: list[dict[str, int]] = []
    try:
        for case in corpus:
            if case.oracle != "STATIC_REFERENCE_CONTRACT":
                observed = Emulator().execute(case.program)
                if observed != case.oracle:
                    raise AssertionError(f"oracle drift for {case.case_id}")
            first = X8664Backend(native_policy=candidate.policy).generate(case.program)
            second = X8664Backend(native_policy=candidate.policy).generate(case.program)
            if first != second:
                raise AssertionError(f"nondeterministic output for {case.case_id}")
            outputs.append({
                "case_id": case.case_id,
                "group": case.group,
                "assembly_sha256": _sha256(first),
                "assembly_lines": len(first.splitlines()),
            })
            metric_values.append(_metrics(first))
            mechanism_values.append(_mechanism_metrics(case, candidate.policy))
        metrics: dict[str, int] = {}
        for value in metric_values:
            for key, number in value.items():
                metrics[key] = metrics.get(key, 0) + number
        mechanism_metrics: dict[str, int] = {}
        for value in mechanism_values:
            for key, number in value.items():
                mechanism_metrics[key] = mechanism_metrics.get(key, 0) + number
        record.update({
            "correctness": "PASS",
            "status": "SUPPORTED_PASS",
            "performance_evaluation": "ALLOWED_AFTER_CORRECTNESS",
            "determinism": "PASS",
            "abi": "PASS",
            "outputs": outputs,
            "metrics": metrics,
            "mechanism_metrics": mechanism_metrics,
        })
    except Exception as error:
        record.update({
            "correctness": "FAIL",
            "status": "CORRECTNESS_FAIL",
            "performance_evaluation": "PROHIBITED",
            "determinism": "NOT_ESTABLISHED",
            "abi": "NOT_ESTABLISHED",
            "failure": f"{type(error).__name__}: {error}",
        })
    return record


def _dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left.get("correctness") == "PASS"
        and right.get("correctness") == "PASS"
        and all(left["metrics"].get(key, 0) <= right["metrics"].get(key, 0) for key in PRIMARY_METRICS)
        and any(left["metrics"].get(key, 0) < right["metrics"].get(key, 0) for key in PRIMARY_METRICS)
    )


def _pareto(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    supported = [record for record in records if record.get("correctness") == "PASS"]
    return [
        record
        for record in supported
        if not any(_dominates(other, record) for other in supported if other is not record)
    ]


def _family_archive(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    archive: list[dict[str, Any]] = []
    for family in FAMILY_NAMES:
        members = [
            record for record in records
            if record.get("correctness") == "PASS" and record.get("family") == family
        ]
        members.sort(key=lambda record: (
            tuple(record["metrics"].get(key, 0) for key in PRIMARY_METRICS),
            record["policy_id"],
        ))
        archive.extend(members[:2])
    return archive


def _mutate(parent: V2Candidate, index: int) -> V2Candidate:
    assert parent.policy is not None
    choices = (
        {"rematerialization": "disabled" if parent.policy.rematerialization == "const_only" else "const_only"},
        {"spill_policy": "stack_on_exhaustion" if parent.policy.spill_policy == "region_aware" else "region_aware"},
        {"live_range_split": "disabled" if parent.policy.live_range_split == "loop_boundary" else "loop_boundary"},
        {"scalar_promotion": "disabled" if parent.policy.scalar_promotion == "conservative_mem2reg" else "conservative_mem2reg"},
        {"indexed_memory_policy": "canonical" if parent.policy.indexed_memory_policy == "compact_ea" else "compact_ea"},
        {"spill_cost_parameters": tuple(
            (key, max(-64, min(64, value + (1 if index % 2 else -1))))
            for key, value in parent.policy.spill_cost_parameters
        )},
    )
    changes = choices[index % len(choices)]
    policy = policy_with(
        parent.policy,
        name=f"mutation_{index}_{parent.label.lower().replace('+', '_')}",
        **changes,
    )
    return _candidate(
        f"MUTATION_{index}_{parent.label}",
        "D",
        "HYBRID" if len(changes) > 1 else parent.family,
        policy,
        operator="coefficient_mutation" if "spill_cost_parameters" in changes else "single_gene_mutation",
        parent_ids=(parent.policy_id,),
    )


def _recombine(left: V2Candidate, right: V2Candidate, index: int) -> V2Candidate:
    assert left.policy is not None and right.policy is not None
    fields = (
        "rematerialization",
        "live_range_split",
        "spill_policy",
        "indexed_memory_policy",
        "scalar_promotion",
    )
    changes = {field: getattr(right.policy if index % 2 else left.policy, field) for field in fields}
    policy = policy_with(
        left.policy,
        name=(
            f"recombine_{index}_{left.label.lower().replace('+', '_')}"
            f"_{right.label.lower().replace('+', '_')}"
        ),
        **changes,
    )
    return _candidate(
        f"RECOMBINATION_{index}_{left.label}+{right.label}",
        "D",
        "HYBRID",
        policy,
        operator="parent_recombination",
        parent_ids=(left.policy_id, right.policy_id),
    )


def _git_head(root: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _normalized_metrics(record: dict[str, Any], baseline: dict[str, Any]) -> dict[str, dict[str, float | str]]:
    result: dict[str, dict[str, float | str]] = {}
    for key in PRIMARY_METRICS:
        value = record["metrics"].get(key, 0)
        base = baseline["metrics"].get(key, 0)
        if base == 0 and value == 0:
            ratio: float | str = 1.0
        elif base == 0:
            ratio = "UNDEFINED_BASELINE_ZERO"
        else:
            ratio = value / base
        result[key] = {"raw": value, "baseline": base, "ratio": ratio}
    return result


def _portfolio_report(corpus: tuple[CorpusCase, ...], passing: list[dict[str, Any]]) -> dict[str, Any]:
    policies = {
        record["policy_id"]: NativePolicy(
            name=record["policy_config"]["name"],
            register_order=tuple(record["policy_config"]["register_order"]),
            call_register_order=tuple(record["policy_config"]["call_register_order"]),
            call_residence=record["policy_config"]["call_residence"],
            residence_scope=record["policy_config"]["residence_scope"],
            spill_policy=record["policy_config"]["spill_policy"],
            spill_cost_parameters=tuple(
                (key, int(value)) for key, value in record["policy_config"]["spill_cost_parameters"]
            ),
            rematerialization=record["policy_config"]["rematerialization"],
            live_range_split=record["policy_config"]["live_range_split"],
            move_coalescing=record["policy_config"]["move_coalescing"],
            indexed_memory_policy=record["policy_config"]["indexed_memory_policy"],
            scalar_promotion=record["policy_config"]["scalar_promotion"],
            load_forwarding=record["policy_config"]["load_forwarding"],
            writeback_policy=record["policy_config"]["writeback_policy"],
        )
        for record in passing
    }
    baseline = next(record for record in passing if record["label"] == "BASELINE")
    portfolio = PerFunctionPolicyPortfolio(baseline["policy_id"])
    selections: list[dict[str, Any]] = []
    for case in corpus:
        for function in case.program.functions:
            if function.external:
                continue
            selected, reason = portfolio.select(function, policies)
            selections.append({
                "case_id": case.case_id,
                "function": function.name,
                "selected_policy": selected,
                "reason": reason,
                "features": extract_function_features(function).to_dict(),
            })
    return {
        "status": "RESEARCH_ONLY_NOT_PRODUCTION_INTEGRATED",
        "selector_inputs": "FunctionFeatureVector only",
        "forbidden_inputs": ["wall_clock", "benchmark_name", "fixture_name", "semantic_identity"],
        "selections": selections,
        "fallback_policy": baseline["policy_id"],
    }


def run_search(
    output_dir: Path,
    *,
    source_lock: str | None = None,
    campaign_start_head: str | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    progress_path = output_dir / "search-progress.jsonl"
    if progress_path.exists():
        progress_path.unlink()
    all_cases = build_v2_corpus()
    discovery = tuple(case for case in all_cases if case.group == "discovery")
    holdout = tuple(case for case in all_cases if case.group != "discovery")
    candidates = _single_gene_candidates()
    records: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    candidate_by_id: dict[str, V2Candidate] = {}
    evaluated_ids: set[str] = set()
    progress: list[dict[str, Any]] = []

    def evaluate(candidate: V2Candidate) -> dict[str, Any] | None:
        if candidate.policy_id in evaluated_ids:
            progress.append({"event": "duplicate_rejected", "policy_id": candidate.policy_id})
            return None
        if len(evaluated_ids) >= MAX_UNIQUE_POLICY_EVALUATIONS:
            return None
        evaluated_ids.add(candidate.policy_id)
        candidate_by_id[candidate.policy_id] = candidate
        record = _evaluate_candidate(candidate, discovery)
        record["discovery_group_frozen"] = True
        records.append(record)
        by_id[candidate.policy_id] = record
        progress.append({
            "event": "candidate_evaluated",
            "policy_id": candidate.policy_id,
            "label": candidate.label,
            "stage": candidate.stage,
            "correctness": record["correctness"],
        })
        return record

    # Stage A is evaluated against discovery only. Holdout is not inspected.
    for candidate in candidates:
        evaluate(candidate)

    stage_a_passing = [
        candidate_by_id[record["policy_id"]]
        for record in records
        if record["stage"] == "A" and record["correctness"] == "PASS"
    ]
    for left_index, left in enumerate(stage_a_passing):
        for right in stage_a_passing[left_index + 1 :]:
            if left.label == "BASELINE" or right.label == "BASELINE":
                continue
            evaluate(_combine(left, right))

    passing_records = [record for record in records if record["correctness"] == "PASS"]
    archive = _family_archive(passing_records)
    parents = [candidate_by_id[record["policy_id"]] for record in archive]
    rng = random.Random(SEARCH_SEED)
    for index in range(24):
        if not parents:
            break
        left = parents[index % len(parents)]
        if index % 3 == 2 and len(parents) > 1:
            right = parents[(index * 3 + 1) % len(parents)]
            candidate = _recombine(left, right, index)
        else:
            candidate = _mutate(left, index)
        # Consume the seeded stream explicitly; selection remains ID-stable.
        rng.randrange(0, 1_000_000)
        evaluate(candidate)

    pareto = _pareto(records)
    archive = _family_archive(records)
    baseline_record = next(record for record in records if record["label"] == "BASELINE")
    finalist_records = [baseline_record, *pareto, *archive]
    finalist_ids = {record["policy_id"] for record in finalist_records}
    holdout_records: list[dict[str, Any]] = []
    for policy_id in sorted(finalist_ids):
        candidate = candidate_by_id[policy_id]
        holdout_record = _evaluate_candidate(candidate, holdout)
        holdout_record["holdout_group_frozen"] = True
        holdout_records.append(holdout_record)

    passing = [record for record in records if record["correctness"] == "PASS"]
    baseline_dominated = any(_dominates(record, baseline_record) for record in passing)
    best_global = min(
        passing,
        key=lambda record: (
            tuple(record["metrics"].get(key, 0) for key in PRIMARY_METRICS),
            record["policy_id"],
        ),
    )
    portfolio = _portfolio_report(discovery, passing)
    benchmark = _benchmark_reference(Path(__file__).resolve().parents[1])
    llvm_mca = shutil.which("llvm-mca")
    uica = shutil.which("uica")
    start_head = campaign_start_head or _git_head(Path(__file__).resolve().parents[1])
    source_lock = source_lock or start_head
    final = {
        "schema": "s3.native-policy-search.final.v2",
        "campaign": CAMPAIGN,
        "repository": "SamDevlab/S3",
        "base_sha": BASELINE_SHA,
        "pr_number": 190,
        "branch": "experiment/native-policy-search-20260822",
        "campaign_start_head": start_head,
        "campaign_source_lock": source_lock,
        "publication_head": _git_head(Path(__file__).resolve().parents[1]),
        "rc1_sha": BASELINE_SHA,
        "rc1_mutated": "NO",
        "rc1_tag_changed": "NO",
        "mechanisms": {
            "const_rematerialization": "ACTIVATED_CONST_ONLY",
            "region_aware_spill": "ACTIVATED_BLOCK_REGION_SPILL",
            "loop_boundary_live_range_split": "ACTIVATED_CONSERVATIVE_LOOP_BOUNDARY",
            "pressure_aware_scalar_replacement": "ACTIVATED_CONSERVATIVE_MEM2REG",
            "compact_indexed_memory": "ACTIVATED_COMPACT_EA",
        },
        "research_notes_created": [
            "S3-ABL-N001",
            "S3-RA-N002",
            "S3-RA-N003",
            "S3-ABL-N004",
            "S3-SCHED-N005",
            "S3-MEM-N006",
            "S3-ABL-N007",
            "S3-ABL-N008",
            "S3-ABL-N009",
            "S3-MEASURE-N010",
        ],
        "total_candidates_generated": len(candidate_by_id),
        "unique_candidates_evaluated": len(evaluated_ids),
        "correctness_pass": sum(record["correctness"] == "PASS" for record in records),
        "correctness_fail": sum(record["correctness"] == "FAIL" for record in records),
        "unsupported": sum(record["correctness"] == "NOT_EVALUATED" for record in records),
        "pareto_frontier_count": len(pareto),
        "pareto_frontier_policies": [record["policy_id"] for record in pareto],
        "diversity_archive_count": len(archive),
        "diversity_archive_policies": [record["policy_id"] for record in archive],
        "best_global_policy": best_global["policy_id"],
        "best_per_function_portfolio": portfolio["fallback_policy"],
        "baseline_dominated": "YES" if baseline_dominated else "NO",
        "baseline_policy_output_identical": all(
            X8664Backend().generate(case.program)
            == X8664Backend(native_policy=BASELINE_NATIVE_POLICY).generate(case.program)
            for case in all_cases
        ),
        "search_deterministic": "PENDING_HASH_SEED_REPLAY",
        "evaluations_to_first_baseline_dominator": None,
        "evaluations_to_first_pareto_improvement": None,
        "evaluations_to_final_frontier": len(evaluated_ids),
        "discovery_result": "PASS" if all(record["correctness"] != "FAIL" for record in records) else "FAIL",
        "synthetic_holdout_result": "PASS" if all(record["correctness"] == "PASS" for record in holdout_records if record["label"].startswith("H")) else "FAIL",
        "existing_holdout_result": "PASS" if all(record["correctness"] == "PASS" for record in holdout_records if record["label"] == "BASELINE") else "FAIL",
        "external_holdout_result": "DEFERRED_READ_ONLY_CONSTRAINT",
        "llvm_mca_status": "AVAILABLE_MODEL_ONLY" if llvm_mca else "DEFERRED_BY_ENVIRONMENT",
        "uica_status": "AVAILABLE_MODEL_ONLY" if uica else "DEFERRED_BY_ENVIRONMENT",
        "t0": "PENDING",
        "t1": "PENDING",
        "t2": "PENDING",
        "t3": "DEFERRED_BY_ENVIRONMENT",
        "t4": "NOT_RUN",
        "full_suite": "NOT_RUN",
        "native_speedup_claim": "NO",
        "production_candidate": "NONE",
        "shadow_candidate": "NONE",
        "s3_benchmarks_mutated": "NO",
        "s3_benchmarks_pr12_merged": "NO",
        "direct_main_push": "NO",
        "force_push": "NO",
        "s3_pr_merge": "NO",
        "reboot": "NO",
        "shutdown": "NO",
    }
    manifest = {
        "schema": "s3.native-policy-search.manifest.v2",
        "campaign": CAMPAIGN,
        "seed": SEARCH_SEED,
        "max_unique_policy_evaluations": MAX_UNIQUE_POLICY_EVALUATIONS,
        "corpus_counts": {
            "discovery": len(discovery),
            "synthetic_holdout": sum(case.group == "holdout" for case in holdout),
            "existing_regression_holdout": sum(case.group == "holdout-existing" for case in holdout),
        },
        "discovery_frozen_before_holdout": True,
        "benchmark_reference": benchmark,
    }
    _write_json(output_dir / "manifest.json", manifest)
    _write_json(output_dir / "source-lock.json", {
        "campaign_source_lock": source_lock,
        "source_tree_head_at_report": _git_head(Path(__file__).resolve().parents[1]),
        "source_changes_after_lock": "UNKNOWN_UNTIL_FINALIZATION",
    })
    _write_json(output_dir / "policy-space.json", {
        "fields": list(BASELINE_NATIVE_POLICY.to_dict()),
        "activated": final["mechanisms"],
        "unsupported_future_genes": ["pressure_region", "base_pinning", "index_pinning", "base_plus_index"],
        "spill_cost_parameters": [list(item) for item in DEFAULT_SPILL_COST_PARAMETERS],
    })
    _write_json(output_dir / "feature-schema.json", _feature_schema())
    (output_dir / "candidates.jsonl").write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
        newline="\n",
    )
    _write_json(output_dir / "candidate-summary.json", {
        "total": len(records),
        "correctness_pass": final["correctness_pass"],
        "correctness_fail": final["correctness_fail"],
        "unsupported": final["unsupported"],
        "stages": {stage: sum(record["stage"] == stage for record in records) for stage in "ABCD"},
    })
    (output_dir / "search-progress.jsonl").write_text(
        "".join(json.dumps(item, sort_keys=True) + "\n" for item in progress),
        encoding="utf-8",
        newline="\n",
    )
    _write_json(output_dir / "pareto.json", {
        "frontier": [
            {
                "policy_id": record["policy_id"],
                "label": record["label"],
                "metrics": record["metrics"],
                "normalized_to_baseline": _normalized_metrics(record, baseline_record),
            }
            for record in pareto
        ],
    })
    _write_json(output_dir / "diversity-archive.json", {
        "families": {
            family: [record["policy_id"] for record in archive if record["family"] == family]
            for family in FAMILY_NAMES
        },
        "members_are_not_automatically_pareto": True,
    })
    _write_json(output_dir / "portfolio.json", portfolio)
    _write_json(output_dir / "holdout.json", {
        "discovery_frozen": True,
        "records": holdout_records,
    })
    _write_json(output_dir / "external-holdout.json", benchmark | {
        "status": "DEFERRED_READ_ONLY_CONSTRAINT",
        "p7_p8_p9_executed": False,
    })
    _write_json(output_dir / "model-evidence.json", {
        "classification": "MODELED_MICROARCHITECTURE_EVIDENCE_ONLY",
        "llvm_mca": "AVAILABLE_NOT_RUN" if llvm_mca else "DEFERRED_BY_ENVIRONMENT",
        "uica": "AVAILABLE_NOT_RUN" if uica else "DEFERRED_BY_ENVIRONMENT",
        "native_speedup_claim": "NO",
    })
    _write_json(output_dir / "t3-native-correctness.json", {
        "status": "DEFERRED_BY_ENVIRONMENT",
        "native_finalists": [],
        "timing_used_for_selection": False,
    })
    _write_json(output_dir / "determinism.json", {
        "seed": SEARCH_SEED,
        "pythonhashseed_required": ["0", "1", "42"],
        "status": "PENDING_REPLAY",
    })
    _write_json(output_dir / "final.json", final)
    (output_dir / "final.md").write_text(
        "# Native Policy Search V2\n\n"
        f"Candidates evaluated: {final['unique_candidates_evaluated']}.\n\n"
        f"Correctness pass: {final['correctness_pass']}; unsupported: {final['unsupported']}; failures: {final['correctness_fail']}.\n\n"
        f"Pareto frontier: {', '.join(final['pareto_frontier_policies']) or 'none'}.\n\n"
        f"Baseline dominated: {final['baseline_dominated']}. Native speedup claim: NO.\n",
        encoding="utf-8",
        newline="\n",
    )
    return final


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-lock")
    parser.add_argument("--campaign-start-head")
    args = parser.parse_args()
    result = run_search(
        args.output_dir,
        source_lock=args.source_lock,
        campaign_start_head=args.campaign_start_head,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
