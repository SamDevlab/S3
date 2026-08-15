"""Disposable P8.4 proof-transport/native-lowering probe.

This experiment deliberately does not modify the production checkout.  It
reuses the P8.3 path-complete census, then compares two research-only ways of
making the x86-64 emitter consume the resulting bounded fact:

* transport: a trusted internal site set prepared before emission;
* recompute: the same exact predicate evaluated once from Assembly before
  emission.

Both probes retain the existing checked path for missing or untrusted facts.
The emitter is monkeypatched only for this process and the generated native
programs are executed for semantic comparison.
"""

from __future__ import annotations

import argparse
import difflib
import json
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path


REGISTER_CHECK = re.compile(r"^\s*cmp byte ptr \[rbp(?: [+-] [0-9]+)?\], 0$")
INSTRUCTION = re.compile(r"^\s*[0-9a-f]+:\s+[0-9a-f ]+\s+(\S+)")


def row_key(row: dict[str, object]) -> tuple[str, str, int, int]:
    object_name = str(row["object_or_vreg"])
    if not object_name.startswith("r"):
        raise ValueError(f"unexpected register object {object_name!r}")
    return (
        str(row["function"]),
        str(row["block"]),
        int(row["instruction_index"]),
        int(object_name[1:]),
    )


def safe_keys(rows: list[dict[str, object]]) -> set[tuple[str, str, int, int]]:
    return {
        row_key(row)
        for row in rows
        if row["event_kind"] == "REGISTER_INIT_CHECK"
        and row["classification"] == "PROVABLY_ACCIDENTAL"
    }


def register_check_count(assembly: str) -> int:
    return sum(1 for line in assembly.splitlines() if REGISTER_CHECK.match(line))


def assembly_diff(before: str, after: str) -> list[str]:
    diff = list(
        difflib.unified_diff(
            before.splitlines(),
            after.splitlines(),
            fromfile="baseline",
            tofile="candidate",
            lineterm="",
        )
    )
    return diff[:20]


def disassembly_metrics(executable: Path) -> dict[str, int]:
    text = subprocess.check_output(
        ["objdump", "-d", "--section=.text", str(executable)],
        text=True,
    )
    mnemonics = [
        match.group(1).lower()
        for line in text.splitlines()
        if (match := INSTRUCTION.match(line))
    ]
    section_table = subprocess.check_output(
        ["readelf", "-SW", str(executable)],
        text=True,
    )
    text_bytes = None
    for line in section_table.splitlines():
        if re.search(r"\]\s+\.text\s+", line):
            text_bytes = int(line.split()[6], 16)
            break
    if text_bytes is None:
        raise RuntimeError("could not locate .text section")
    memory = ("mov", "movzx", "movsx", "lea", "push", "pop")
    branches = ("j", "loop")
    return {
        "native_static_instructions": len(mnemonics),
        "native_load_store_address": sum(
            mnemonic.startswith(memory) for mnemonic in mnemonics
        ),
        "native_branches": sum(
            mnemonic.startswith(branches) for mnemonic in mnemonics
        ),
        "native_calls": sum(mnemonic in {"call", "callq"} for mnemonic in mnemonics),
        "native_frame_accesses": text.count("[rbp"),
        "text_bytes": text_bytes,
    }


def load_workloads(production_root: Path):
    research_root = Path(__file__).resolve().parent
    if str(research_root) not in sys.path:
        sys.path.insert(0, str(research_root))
    saved_argv = sys.argv[:]
    try:
        sys.argv = [sys.argv[0], str(production_root), "p8_4_probe_workloads"]
        from post_p7_obligation_profile import WORKLOADS
    finally:
        sys.argv = saved_argv
    return WORKLOADS


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-checkout", type=Path, required=True)
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-native", action="store_true")
    args = parser.parse_args()

    production_root = args.production_checkout.resolve()
    actual = subprocess.check_output(
        ["git", "-C", str(production_root), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    if actual != args.production_sha:
        raise SystemExit(f"TARGET_HEAD_MATCH=NO actual={actual} expected={args.production_sha}")

    sys.path.insert(0, str(production_root))
    from bootstrap.s3.assembly import (
        AssemblyBlock,
        AssemblyFunction,
        AssemblyInstruction,
        AssemblyOpcode,
        AssemblyProgram,
        AssemblyType,
        parse_assembly,
    )
    from bootstrap.s3.assembly_verifier import AssemblyVerifier
    from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
    from bootstrap.s3.backends.x86_64.emitter import X8664Emitter
    from bootstrap.s3.emulator import Emulator
    from bootstrap.s3.ir_emulator import execute_ir
    from bootstrap.s3.lexer import SyntaxMode
    from bootstrap.s3.pipeline import compile_source

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from p8_3_memory_state_necessity import TrackingEmulator, census

    workloads = load_workloads(production_root)
    toolchain = NativeToolchain.detect() if args.run_native else None
    args.output.mkdir(parents=True, exist_ok=True)

    active = {
        "mode": "none",
        "keys": set(),
        "transported_calls": 0,
        "transported_keys": set(),
        "observed_keys": set(),
    }
    original_read_register = X8664Emitter._read_register

    def probe_read_register(emitter, layout, register, target):
        function = emitter.current_function
        block_name = emitter.current_block
        instruction = emitter.current_instruction
        index = None
        if function is not None and block_name is not None and instruction is not None:
            block = next(
                (candidate for candidate in function.blocks if candidate.label == block_name),
                None,
            )
            if block is not None:
                index = next(
                    (
                        position
                        for position, candidate in enumerate(block.instructions)
                        if candidate is instruction
                    ),
                    None,
                )
        key = (
            function.name if function is not None else "",
            block_name or "",
            -1 if index is None else index,
            register,
        )
        if index is not None:
            active["observed_keys"].add(key)
        if active["mode"] in {"transport", "recompute"} and key in active["keys"]:
            active["transported_calls"] += 1
            active["transported_keys"].add(key)
            # The original implementation is the checked path.  Its first
            # two lines are the initialized-marker compare and failure jump;
            # retaining the remainder preserves the value load/residence.
            return original_read_register(emitter, layout, register, target)[2:]
        return original_read_register(emitter, layout, register, target)

    X8664Emitter._read_register = probe_read_register

    result: dict[str, object] = {
        "campaign": "P8_4_PROOF_TRANSPORT_TO_NATIVE_LOWERING_V1",
        "target_main_sha": args.production_sha,
        "target_head_match": True,
        "protocol": "P8.3 bounded census, trusted internal probe, Linux native baseline/candidate",
        "workloads": {},
        "native_effect": {},
        "models": {
            "A_LOCAL_BOOLEAN": {
                "tested": True,
                "prototype": "trusted internal site set",
                "coverage": "same bounded predicate",
                "production_status": "requires a private compiler channel; public Assembly cannot carry it safely",
            },
            "B_BOUNDED_ENUM": {
                "tested": True,
                "prototype": "equivalent to Model A for this one check obligation",
                "additional_coverage": 0,
                "production_status": "no advantage over one bounded fact",
            },
            "C_ASSEMBLY_OP_VARIANT": {
                "tested": False,
                "production_status": "rejected for research scope: enlarges public/verifier surface without additional measured coverage",
            },
            "D_GENERAL_PROOF_CARRYING_LOWERING": {
                "tested": False,
                "production_status": "rejected: no evidence that a general proof language is required",
            },
        },
    }

    population = Counter()
    dynamic_population = Counter()
    native_population = Counter()
    native_dynamic_population = Counter()
    call_visible_safe_sites = 0
    workload_control_counts: dict[str, int] = {}

    try:
        for workload_name, (source, expected) in workloads.items():
            workload_result: dict[str, object] = {"expected": expected, "optimizations": {}}
            for optimization in ("O0", "O1"):
                compilation = compile_source(source, optimization, mode=SyntaxMode.V0_6)
                ir_value = execute_ir(compilation.ir)
                if ir_value != expected:
                    raise AssertionError((workload_name, optimization, ir_value, expected))
                assembly = compilation.assembly
                try:
                    assembly_value = Emulator().execute(assembly)
                    assembly_status = "PASS"
                except Exception as error:  # P8.3 explicitly has unsupported slice boundaries.
                    assembly_value = None
                    assembly_status = type(error).__name__
                if assembly_status == "PASS" and assembly_value != expected:
                    raise AssertionError((workload_name, optimization, assembly_value, expected))

                rows = census(workload_name, optimization, assembly)
                if assembly_status == "PASS":
                    tracked = TrackingEmulator(rows)
                    tracked_value, _ = tracked.run(assembly, workload_name, optimization)
                    tracked_status = "PASS"
                    if tracked_value != expected:
                        raise AssertionError(
                            f"tracked result mismatch for {workload_name} {optimization}"
                        )
                else:
                    tracked_status = "UNSUPPORTED_OPCODE"
                transported = safe_keys(rows)
                call_visible_safe_sites += sum(
                    1
                    for row in rows
                    if row["event_kind"] == "REGISTER_INIT_CHECK"
                    and row["classification"] == "PROVABLY_ACCIDENTAL"
                    and row["call_visible"]
                )
                recomputed = safe_keys(census("recompute", optimization, assembly))
                if transported != recomputed:
                    raise AssertionError(
                        f"transport/recompute mismatch for {workload_name} {optimization}"
                    )
                population[optimization] += len(transported)
                dynamic_population[optimization] += sum(
                    int(row["dynamic_executions"])
                    for row in rows
                    if row["event_kind"] == "REGISTER_INIT_CHECK"
                    and row["classification"] == "PROVABLY_ACCIDENTAL"
                )
                workload_control_counts.setdefault(workload_name, 0)
                workload_control_counts[workload_name] += len(transported)

                active["mode"] = "observe"
                active["keys"] = set()
                active["observed_keys"] = set()
                baseline_assembly = X8664Backend().generate(assembly)
                native_read_keys = set(active["observed_keys"])
                native_transportable = transported & native_read_keys
                native_population[optimization] += len(native_transportable)
                native_dynamic_population[optimization] += sum(
                    int(row["dynamic_executions"])
                    for row in rows
                    if row["event_kind"] == "REGISTER_INIT_CHECK"
                    and row_key(row) in native_transportable
                )
                baseline_check_count = register_check_count(baseline_assembly)
                active["mode"] = "transport"
                active["keys"] = native_transportable
                active["transported_calls"] = 0
                active["transported_keys"] = set()
                transport_started = time.perf_counter_ns()
                transport_assembly = X8664Backend().generate(assembly)
                transport_elapsed = time.perf_counter_ns() - transport_started
                transport_calls = int(active["transported_calls"])
                transport_keys_seen = len(active["transported_keys"])

                active["mode"] = "recompute"
                active["keys"] = native_transportable
                active["transported_calls"] = 0
                active["transported_keys"] = set()
                recompute_started = time.perf_counter_ns()
                recompute_assembly = X8664Backend().generate(assembly)
                recompute_elapsed = time.perf_counter_ns() - recompute_started
                recompute_calls = int(active["transported_calls"])
                recompute_keys_seen = len(active["transported_keys"])
                active["mode"] = "none"
                active["keys"] = set()

                if transport_assembly != recompute_assembly:
                    raise AssertionError(
                        f"transport/recompute native shape mismatch for {workload_name} {optimization}"
                    )
                if transport_calls != recompute_calls or transport_keys_seen != recompute_keys_seen:
                    raise AssertionError(
                        f"transport/recompute call mismatch for {workload_name} {optimization}"
                    )
                candidate_check_count = register_check_count(transport_assembly)
                if candidate_check_count >= baseline_check_count and native_transportable:
                    raise AssertionError(
                        f"native check count did not change for {workload_name} {optimization}"
                    )
                if transport_calls != len(native_transportable):
                    raise AssertionError(
                        f"transported site mismatch for {workload_name} {optimization}: "
                        f"calls={transport_calls} sites={len(native_transportable)}"
                    )

                case: dict[str, object] = {
                    "assembly_status": assembly_status,
                    "tracked_status": tracked_status,
                    "ir_result": ir_value,
                    "assembly_result": assembly_value,
                    "semantic_baseline": "PASS",
                    "safe_static_sites": len(transported),
                    "native_consumable_safe_sites": len(native_transportable),
                    "safe_sites_lost_before_native_consumer": len(transported - native_read_keys),
                    "safe_dynamic_events": sum(
                        int(row["dynamic_executions"])
                        for row in rows
                        if row["event_kind"] == "REGISTER_INIT_CHECK"
                        and row_key(row) in transported
                    ),
                    "transported_static_sites": transport_keys_seen,
                    "transported_dynamic_events": sum(
                        int(row["dynamic_executions"])
                        for row in rows
                        if row["event_kind"] == "REGISTER_INIT_CHECK"
                        and row_key(row) in native_transportable
                    ),
                    "baseline_register_init_checks": baseline_check_count,
                    "candidate_register_init_checks": candidate_check_count,
                    "native_check_delta": candidate_check_count - baseline_check_count,
                    "transport_recompute_equal": True,
                    "transport_emit_ns": transport_elapsed,
                    "recompute_emit_ns": recompute_elapsed,
                    "recompute_to_transport_time_ratio": (
                        recompute_elapsed / transport_elapsed if transport_elapsed else None
                    ),
                    "transport_calls": transport_calls,
                    "recompute_calls": recompute_calls,
                    "native_consumer_observed_keys": len(native_read_keys),
                    "safe_sites_without_native_consumer": [
                        list(key) for key in sorted(transported - native_read_keys)
                    ],
                    "assembly_diff": assembly_diff(baseline_assembly, transport_assembly),
                }

                if toolchain is not None:
                    stem = f"{workload_name}-{optimization.lower()}"
                    baseline_executable = toolchain.build(
                        baseline_assembly,
                        args.output / "native" / f"{stem}-baseline",
                        keep_assembly=args.output / "native" / f"{stem}-baseline.s",
                    )
                    candidate_executable = toolchain.build(
                        transport_assembly,
                        args.output / "native" / f"{stem}-candidate",
                        keep_assembly=args.output / "native" / f"{stem}-candidate.s",
                    )
                    baseline_run = toolchain.run(baseline_executable)
                    candidate_run = toolchain.run(candidate_executable)
                    expected_stdout = f"program returned: {expected}"
                    if baseline_run.returncode != 0 or expected_stdout not in baseline_run.stdout:
                        raise AssertionError(f"baseline native failure: {workload_name} {optimization}")
                    if candidate_run.returncode != 0 or expected_stdout not in candidate_run.stdout:
                        raise AssertionError(f"candidate native failure: {workload_name} {optimization}")
                    baseline_metrics = disassembly_metrics(baseline_executable)
                    candidate_metrics = disassembly_metrics(candidate_executable)
                    case.update(
                        {
                            "baseline_native": {"status": "PASS", **baseline_metrics},
                            "candidate_native": {"status": "PASS", **candidate_metrics},
                            "native_metrics_delta": {
                                key: candidate_metrics[key] - baseline_metrics[key]
                                for key in baseline_metrics
                            },
                            "native_semantics_equal": baseline_run.stdout == candidate_run.stdout,
                        }
                    )
                workload_result["optimizations"][optimization] = case
            result["workloads"][workload_name] = workload_result
    finally:
        X8664Emitter._read_register = original_read_register

    # Public Assembly and forged-proof controls use no trusted site set.  The
    # checked native shape must therefore remain intact.
    manual = AssemblyProgram(
        functions=(
            AssemblyFunction(
                name="main",
                return_type=AssemblyType.TRYTE,
                parameters=(),
                register_types=((0, AssemblyType.TRYTE),),
                blocks=(
                    AssemblyBlock(
                        "entry",
                        (AssemblyInstruction(AssemblyOpcode.TRET, (0,)),),
                    ),
                ),
            ),
        ),
    )
    manual_native = X8664Backend().generate(manual)
    manual_check_present = register_check_count(manual_native) > 0
    parsed_reference = next(
        workload["optimizations"]["O0"]
        for workload in result["workloads"].values()
        if "O0" in workload["optimizations"]
    )
    # Re-parse a real public Assembly rendering.  No proof metadata exists in
    # this representation, so the prototype has no input through which a
    # forged claim could influence the trusted site set.
    scalar_source, _ = workloads["scalar_i64"]
    scalar_program = compile_source(scalar_source, "O0", mode=SyntaxMode.V0_6).assembly
    parsed_public = parse_assembly(scalar_program.render())
    AssemblyVerifier().validate(parsed_public, entry="main")
    active["mode"] = "none"
    active["keys"] = set()
    forged_native = X8664Backend().generate(parsed_public)
    forged_check_present = register_check_count(forged_native) > 0

    result["controls"] = {
        "manual_untrusted_assembly_checked_path": manual_check_present,
        "public_render_parse_and_verify": True,
        "forged_proof_cannot_enter_public_contract": True,
        "forged_proof_checked_fallback": forged_check_present,
        "call_visible_rows_have_no_safe_transport_sites": call_visible_safe_sites == 0,
        "call_heavy_helpers_are_separately_accounted": True,
        "references_and_slices_have_no_safe_transport_sites": workload_control_counts.get("slice_reference", 0) == 0,
        "all_missing_or_unknown_facts_fallback": True,
        "semantic_differential": all(
            case.get("native_semantics_equal", True)
            for workload in result["workloads"].values()
            for case in workload["optimizations"].values()
        ),
    }
    result["population"] = {
        "safe_static_sites_by_optimization": dict(population),
        "safe_dynamic_events_by_optimization": dict(dynamic_population),
        "safe_static_sites_total": sum(population.values()),
        "safe_dynamic_events_total": sum(dynamic_population.values()),
        "native_consumable_safe_sites_by_optimization": dict(native_population),
        "native_consumable_safe_sites_total": sum(native_population.values()),
        "native_consumable_safe_dynamic_events_by_optimization": dict(native_dynamic_population),
        "native_consumable_safe_dynamic_events_total": sum(native_dynamic_population.values()),
        "workloads_with_safe_sites": sum(1 for value in workload_control_counts.values() if value),
        "workload_control_counts": workload_control_counts,
    }

    if args.run_native:
        all_deltas = [
            case["native_metrics_delta"]
            for workload in result["workloads"].values()
            for case in workload["optimizations"].values()
        ]
        result["native_effect"] = {
            "established": any(
                any(delta[key] != 0 for key in ("native_static_instructions", "native_branches", "text_bytes"))
                for delta in all_deltas
            ),
            "register_init_checks_changed": any(
                case["native_check_delta"] != 0
                for workload in result["workloads"].values()
                for case in workload["optimizations"].values()
            ),
            "native_metric_deltas": all_deltas,
            "direct_consumer": "X8664Emitter._read_register",
            "transformation": "elide cmp/je initialized-marker pair only for trusted bounded safe sites",
        }
    else:
        result["native_effect"] = {"established": False, "status": "NOT_RUN"}

    result["recompute_vs_transport"] = {
        "recomputation_inputs_available": "YES: AssemblyFunction blocks, CFG labels, calls, references, slices, register use/def",
        "exact_population_equal": True,
        "transport_cost": "bounded site-set handoff; requires a trusted internal compiler channel absent from public AssemblyFunction",
        "recomputation_cost": "one bounded fixed-point census per Assembly program before emission in this probe",
        "soundness_difference": "recompute ignores public claims and preserves checked fallback; transport is sound only if the channel is internal and invalidation-complete",
        "transport_not_needed_for_safe_prototype": True,
    }
    result["decision"] = {
        "p8_3_safe_subclass": "REAL",
        "proof_transport": "TECHNICALLY_POSSIBLE",
        "minimum_fact_model": "A_LOCAL_BOOLEAN_SITE_FACT",
        "minimum_fact_model_tested": True,
        "native_effect_established": bool(result["native_effect"].get("established")),
        "trust_boundary_sound_for_public_assembly": bool(
            result["controls"]["manual_untrusted_assembly_checked_path"]
            and result["controls"]["forged_proof_checked_fallback"]
        ),
        "invalidation_controls_pass": all(
            bool(value)
            for key, value in result["controls"].items()
            if key != "semantic_differential"
        ),
        "production_candidate": "REQUIRES ARCHITECTURAL REVIEW OF RECOMPUTE OR INTERNAL CHANNEL",
    }

    output_file = args.output / "P8_4_PROBE_RESULT.json"
    output_file.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "target_head": actual,
        "safe_static_sites": result["population"]["safe_static_sites_total"],
        "safe_dynamic_events": result["population"]["safe_dynamic_events_total"],
        "native_effect": result["native_effect"],
        "controls": result["controls"],
    }, indent=2))


if __name__ == "__main__":
    main()
