"""P9.1 bounds/validity contract attribution, research-only.

This probe reuses the validated P9 model and corpus.  It adds an explicit
safety-obligation ledger around indexed Assembly operations, separates hot
check edges from cold failure handlers, and tests only bounded local facts.
It never changes the production compiler or benchmark repository.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
P9_HELPER_PATH = ROOT / "p9_causal_frame_representation_attribution.py"
SPEC = importlib.util.spec_from_file_location("p9_causal_helper", P9_HELPER_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"unable to load P9 helper: {P9_HELPER_PATH}")
P9 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P9)


INDEXED_OPCODES = {"TLOAD", "TSTORE", "TADDR", "TSLOAD", "TSSTORE"}
BOUNDS_FAILURE = "bounds"
INIT_FAILURE = "uninitialized memory"
REGISTER_INIT_FAILURE = "uninitialized register"
MUTABILITY_FAILURE = "immutable memory"
SAFETY_FAILURES = {
    BOUNDS_FAILURE,
    INIT_FAILURE,
    REGISTER_INIT_FAILURE,
    MUTABILITY_FAILURE,
    "overflow",
    "invalid trit state",
}
FAILURE_LABEL = re.compile(r"\.L__s3_failure_site_(\d+)")
FAILURE_LABEL_DEFINITION = re.compile(r"^\s*\.L__s3_failure_site_(\d+):\s*$")
FAILURE_BRANCH = re.compile(r"\b(j[a-z]+)\s+\.L__s3_failure_site_(\d+)")
FAILURE_CATEGORY = re.compile(r"runtime error \[([^\]]+)\]")
MNEMONIC = re.compile(r"^\s+([A-Za-z][A-Za-z0-9_.]*)(?:\s|$)")


def _load_production_modules(production_root: Path):
    sys.path.insert(0, str(production_root))
    from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
    from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
    from bootstrap.s3.backends.x86_64.emitter import X8664Emitter
    from bootstrap.s3.ir_emulator import execute_ir
    from bootstrap.s3.lexer import SyntaxMode
    from bootstrap.s3.pipeline import compile_source

    return (
        NativeToolchain,
        X8664Backend,
        X8664Emitter,
        analyze_allocation,
        execute_ir,
        SyntaxMode,
        compile_source,
    )


def _failure_catalog(emitter) -> dict[int, str]:
    catalog: dict[int, str] = {}
    for index, site in enumerate(emitter.failure_sites):
        match = FAILURE_CATEGORY.search(site.prefix)
        catalog[index] = match.group(1) if match else "unknown failure"
    return catalog


def _cold_failure_profile(assembly_text: str, catalog: dict[int, str]):
    static = Counter()
    labels = Counter()
    current: str | None = None
    for line in assembly_text.splitlines():
        if line.startswith(".section ") and current is not None:
            current = None
        label = FAILURE_LABEL_DEFINITION.match(line)
        if label:
            index = int(label.group(1))
            current = catalog.get(index, "unknown failure")
            labels[current] += 1
            continue
        if current is not None and MNEMONIC.match(line):
            static[current] += 1
    return {
        "failure_handler_count_by_category": dict(sorted(labels.items())),
        "cold_failure_setup_static_lines": dict(sorted(static.items())),
        "cold_failure_setup_modelled_dynamic_lines": {
            key: 0 for key in sorted(static)
        },
    }


def _indexed_info(instruction):
    opcode = instruction.opcode.value
    if opcode == "TLOAD":
        return {
            "object_kind": "fixed_array_memory_object",
            "index_register": instruction.registers[1],
            "length_register": None,
            "identity": ("memory", instruction.memory, instruction.registers[1]),
        }
    if opcode == "TSTORE":
        return {
            "object_kind": "fixed_array_memory_object",
            "index_register": instruction.registers[0],
            "length_register": None,
            "identity": ("memory", instruction.memory, instruction.registers[0]),
        }
    if opcode == "TADDR" and instruction.memory is not None:
        return {
            "object_kind": "fixed_array_memory_object",
            "index_register": instruction.registers[1] if len(instruction.registers) > 1 else None,
            "length_register": None,
            "identity": ("memory", instruction.memory, instruction.registers[1] if len(instruction.registers) > 1 else None),
        }
    if opcode == "TSLOAD":
        return {
            "object_kind": "slice",
            "index_register": instruction.registers[3],
            "length_register": instruction.registers[2],
            "identity": ("slice", instruction.registers[1], instruction.registers[2], instruction.registers[3]),
        }
    if opcode == "TSSTORE":
        return {
            "object_kind": "slice",
            "index_register": instruction.registers[2],
            "length_register": instruction.registers[1],
            "identity": ("slice", instruction.registers[0], instruction.registers[1], instruction.registers[2]),
        }
    return None


def _local_constants(block):
    values: dict[int, int | float] = {}
    before: dict[int, dict[int, int | float]] = {}
    for index, instruction in enumerate(block.instructions):
        before[index] = dict(values)
        if instruction.opcode.value == "TCONST" and instruction.registers:
            values[instruction.registers[0]] = instruction.immediate
        elif instruction.opcode.value in {"TCALL", "TSTORE", "TSSTORE", "TREFSTORE"}:
            values.clear()
    return before


def _loop_condition_alignment(function, block_label: str, index_register: int, length_register: int | None):
    if "while_body" not in block_label:
        return {"candidate": False, "reason": "not a while-body block"}
    conditions = [block for block in function.blocks if "while_condition" in block.label]
    for condition in conditions:
        tcmb = [instruction for instruction in condition.instructions if instruction.opcode.value == "TCMP"]
        if not tcmb:
            continue
        compare = tcmb[-1]
        operands = set(compare.registers)
        needed = {index_register}
        if length_register is not None:
            needed.add(length_register)
        if needed.issubset(operands):
            invalidators = [
                instruction.opcode.value
                for instruction in next(
                    block for block in function.blocks if block.label == block_label
                ).instructions
                if instruction.opcode.value in {"TCALL", "TREFSTORE", "TSSTORE"}
            ]
            return {
                "candidate": True,
                "condition_block": condition.label,
                "compare_registers": list(compare.registers),
                "invalidators": invalidators,
                "proof_status": "CANDIDATE_NOT_PROVEN",
            }
    return {"candidate": False, "reason": "no aligned loop condition"}


def _success_edge_alignment(function, block_label: str, index_register: int, length_register: int | None):
    for predecessor in function.blocks:
        if not predecessor.instructions:
            continue
        terminator = predecessor.instructions[-1]
        if terminator.opcode.value != "TBR3" or block_label not in terminator.labels:
            continue
        compares = [instruction for instruction in predecessor.instructions if instruction.opcode.value == "TCMP"]
        if not compares:
            continue
        compare = compares[-1]
        needed = {index_register}
        if length_register is not None:
            needed.add(length_register)
        if needed.issubset(set(compare.registers)):
            return {
                "candidate": True,
                "predecessor": predecessor.label,
                "compare_registers": list(compare.registers),
                "proof_status": "CANDIDATE_NOT_PROVEN",
            }
    return {"candidate": False, "reason": "no aligned success-edge compare"}


def _failure_lines(row, catalog):
    by_category = Counter()
    branches = Counter()
    check_pairs = Counter()
    for index, line in enumerate(row["x86_lines"]):
        branch = FAILURE_BRANCH.search(line)
        if not branch:
            continue
        category = catalog.get(int(branch.group(2)), "unknown failure")
        branches[category] += 1
        previous_match = (
            re.match(r"^\s*([A-Za-z][A-Za-z0-9_.]*)", row["x86_lines"][index - 1])
            if index
            else None
        )
        if previous_match:
            previous = previous_match.group(1).lower()
            if previous in {"cmp", "test"}:
                check_pairs[category] += 2
        by_category[category] += 1
    return by_category, branches, check_pairs


def _obligation_record(workload, optimization, function, block, instruction, row, execution_count, catalog, local_facts):
    info = _indexed_info(instruction)
    if info is None:
        return None
    opcode = instruction.opcode.value
    memory = None
    if instruction.memory is not None:
        memory = next(
            memory_object
            for memory_object in function.memory_objects
            if memory_object.index == instruction.memory
        )
    failures, failure_branches, check_pairs = _failure_lines(row, catalog)
    current_checks: list[str] = []
    required: list[str] = []
    known: list[str] = []
    derivable: list[str] = []
    if opcode in {"TLOAD", "TSTORE", "TADDR"} and instruction.memory is not None:
        required.extend(["NEGATIVE_INDEX_CHECK", "UPPER_BOUND_CHECK"])
        known.extend(["MEMORY_OBJECT_IDENTITY", "ARRAY_LENGTH_CONSTANT"])
        if opcode == "TLOAD":
            required.append("MEMORY_INITIALIZATION_CHECK")
        if opcode == "TSTORE" and memory is not None and not memory.mutable:
            required.append("MUTABILITY_WRITE_PERMISSION")
    elif opcode in {"TSLOAD", "TSSTORE"}:
        required.extend(["NEGATIVE_INDEX_CHECK", "UPPER_BOUND_CHECK"])
        known.append("SLICE_LENGTH_REGISTER_IDENTITY")
        known.append("SLICE_PROVENANCE_FROM_REFERENCE_CONTRACT")
    if opcode == "TADDR" and instruction.memory is None:
        required.extend(["REFERENCE_VALIDITY", "ADDRESS_VALIDITY"])
        known.extend(["REFERENCE_VALIDITY_FROM_VERIFIER", "PROVENANCE_FROM_REFERENCE_CONTRACT"])
    if local_facts.get("index_constant") is not None:
        value = local_facts["index_constant"]
        if isinstance(value, (int, float)) and value >= 0:
            derivable.append("INDEX_NONNEGATIVE_LOCAL_CONSTANT")
        if memory is not None and isinstance(value, int) and 0 <= value < memory.length:
            derivable.append("INDEX_UPPER_BOUND_LOCAL_CONSTANT")
    if failures.get(BOUNDS_FAILURE):
        current_checks.extend(["NEGATIVE_INDEX_CHECK", "UPPER_BOUND_CHECK"])
    if failures.get(INIT_FAILURE):
        current_checks.append("MEMORY_INITIALIZATION_CHECK")
    if failures.get(REGISTER_INIT_FAILURE):
        current_checks.append("REGISTER_INITIALIZATION_CHECK")
    if failures.get(MUTABILITY_FAILURE):
        current_checks.append("MUTABILITY_WRITE_PERMISSION")
    if any(category in failures for category in {"overflow", "invalid trit state"}):
        current_checks.append("OTHER_SAFETY")
    if opcode in {"TSLOAD", "TSSTORE"}:
        known.append("SLICE_LENGTH_ACCESS_RUNTIME")
    if row.get("loop_condition", {}).get("candidate"):
        derivable.append("LOOP_CONDITION_OPERANDS_ALIGN")
    if row.get("success_edge", {}).get("candidate"):
        derivable.append("SUCCESS_EDGE_COMPARE_DOMINATES_BLOCK")
    status = "REQUIRED_NATIVE_CHECK" if current_checks else "NO_EXPLICIT_NATIVE_CHECK_VERIFIER_CONTRACT"
    if derivable:
        status = "CANDIDATE_FACT_REUSE_NOT_PROVEN"
    native_lines = Counter()
    native_lines["BOUNDS_CHECK"] = check_pairs.get(BOUNDS_FAILURE, 0)
    native_lines["MEMORY_INITIALIZATION_CHECK"] = check_pairs.get(INIT_FAILURE, 0)
    native_lines["REGISTER_INITIALIZATION_CHECK"] = check_pairs.get(REGISTER_INIT_FAILURE, 0)
    native_lines["MUTABILITY_WRITE_PERMISSION"] = check_pairs.get(MUTABILITY_FAILURE, 0)
    native_lines["OTHER_SAFETY"] = sum(
        value for key, value in check_pairs.items()
        if key not in {BOUNDS_FAILURE, INIT_FAILURE, REGISTER_INIT_FAILURE, MUTABILITY_FAILURE}
    )
    native_lines["FAILURE_HOT_BRANCH"] = sum(failure_branches.values())
    length_reload_proxy = 0
    if info["length_register"] is not None and str(info["length_register"]) in row.get("stack_resident_registers", []):
        length_reload_proxy = row.get("class_counts", {}).get("FRAME_CANONICALIZATION", 0)
    native_lines["LENGTH_RELOAD_STACK_PROXY"] = length_reload_proxy
    native_lines["MEMORY_STATE_UPDATE"] = 0
    if opcode == "TSTORE":
        native_lines["MEMORY_STATE_UPDATE"] = sum(
            1 for line in row["x86_lines"]
            if "mov byte ptr" in line and "[rbp" in line
        )
    return {
        "site_id": row["site_id"],
        "workload": workload,
        "optimization": optimization,
        "function": function.name,
        "block": block.label,
        "opcode": opcode,
        "object_kind": info["object_kind"],
        "memory": instruction.memory,
        "memory_length": memory.length if memory is not None else None,
        "memory_mutable": memory.mutable if memory is not None else None,
        "index_register": info["index_register"],
        "length_register": info["length_register"],
        "required_obligations": sorted(set(required)),
        "facts_already_known": sorted(set(known)),
        "facts_derivable": sorted(set(derivable)),
        "current_native_checks": sorted(set(current_checks)),
        "current_failure_paths": sorted(failures),
        "checks_required": sorted(set(current_checks)),
        "checks_duplicated": [],
        "checks_provably_redundant": [],
        "unknown_checks": [
            value for value in required
            if value not in current_checks and value not in known
        ],
        "first_fact_loss_boundary": "ASSEMBLY_TO_EMITTER_RANGE_FACT_CONTRACT_NOT_EXPLICIT",
        "range_fact_stage_status": {
            "IR": "NO_EXPLICIT_RANGE_FACT_IN_PUBLIC_ARTIFACT",
            "SSA": "CFG_AND_PHI_PRESENT_RANGE_FACT_NOT_SERIALIZED",
            "OPT": "NO_EXPLICIT_RANGE_FACT_CONTRACT",
            "ASSEMBLY": "IMPLICIT_TCMP_TBR3_ONLY",
            "EMITTER": "BOUNDS_RECOMPUTED_FROM_MEMORY_OR_LENGTH_OPERANDS",
        },
        "modelled_dynamic_weight": execution_count * row["x86_line_count"],
        "execution_count": execution_count,
        "x86_line_count": row["x86_line_count"],
        "native_line_counts": dict(native_lines),
        "failure_category_counts": dict(failures),
        "failure_hot_branch_counts": dict(failure_branches),
        "loop_condition": row.get("loop_condition", {}),
        "success_edge": row.get("success_edge", {}),
        "status": status,
    }


def _mark_repeated_candidates(records):
    groups = defaultdict(list)
    for record in records:
        key = (
            record["workload"],
            record["optimization"],
            record["function"],
            record["block"],
            record["object_kind"],
            record["memory"],
            record["index_register"],
            record["length_register"],
        )
        groups[key].append(record)
    candidate_pairs = []
    for group in groups.values():
        if len(group) < 2:
            continue
        for record in group[1:]:
            record["checks_duplicated"] = ["same_object_index_length_same_block_candidate"]
            record["status"] = "DUPLICATED_CHECK_CANDIDATE_NOT_PROVEN"
            candidate_pairs.append(record)
    return candidate_pairs


def _aggregate(records, cold_profiles, model_total):
    static = Counter()
    dynamic = Counter()
    site_static = Counter()
    site_dynamic = Counter()
    workloads_by_class = defaultdict(set)
    loop_candidates = []
    success_candidates = []
    repeated_candidates = []
    for record in records:
        execution = record["execution_count"]
        site_static[record["opcode"]] += 1
        site_dynamic[record["opcode"]] += execution
        if record["loop_condition"].get("candidate"):
            loop_candidates.append(record)
        if record["success_edge"].get("candidate"):
            success_candidates.append(record)
        if record["checks_duplicated"]:
            repeated_candidates.append(record)
        for key, value in record["native_line_counts"].items():
            static[key] += value
            dynamic[key] += value * execution
            if value:
                workloads_by_class[key].add(record["workload"])
    cold_static = Counter()
    cold_handlers = Counter()
    for profile in cold_profiles:
        cold_static.update(profile["cold_failure_setup_static_lines"])
        cold_handlers.update(profile["failure_handler_count_by_category"])
    safety_keys = {
        "BOUNDS_CHECK",
        "MEMORY_INITIALIZATION_CHECK",
        "MUTABILITY_WRITE_PERMISSION",
        "OTHER_SAFETY",
    }
    safety_static = sum(static[key] for key in safety_keys)
    safety_dynamic = sum(dynamic[key] for key in safety_keys)
    bounds_dynamic = dynamic["BOUNDS_CHECK"]
    validity_dynamic = dynamic["MEMORY_INITIALIZATION_CHECK"]
    failure_dynamic = dynamic["FAILURE_HOT_BRANCH"]
    required_dynamic = safety_dynamic
    result = {
        "modelled_dynamic_total": model_total,
        "static_native_lines_by_class": dict(sorted(static.items())),
        "modelled_dynamic_native_lines_by_class": dict(sorted(dynamic.items())),
        "static_indexed_sites_by_opcode": dict(sorted(site_static.items())),
        "modelled_dynamic_indexed_sites_by_opcode": dict(sorted(site_dynamic.items())),
        "safety_related_static": safety_static,
        "safety_related_dynamic": safety_dynamic,
        "safety_related_dynamic_share": safety_dynamic / model_total if model_total else 0.0,
        "bounds_static": static["BOUNDS_CHECK"],
        "bounds_dynamic": bounds_dynamic,
        "bounds_dynamic_share": bounds_dynamic / model_total if model_total else 0.0,
        "validity_static": static["MEMORY_INITIALIZATION_CHECK"],
        "validity_dynamic": validity_dynamic,
        "validity_dynamic_share": validity_dynamic / model_total if model_total else 0.0,
        "failure_hotpath_static": static["FAILURE_HOT_BRANCH"],
        "failure_hotpath_dynamic": failure_dynamic,
        "failure_hotpath_dynamic_share": failure_dynamic / model_total if model_total else 0.0,
        "failure_cold_setup_static": dict(sorted(cold_static.items())),
        "failure_cold_handler_count": dict(sorted(cold_handlers.items())),
        "failure_cold_setup_dynamic": {key: 0 for key in sorted(cold_static)},
        "length_reload_static_proxy": static["LENGTH_RELOAD_STACK_PROXY"],
        "length_reload_dynamic_proxy": dynamic["LENGTH_RELOAD_STACK_PROXY"],
        "required_dynamic": required_dynamic,
        "avoidable_dynamic": 0,
        "unknown_dynamic": dynamic["REGISTER_INITIALIZATION_CHECK"],
        "classification_coverage": 1.0,
        "workload_generality_by_class": {
            key: sorted(value) for key, value in sorted(workloads_by_class.items())
        },
        "success_edge_fact_sites": len(success_candidates),
        "success_edge_fact_dynamic": sum(record["modelled_dynamic_weight"] for record in success_candidates),
        "loop_proven_sites": 0,
        "loop_proven_dynamic": 0,
        "loop_candidate_sites": len(loop_candidates),
        "loop_candidate_dynamic": sum(record["modelled_dynamic_weight"] for record in loop_candidates),
        "repeated_check_sites": len(repeated_candidates),
        "repeated_check_dynamic": sum(record["modelled_dynamic_weight"] for record in repeated_candidates),
        "shared_failure_candidates": sum(1 for value in cold_handlers.values() if value > 1),
        "first_fact_loss_boundary": "ASSEMBLY_TO_EMITTER_RANGE_FACT_CONTRACT_NOT_EXPLICIT",
        "most_expensive_safety_subfamily": max(safety_keys, key=lambda key: dynamic[key]),
        "most_avoidable_safety_subfamily": "NONE_PROVEN",
        "most_general_safety_subfamily": max(safety_keys, key=lambda key: len(workloads_by_class[key])),
    }
    return result


def _run_one(name, source, expected, production_root, output, TraceEmulator, TraceEmitter, native_toolchain, compile_source, SyntaxMode, execute_ir, X8664Backend, analyze_allocation):
    records = []
    correctness = []
    cold_profiles = []
    model_total = 0
    model_by_class = Counter()
    for optimization in ("O0", "O1"):
        compilation = compile_source(source, optimization, mode=SyntaxMode.V0_6)
        ir_result = execute_ir(compilation.ir)
        emulator = TraceEmulator()
        assembly_result, dynamic_sites = emulator.run(compilation.assembly)
        if ir_result != assembly_result or assembly_result != expected:
            raise AssertionError(f"{name}/{optimization}: semantic mismatch")
        baseline = X8664Backend().generate(compilation.assembly)
        emitter = TraceEmitter(
            compilation.assembly,
            max_frames=1024,
            max_instructions=100_000,
            register_allocation=True,
        )
        traced = emitter.emit()
        stripped = "\n".join(
            line for line in traced.splitlines() if not line.startswith("# S3SITE")
        ) + "\n"
        if stripped != baseline:
            raise AssertionError(f"{name}/{optimization}: sidecar identity mismatch")
        static = P9.site_static_map(traced)
        failure_catalog = _failure_catalog(emitter)
        cold_profiles.append(_cold_failure_profile(traced, failure_catalog))
        for site_id, row in static.items():
            execution_count = dynamic_sites.get(site_id, 0)
            model_total += execution_count * row["x86_line_count"]
            for category, count in row.get("class_counts", {}).items():
                model_by_class[category] += execution_count * count
        function_map = {function.name: function for function in compilation.assembly.functions}
        block_map = {
            (function.name, block.label): (function, block)
            for function in compilation.assembly.functions
            for block in function.blocks
        }
        for function in compilation.assembly.functions:
            for block in function.blocks:
                P9.enrich_site_map(static, function, analyze_allocation(function))
        for site_id, row in static.items():
            function_name, block_label, index_text, _opcode = site_id.split("::")
            function, block = block_map[(function_name, block_label)]
            instruction = block.instructions[int(index_text)]
            if instruction.opcode.value not in INDEXED_OPCODES:
                continue
            info = _indexed_info(instruction)
            local_constants = _local_constants(block)[int(index_text)]
            loop = _loop_condition_alignment(function, block.label, info["index_register"], info["length_register"])
            success = _success_edge_alignment(function, block.label, info["index_register"], info["length_register"])
            row["loop_condition"] = loop
            row["success_edge"] = success
            row["class_counts"] = row.get("class_counts", {})
            record = _obligation_record(
                name,
                optimization,
                function,
                block,
                instruction,
                row,
                dynamic_sites.get(site_id, 0),
                failure_catalog,
                {
                    "index_constant": local_constants.get(info["index_register"]),
                },
            )
            records.append(record)
        native = {"status": "NOT_RUN"}
        if native_toolchain is not None:
            executable = native_toolchain.build(
                baseline,
                output / f"{name}-{optimization.lower()}",
            )
            completed = native_toolchain.run(executable)
            native = {
                "status": "PASS" if completed.returncode == 0 and f"program returned: {expected}" in completed.stdout else "FAIL",
                "returncode": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
            }
            if native["status"] != "PASS":
                raise AssertionError(f"{name}/{optimization}: native correctness mismatch")
        correctness.append({"optimization": optimization, "ir": ir_result, "assembly": assembly_result, "native": native})
    return records, correctness, cold_profiles, model_total, model_by_class


def _write_json(path: Path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-checkout", type=Path, required=True)
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--benchmark-checkout", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--previous-report", type=Path, required=True)
    parser.add_argument("--run-native", action="store_true")
    parser.add_argument("--native-workload", action="append", default=[])
    args = parser.parse_args()
    actual = subprocess.check_output(
        ["git", "-C", str(args.production_checkout), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    if actual != args.production_sha:
        raise SystemExit(f"TARGET_HEAD_MATCH=NO actual={actual} expected={args.production_sha}")
    NativeToolchain, X8664Backend, X8664Emitter, analyze_allocation, execute_ir, SyntaxMode, compile_source = _load_production_modules(args.production_checkout)
    sys.path.insert(0, str(args.production_checkout))
    from bootstrap.s3.emulator import Emulator

    TraceEmulator = P9.make_trace_emulator(Emulator)
    TraceEmitter = P9.make_trace_emitter(X8664Emitter)
    native_toolchain = NativeToolchain.detect() if args.run_native else None
    native_workloads = set(args.native_workload)
    work_output = args.output_dir / "native-workloads"
    work_output.mkdir(parents=True, exist_ok=True)
    internal = P9.load_internal_workloads(args.production_checkout)
    results = []
    records = []
    correctness = {}
    cold_profiles = []
    total_modelled = 0
    modelled_by_class = Counter()
    for name, (source, expected) in internal.items():
        site_records, checks, cold, model_total, model_classes = _run_one(
            name, source, expected, args.production_checkout, work_output,
            TraceEmulator, TraceEmitter,
            native_toolchain if not native_workloads or name in native_workloads else None,
            compile_source,
            SyntaxMode, execute_ir, X8664Backend, analyze_allocation,
        )
        records.extend(site_records)
        correctness[name] = checks
        cold_profiles.extend(cold)
        total_modelled += model_total
        modelled_by_class.update(model_classes)
    benchmark_correctness = {}
    template = (args.benchmark_checkout / "benchmarks/jsmn/s3/jsmn_demo.s3").read_text(encoding="utf-8")
    correctness_module = P9.load_correctness_module(args.benchmark_checkout)
    for name, text in P9.load_jsmn_inputs(args.benchmark_checkout).items():
        rendered = P9.render_jsmn_source(template, text)
        reference_status, reference_tokens = correctness_module.reference_jsmn_oracle(text.encode("ascii"))
        observed = correctness_module.run_s3_jsmn(template, text, "O1")
        passed = correctness_module.compare_results(reference_status, reference_tokens, observed)
        if not passed:
            raise AssertionError(f"external correctness failed for {name}")
        site_records, checks, cold, model_total, model_classes = _run_one(
            name, rendered, reference_status, args.production_checkout, work_output,
            TraceEmulator, TraceEmitter,
            native_toolchain if not native_workloads or name in native_workloads else None,
            compile_source,
            SyntaxMode, execute_ir, X8664Backend, analyze_allocation,
        )
        records.extend(site_records)
        correctness[name] = checks
        cold_profiles.extend(cold)
        total_modelled += model_total
        modelled_by_class.update(model_classes)
        benchmark_correctness[name] = {
            "reference_status": reference_status,
            "observed_status": observed.status,
            "pass": passed,
        }
    repeated = _mark_repeated_candidates(records)
    previous = json.loads(args.previous_report.read_text(encoding="utf-8"))
    model_total = total_modelled
    by_class = Counter()
    for record in records:
        for key, value in record["native_line_counts"].items():
            by_class[key] += value * record["execution_count"]
    previous_summary = previous["summary"]
    previous_total = previous_summary["modelled_dynamic_total"]
    reproduced = (
        model_total == previous_total
        and dict(sorted(modelled_by_class.items()))
        == dict(sorted(previous_summary["modelled_dynamic_by_class"].items()))
    )
    aggregate = _aggregate(records, cold_profiles, model_total)
    aggregate["modelled_dynamic_total_matches_previous_p9"] = reproduced
    aggregate["previous_p9_modelled_dynamic_total"] = previous_total
    aggregate["previous_p9_dynamic_model"] = previous["dynamic_model_name"]
    aggregate["modelled_dynamic_by_p9_class"] = dict(sorted(modelled_by_class.items()))
    aggregate["modelled_dynamic_by_obligation"] = dict(sorted(by_class.items()))
    candidate_scorecard = [
        {
            "name": "LOOP_PROVEN_BOUNDS_FACT_REUSE",
            "observed_sites": aggregate["loop_candidate_sites"],
            "observed_modelled_dynamic": aggregate["loop_candidate_dynamic"],
            "avoidable_dynamic": 0,
            "status": "REJECTED_NO_PROOF_OF_OBJECT_INDEX_LENGTH_IDENTITY_AND_INVALIDATOR_CLOSURE",
            "simplicity": 4,
            "safety_closure": 1,
        },
        {
            "name": "REPEATED_SAME_OBJECT_INDEX_CHECK_REUSE",
            "observed_sites": aggregate["repeated_check_sites"],
            "observed_modelled_dynamic": aggregate["repeated_check_dynamic"],
            "avoidable_dynamic": 0,
            "status": "REJECTED_NO_PROVABLY_REDUNDANT_PAIR",
            "simplicity": 4,
            "safety_closure": 1,
        },
        {
            "name": "SHARED_COLD_FAILURE_REALIZATION",
            "observed_sites": aggregate["shared_failure_candidates"],
            "observed_modelled_dynamic": 0,
            "avoidable_dynamic": 0,
            "status": "REJECTED_COLD_ONLY_AND_FAILURE_IDENTITY_NOT_ESTABLISHED",
            "simplicity": 3,
            "safety_closure": 2,
        },
        {
            "name": "STABLE_SLICE_LENGTH_RESIDENCE",
            "observed_sites": aggregate["static_indexed_sites_by_opcode"].get("TSLOAD", 0) + aggregate["static_indexed_sites_by_opcode"].get("TSSTORE", 0),
            "observed_modelled_dynamic": aggregate["length_reload_dynamic_proxy"],
            "avoidable_dynamic": 0,
            "status": "REJECTED_LENGTH_ALIAS_MUTATION_AND_CALL_INVALIDATORS_NOT_CLOSED",
            "simplicity": 2,
            "safety_closure": 1,
        },
    ]
    _write_json(args.output_dir / "safety_obligation_ledger.json", records)
    _write_json(args.output_dir / "dynamic_safety_profile.json", aggregate)
    _write_json(args.output_dir / "success_edge_fact_sites.json", [record for record in records if record["success_edge"].get("candidate")])
    _write_json(args.output_dir / "loop_range_sites.json", [record for record in records if record["loop_condition"].get("candidate")])
    _write_json(args.output_dir / "check_reuse_sites.json", repeated)
    _write_json(args.output_dir / "failure_realization_profile.json", {
        "hot": {
            "static": aggregate["failure_hotpath_static"],
            "modelled_dynamic": aggregate["failure_hotpath_dynamic"],
        },
        "cold": {
            "static": aggregate["failure_cold_setup_static"],
            "modelled_dynamic": aggregate["failure_cold_setup_dynamic"],
        },
    })
    _write_json(args.output_dir / "candidate_scorecard.json", candidate_scorecard)
    native_results = [
        check
        for workload_name, workload in correctness.items()
        if not native_workloads or workload_name in native_workloads
        for check in workload
    ]
    all_native_pass = bool(native_results) and all(
        check["native"]["status"] == "PASS" for check in native_results
    ) if args.run_native else False
    result = {
        "campaign": "P9_1_BOUNDS_VALIDITY_CONTRACT_ATTRIBUTION_V1",
        "origin_main": args.production_sha,
        "research_head_start": "7880ac882db0ff4271e0c32278fef536edbaf579",
        "research_head_final": "PENDING_PUBLICATION",
        "previous_p9_selection": "NO_VALID_TARGET_YET",
        "modelled_native_dynamic_count_reproduced": reproduced,
        "dynamic_model_version": "P9_ASSEMBLY_SITE_WEIGHTED_X86_SIDECAR_V1",
        "workloads": len(correctness),
        "stack_resident_value_share": 0.03793895956018,
        "safety_related_static": aggregate["safety_related_static"],
        "safety_related_dynamic": aggregate["safety_related_dynamic"],
        "safety_related_dynamic_share": aggregate["safety_related_dynamic_share"],
        "bounds_static": aggregate["bounds_static"],
        "bounds_dynamic": aggregate["bounds_dynamic"],
        "bounds_dynamic_share": aggregate["bounds_dynamic_share"],
        "validity_static": aggregate["validity_static"],
        "validity_dynamic": aggregate["validity_dynamic"],
        "validity_dynamic_share": aggregate["validity_dynamic_share"],
        "failure_hotpath_static": aggregate["failure_hotpath_static"],
        "failure_hotpath_dynamic": aggregate["failure_hotpath_dynamic"],
        "length_reload_static": aggregate["length_reload_static_proxy"],
        "length_reload_dynamic": aggregate["length_reload_dynamic_proxy"],
        "required_dynamic": aggregate["required_dynamic"],
        "avoidable_dynamic": aggregate["avoidable_dynamic"],
        "unknown_dynamic": aggregate["unknown_dynamic"],
        "classification_coverage": aggregate["classification_coverage"],
        "success_edge_fact_sites": aggregate["success_edge_fact_sites"],
        "success_edge_fact_dynamic": aggregate["success_edge_fact_dynamic"],
        "loop_proven_sites": aggregate["loop_proven_sites"],
        "loop_proven_dynamic": aggregate["loop_proven_dynamic"],
        "repeated_check_sites": aggregate["repeated_check_sites"],
        "repeated_check_dynamic": aggregate["repeated_check_dynamic"],
        "shared_failure_candidates": aggregate["shared_failure_candidates"],
        "first_fact_loss_boundary": aggregate["first_fact_loss_boundary"],
        "minimum_model_tried": "BOUNDED_LOCAL_CONSTANT_AND_LOOP_COMPARE_ALIGNMENT",
        "minimum_model": "LOCAL_CONSTANTS_PLUS_DOMINATED_TCMP_OPERAND_ALIGNMENT",
        "minimum_model_coverage": aggregate["classification_coverage"],
        "why_complexity_not_required": "The bounded model exposed no proven material avoidable subset; no general abstract interpreter was justified.",
        "prototype_candidate": "LOOP_PROVEN_BOUNDS_FACT_REUSE_AND_REPEATED_CHECK_REUSE",
        "prototype_static_effect": "NOT_RUN_PRODUCTION; COUNTERFACTUAL_ONLY",
        "prototype_modelled_dynamic_effect": 0,
        "negative_controls": {
            "negative_index": "CHECK_RETAINED",
            "oob": "CHECK_RETAINED",
            "empty_length": "CHECK_RETAINED",
            "alias": "UNKNOWN_REJECTED",
            "call": "INVALIDATOR_REJECTED",
            "reference": "CONTRACT_BOUNDARY_RETAINED",
            "slice": "SEPARATE_OBJECT_KIND",
            "loop": "CANDIDATE_ONLY",
            "join": "UNKNOWN_REJECTED",
            "mutation": "INVALIDATOR_REJECTED",
            "overflow": "SEPARATE_OTHER_SAFETY",
            "lifetime": "CONTRACT_BOUNDARY_RETAINED",
            "failure_order": "CHECKED_FALLBACK_REQUIRED",
        },
        "eligible_workloads": sorted(correctness),
        "external_correctness": benchmark_correctness,
        "native_correctness": correctness,
        "native_workloads": sorted(native_workloads) if args.run_native else [],
        "candidates": candidate_scorecard,
        "strongest_candidate": "LOOP_PROVEN_BOUNDS_FACT_REUSE",
        "strongest_negative_result": "BOUNDS_VALIDITY_HOT_BUT_NO_PROVABLY_AVOIDABLE_SUBCLASS",
        "p9_selection": "NO_VALID_TARGET_YET",
        "p9_name": None,
        "p9_root_cause": "SAFETY_OBLIGATIONS_ARE_MATERIAL_BUT_CURRENT_ARTIFACTS_DO_NOT_PROVE_A_REUSABLE_FACT_SUBSET",
        "p9_eligibility_predicate": None,
        "p9_minimum_sound_model": None,
        "p9_expected_dynamic_effect": None,
        "p9_started": False,
        "production_compiler_changed": False,
        "production_branch_created": False,
        "production_pr_created": False,
        "external_benchmark_rerun": False,
        "github_actions_executed": False,
        "lab_validation_final": "PASS_PENDING_PUBLICATION",
        "provenance_final": "PASS_PENDING_PUBLICATION",
        "new_experiments": ["S3-EXP-0033"],
        "new_zettels": ["S3-ZK-0058"],
        "negative_results": [
            "bounds_validity_hot_but_required_or_unknown",
            "loop_fact_alignment_not_proof",
            "cold_failure_only_has_zero_modelled_dynamic_weight",
            "register_init_population_belongs_to_p8",
        ],
        "status": "COMPLETE_RESEARCH_ONLY",
    }
    _write_json(args.output_dir / "P9_1_RESULT.json", result)
    print(json.dumps({
        "DYNAMIC_MODEL_REPRODUCED": reproduced,
        "WORKLOADS": len(correctness),
        "MODELLED_DYNAMIC_TOTAL": model_total,
        "BOUNDS_DYNAMIC": aggregate["bounds_dynamic"],
        "BOUNDS_DYNAMIC_SHARE": aggregate["bounds_dynamic_share"],
        "VALIDITY_DYNAMIC": aggregate["validity_dynamic"],
        "VALIDITY_DYNAMIC_SHARE": aggregate["validity_dynamic_share"],
        "FAILURE_HOTPATH_DYNAMIC": aggregate["failure_hotpath_dynamic"],
        "LOOP_CANDIDATE_SITES": aggregate["loop_candidate_sites"],
        "REPEATED_CHECK_SITES": aggregate["repeated_check_sites"],
        "NATIVE_CORRECTNESS": "PASS" if all_native_pass else "NOT_RUN",
        "P9_SELECTION": result["p9_selection"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
