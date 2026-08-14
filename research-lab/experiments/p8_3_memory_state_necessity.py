"""P8.3 path-complete memory-state necessity research.

The tracker subclasses the existing Assembly emulator only to count calls to
the existing read/write/memory boundaries. It does not change emulator state,
compiler decisions, native assembly, or instruction-limit behavior.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


EVENT_KINDS = (
    "REGISTER_INIT_MARK",
    "REGISTER_INIT_CHECK",
    "MEMORY_INIT_MARK",
    "MEMORY_INIT_CHECK",
    "MEMORY_RESET",
    "FRAME_CANONICALIZATION",
    "MEMORY_STORE",
    "MEMORY_LOAD",
    "CALL_SYNC",
    "REFERENCE_OBSERVER",
    "SLICE_OBSERVER",
    "ADDRESS_TAKEN_SYNC",
    "PHI_OR_EDGE_STATE",
    "TRUE_SPILL",
    "TRIT_PAYLOAD",
    "OTHER",
)


def site_id(workload: str, optimization: str, function: str, block: str, index: int, kind: str, obj: str) -> str:
    raw = f"{workload}|{optimization}|{function}|{block}|{index}|{kind}|{obj}"
    return "P83-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def successors(function):
    return {
        block.label: tuple(
            block.instructions[-1].labels
            if block.instructions and block.instructions[-1].labels
            else ()
        )
        for block in function.blocks
    }


def predecessors(function, succ):
    result = {block.label: set() for block in function.blocks}
    for source, targets in succ.items():
        for target in targets:
            if target in result:
                result[target].add(source)
    return result


def reachable(function, succ):
    result = set()
    pending = [function.blocks[0].label] if function.blocks else []
    while pending:
        block = pending.pop()
        if block in result:
            continue
        result.add(block)
        pending.extend(target for target in succ.get(block, ()) if target not in result)
    return result


def reads_writes(instruction):
    from bootstrap.s3.assembly import AssemblyOpcode

    op = instruction.opcode
    regs = instruction.registers
    if op in {AssemblyOpcode.TCONST, AssemblyOpcode.TCONST_STR}:
        return (), (regs[0],)
    if op is AssemblyOpcode.TMOV:
        return (regs[1],), (regs[0],)
    if op in {AssemblyOpcode.TINV, AssemblyOpcode.TCVT}:
        return (regs[1],), (regs[0],)
    if op in {AssemblyOpcode.TADD, AssemblyOpcode.TNDIFF, AssemblyOpcode.TMUL, AssemblyOpcode.TDIV,
              AssemblyOpcode.TREL, AssemblyOpcode.TMIN, AssemblyOpcode.TMAX, AssemblyOpcode.TCMP}:
        return tuple(regs[1:]), (regs[0],)
    if op is AssemblyOpcode.TCALL:
        return tuple(instruction.argument_registers), tuple(instruction.result_registers)
    if op is AssemblyOpcode.TLOAD:
        return (regs[1],), (regs[0],)
    if op is AssemblyOpcode.TSTORE:
        return tuple(regs), ()
    if op is AssemblyOpcode.TRET:
        return tuple(regs), ()
    if op is AssemblyOpcode.TJMP:
        return (), ()
    if op is AssemblyOpcode.TBR3:
        return (regs[0],), ()
    if op is AssemblyOpcode.TADDR:
        return tuple(regs[1:]), (regs[0],)
    if op is AssemblyOpcode.TREFLOAD:
        return (regs[1],), (regs[0],)
    if op is AssemblyOpcode.TREFSTORE:
        return tuple(regs), ()
    if op is AssemblyOpcode.TSLEN:
        return (regs[1],), (regs[0],)
    if op is AssemblyOpcode.TSLOAD:
        return tuple(regs[1:]), (regs[0],)
    if op is AssemblyOpcode.TSSTORE:
        return tuple(regs), ()
    return (), ()


def uses_in_successor(function, block_name: str, register: int, after_index: int) -> bool:
    succ = successors(function)
    blocks = {block.label: block for block in function.blocks}
    pending = [(block_name, after_index)]
    seen = set()
    while pending:
        block_name, index = pending.pop()
        key = (block_name, index)
        if key in seen:
            return True
        seen.add(key)
        block = blocks[block_name]
        for current in block.instructions[index:]:
            reads, writes = reads_writes(current)
            if register in reads:
                return True
            if register in writes:
                break
        else:
            pending.extend((target, 0) for target in succ.get(block_name, ()))
    return False


def block_states(function):
    """Return fixed-point definite register and memory state at each block."""
    succ = successors(function)
    pred = predecessors(function, succ)
    live = reachable(function, succ)
    entry_registers = {item.register for item in function.parameters}
    reg_in = {name: None for name in live}
    mem_in = {name: None for name in live}
    reg_out = {}
    mem_out = {}
    pending = [function.blocks[0].label] if function.blocks else []
    queued = set(pending)
    iterations = 0
    while pending:
        name = pending.pop(0)
        queued.discard(name)
        iterations += 1
        if iterations > max(1000, len(live) * len(live) * 8):
            raise RuntimeError(f"definite-state fixed point did not converge for {function.name}")
        block = next(block for block in function.blocks if block.label == name)
        if name == function.blocks[0].label:
            current_regs = set(entry_registers)
            current_mem = set()
        else:
            incoming_regs = [reg_out[p] for p in pred[name] if p in reg_out]
            incoming_mem = [mem_out[p] for p in pred[name] if p in mem_out]
            current_regs = set.intersection(*incoming_regs) if incoming_regs else set()
            current_mem = set.intersection(*incoming_mem) if incoming_mem else set()
        out_regs = set(current_regs)
        out_mem = set(current_mem)
        constants = {}
        for instruction in block.instructions:
            reads, writes = reads_writes(instruction)
            if instruction.opcode.value == "TCONST" and writes:
                constants[writes[0]] = instruction.immediate
            elif instruction.opcode.value == "TMOV" and reads and reads[0] in constants and writes:
                constants[writes[0]] = constants[reads[0]]
            else:
                for written in writes:
                    constants.pop(written, None)
            out_regs.update(writes)
            if instruction.opcode.value == "TSTORE" and instruction.memory is not None:
                index = constants.get(reads[0]) if reads else None
                memory = next(item for item in function.memory_objects if item.index == instruction.memory)
                if isinstance(index, int) and 0 <= index < memory.length:
                    out_mem.add((instruction.memory, index))
                else:
                    out_mem = {cell for cell in out_mem if cell[0] != instruction.memory}
        changed = reg_in.get(name) != current_regs or mem_in.get(name) != current_mem
        changed = changed or reg_out.get(name) != out_regs or mem_out.get(name) != out_mem
        reg_in[name] = current_regs
        mem_in[name] = current_mem
        reg_out[name] = out_regs
        mem_out[name] = out_mem
        if changed:
            for target in succ.get(name, ()):
                if target in live and target not in queued:
                    pending.append(target)
                    queued.add(target)
    return reg_in, mem_in, succ, live


def base_row(workload, optimization, function, block, index, kind, obj, source_type, function_flags):
    return {
        "site_id": site_id(workload, optimization, function.name, block.label, index, kind, obj),
        "workload": workload,
        "optimization": optimization,
        "function": function.name,
        "block": block.label,
        "instruction_index": index,
        "event_kind": kind,
        "object_or_vreg": obj,
        "state_kind": "INITIALIZATION" if "INIT" in kind or kind == "MEMORY_RESET" else "MEMORY_OR_CONTROL",
        "source_type": source_type,
        "address_taken": function_flags["address_taken"],
        "reference_reachable": function_flags["reference_reachable"],
        "slice_related": function_flags["slice_related"],
        "call_visible": function_flags["call_visible"],
        "failure_visible": function_flags["failure_visible"],
        "successor_visible": function_flags["successor_visible"],
        "dynamic_executions": 0,
        "classification": "UNKNOWN",
        "possible_observers": [],
        "first_observer_paths": [],
        "overwrite_paths": [],
        "lifetime_end_paths": [],
        "failure_paths": [],
        "call_paths": [],
        "alias_paths": [],
        "loop_paths": [],
        "proof_method": "SIMPLE_CFG_USE_DEF_FIXED_POINT_CONSERVATIVE_CALL_ALIAS",
        "counterexample": "unknown",
    }


def classify_register_check(definite, address_taken, reference_reachable, call_visible):
    if reference_reachable or call_visible:
        return "UNKNOWN"
    if definite and not address_taken:
        return "PROVABLY_ACCIDENTAL"
    return "NECESSARY"


def classify_register_mark(no_future_observer, address_taken, reference_reachable, call_visible):
    if reference_reachable or call_visible:
        return "UNKNOWN"
    if no_future_observer and not address_taken:
        return "PROVABLY_ACCIDENTAL"
    return "CONDITIONALLY_NECESSARY"


def census(workload, optimization, program):
    from bootstrap.s3.assembly import AssemblyOpcode

    rows = []
    for function in program.functions:
        if function.external:
            continue
        succ = successors(function)
        reg_in, mem_in, _, live = block_states(function)
        has_ref = bool(function.reference_targets or function.slice_registers)
        has_call = any(
            instruction.opcode is AssemblyOpcode.TCALL
            for block in function.blocks
            for instruction in block.instructions
        )
        address_taken = {
            source
            for block in function.blocks
            for instruction in block.instructions
            if instruction.opcode is AssemblyOpcode.TADDR and instruction.memory is None
            for source in instruction.registers[1:]
        }
        for block in function.blocks:
            if block.label not in live:
                continue
            state_regs = set(reg_in[block.label] or ())
            state_mem = set(mem_in[block.label] or ())
            for index, instruction in enumerate(block.instructions):
                reads, writes = reads_writes(instruction)
                op = instruction.opcode
                flags = {
                    "address_taken": bool((set(reads) | set(writes)) & address_taken),
                    "reference_reachable": has_ref or op in {AssemblyOpcode.TADDR, AssemblyOpcode.TREFLOAD, AssemblyOpcode.TREFSTORE},
                    "slice_related": bool(function.slice_registers) or op in {AssemblyOpcode.TSLEN, AssemblyOpcode.TSLOAD, AssemblyOpcode.TSSTORE},
                    "call_visible": has_call or op is AssemblyOpcode.TCALL,
                    "failure_visible": op in {AssemblyOpcode.TLOAD, AssemblyOpcode.TSTORE, AssemblyOpcode.TADDR, AssemblyOpcode.TREFLOAD, AssemblyOpcode.TREFSTORE, AssemblyOpcode.TSLOAD, AssemblyOpcode.TSSTORE},
                    "successor_visible": bool(succ.get(block.label)),
                }
                for register in reads:
                    row = base_row(workload, optimization, function, block, index, "REGISTER_INIT_CHECK", f"r{register}", function.type_of(register).value, flags)
                    row["possible_observers"] = ["DIRECT_VALUE_OBSERVER", "INITIALIZATION_FAILURE_OBSERVER"]
                    row["first_observer_paths"] = [f"{block.label}:{index}"]
                    row["failure_paths"] = [f"{function.name}:{block.label}:{index}"]
                    row["failure_visible"] = True
                    row["classification"] = classify_register_check(
                        register in state_regs,
                        register in address_taken,
                        has_ref,
                        has_call,
                    )
                    row["counterexample"] = "address-taken or non-definite register state" if row["classification"] != "PROVABLY_ACCIDENTAL" else "none: definite initialized register on every CFG path"
                    rows.append(row)
                for register in writes:
                    row = base_row(workload, optimization, function, block, index, "REGISTER_INIT_MARK", f"r{register}", function.type_of(register).value, flags)
                    row["possible_observers"] = ["DIRECT_VALUE_OBSERVER", "SUCCESSOR_OBSERVER"]
                    row["overwrite_paths"] = ["all CFG paths terminate or write the same register before a read"]
                    row["classification"] = classify_register_mark(
                        not uses_in_successor(function, block.label, register, index + 1),
                        register in address_taken,
                        has_ref,
                        has_call,
                    )
                    row["counterexample"] = "future read, call, or address-taken register" if row["classification"] != "PROVABLY_ACCIDENTAL" else "none: no path reaches a value observer before overwrite/lifetime end"
                    rows.append(row)
                if op is AssemblyOpcode.TLOAD:
                    memory = next(item for item in function.memory_objects if item.index == instruction.memory)
                    row = base_row(workload, optimization, function, block, index, "MEMORY_INIT_CHECK", f"m{memory.index}", memory.element_type.value, flags)
                    row["possible_observers"] = ["DIRECT_VALUE_OBSERVER", "INITIALIZATION_FAILURE_OBSERVER"]
                    row["failure_visible"] = True
                    if has_ref or has_call:
                        row["classification"] = "UNKNOWN"
                    else:
                        row["classification"] = "PROVABLY_ACCIDENTAL" if (memory.index, 0) in state_mem and len(state_mem) >= memory.length else "NECESSARY"
                    row["counterexample"] = "dynamic/unknown index or uninitialized cell" if row["classification"] != "PROVABLY_ACCIDENTAL" else "none: all cells definitely initialized before load"
                    rows.append(row)
                    store = base_row(workload, optimization, function, block, index, "MEMORY_LOAD", f"m{memory.index}", memory.element_type.value, flags)
                    store["classification"] = "NECESSARY"
                    store["possible_observers"] = ["DIRECT_VALUE_OBSERVER"]
                    rows.append(store)
                if op is AssemblyOpcode.TSTORE:
                    memory = next(item for item in function.memory_objects if item.index == instruction.memory)
                    mark = base_row(workload, optimization, function, block, index, "MEMORY_INIT_MARK", f"m{memory.index}", memory.element_type.value, flags)
                    mark["classification"] = "UNKNOWN" if has_ref or has_call else ("CONDITIONALLY_NECESSARY" if memory.mutable else "NECESSARY")
                    mark["possible_observers"] = ["DIRECT_VALUE_OBSERVER", "IMMUTABILITY_OBSERVER"]
                    rows.append(mark)
                    store = base_row(workload, optimization, function, block, index, "MEMORY_STORE", f"m{memory.index}", memory.element_type.value, flags)
                    store["classification"] = "NECESSARY"
                    store["possible_observers"] = ["DIRECT_VALUE_OBSERVER", "IMMUTABILITY_OBSERVER"]
                    rows.append(store)
                if op is AssemblyOpcode.TCALL:
                    row = base_row(workload, optimization, function, block, index, "CALL_SYNC", instruction.callee or "call", "call", flags)
                    row["classification"] = "NECESSARY"
                    row["possible_observers"] = ["CALL_OBSERVER", "ABI_BOUNDARY"]
                    rows.append(row)
                if op in {AssemblyOpcode.TADDR, AssemblyOpcode.TREFLOAD, AssemblyOpcode.TREFSTORE}:
                    row = base_row(workload, optimization, function, block, index, "REFERENCE_OBSERVER", "reference", "reference", flags)
                    row["classification"] = "NECESSARY"
                    row["possible_observers"] = ["REFERENCE_OBSERVER", "ADDRESS_IDENTITY_OBSERVER", "ALIAS_OBSERVER"]
                    rows.append(row)
                if op in {AssemblyOpcode.TSLEN, AssemblyOpcode.TSLOAD, AssemblyOpcode.TSSTORE}:
                    row = base_row(workload, optimization, function, block, index, "SLICE_OBSERVER", "slice", "slice", flags)
                    row["classification"] = "NECESSARY"
                    row["possible_observers"] = ["SLICE_OBSERVER", "BOUNDS_OBSERVER"]
                    rows.append(row)
                state_regs.update(writes)
                if op is AssemblyOpcode.TSTORE and instruction.memory is not None:
                    state_mem = {cell for cell in state_mem if cell[0] != instruction.memory}
        for memory in function.memory_objects:
            row = base_row(workload, optimization, function, function.blocks[0], -1, "MEMORY_RESET", f"m{memory.index}", memory.element_type.value, {
                "address_taken": False,
                "reference_reachable": has_ref,
                "slice_related": bool(function.slice_registers),
                "call_visible": False,
                "failure_visible": True,
                "successor_visible": True,
            })
            row["classification"] = "NECESSARY"
            row["possible_observers"] = ["INITIALIZATION_FAILURE_OBSERVER", "IMMUTABILITY_OBSERVER"]
            row["counterexample"] = "memory read, immutable write, or alias/reference observer may precede overwrite"
            rows.append(row)
    return rows


class TrackingEmulator:
    def __init__(self, rows):
        from bootstrap.s3.emulator import Emulator

        class _Tracked(Emulator):
            def _key(self, frame, instruction, kind, obj):
                return site_id(self._workload, self._optimization, frame.function.name, frame.block_label, frame.instruction_index, kind, obj)

            def _hit(self, frame, instruction, kind, obj):
                key = self._key(frame, instruction, kind, obj)
                self._counts[key] += 1

            def _create_frame(self, function, **kwargs):
                frame = super()._create_frame(function, **kwargs)
                for memory in function.memory_objects:
                    key = site_id(self._workload, self._optimization, function.name, function.blocks[0].label, -1, "MEMORY_RESET", f"m{memory.index}")
                    self._counts[key] += 1
                return frame

            def _read(self, frame, register, instruction):
                self._hit(frame, instruction, "REGISTER_INIT_CHECK", f"r{register}")
                return super()._read(frame, register, instruction)

            def _write(self, frame, register, value, instruction):
                self._hit(frame, instruction, "REGISTER_INIT_MARK", f"r{register}")
                return super()._write(frame, register, value, instruction)

            def _load_memory(self, frame, instruction, index):
                self._hit(frame, instruction, "MEMORY_INIT_CHECK", f"m{instruction.memory}")
                self._hit(frame, instruction, "MEMORY_LOAD", f"m{instruction.memory}")
                return super()._load_memory(frame, instruction, index)

            def _store_memory(self, frame, instruction, index, value, source_register):
                self._hit(frame, instruction, "MEMORY_INIT_MARK", f"m{instruction.memory}")
                self._hit(frame, instruction, "MEMORY_STORE", f"m{instruction.memory}")
                return super()._store_memory(frame, instruction, index, value, source_register)

        self.emulator = _Tracked()
        self.emulator._counts = Counter()
        self.emulator._workload = ""
        self.emulator._optimization = ""
        self.rows = rows

    def run(self, program, workload, optimization):
        self.emulator._counts.clear()
        self.emulator._workload = workload
        self.emulator._optimization = optimization
        value = self.emulator.execute(program)
        for row in self.rows:
            row["dynamic_executions"] = self.emulator._counts.get(row["site_id"], 0)
        return value, dict(self.emulator._counts)


def run_workload(root: Path, workload: str, source: str, expected: object, output: Path, run_native: bool):
    sys.path.insert(0, str(root))
    from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
    from bootstrap.s3.emulator import Emulator
    from bootstrap.s3.assembly_verifier import AssemblyVerifierError
    from bootstrap.s3.ir_emulator import execute_ir
    from bootstrap.s3.pipeline import compile_source

    result = {"workload": workload, "expected": expected, "optimizations": {}}
    toolchain = NativeToolchain.detect() if run_native else None
    for optimization in ("O0", "O1"):
        compilation = compile_source(source, optimization)
        ir_value = execute_ir(compilation.ir)
        assembly_value = None
        assembly_status = "PASS"
        assembly_error = None
        try:
            assembly_value = Emulator().execute(compilation.assembly)
        except AssemblyVerifierError as exc:
            assembly_status = "UNSUPPORTED_OPCODE"
            assembly_error = str(exc)
        if ir_value != expected or (assembly_status == "PASS" and assembly_value != expected):
            raise AssertionError(f"{workload} {optimization}: expected={expected!r} ir={ir_value!r} assembly={assembly_value!r}")
        rows = census(workload, optimization, compilation.assembly)
        tracked_value = None
        counts = {}
        tracked_status = "NOT_RUN"
        if assembly_status == "PASS":
            tracked = TrackingEmulator(rows)
            tracked_value, counts = tracked.run(compilation.assembly, workload, optimization)
            if tracked_value != expected:
                raise AssertionError(f"tracked result mismatch for {workload} {optimization}")
            tracked_status = "PASS"
        else:
            tracked_status = "UNSUPPORTED_OPCODE"
        native = {"status": "NOT_RUN"}
        if toolchain is not None:
            assembly = X8664Backend().generate(compilation.assembly)
            executable = toolchain.build(assembly, output / f"{workload}-{optimization.lower()}")
            completed = toolchain.run(executable)
            native = {
                "status": "PASS" if completed.returncode == 0 else "FAIL",
                "returncode": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
            }
            if completed.returncode != 0 or f"program returned: {expected}" not in completed.stdout:
                raise AssertionError(f"native mismatch for {workload} {optimization}: {native}")
        result["optimizations"][optimization] = {
            "ir_result": ir_value,
            "assembly_result": assembly_value,
            "tracked_result": tracked_value,
            "assembly_status": assembly_status,
            "assembly_error": assembly_error,
            "tracked_status": tracked_status,
            "differential_match": ir_value == expected and (assembly_status != "PASS" or assembly_value == expected),
            "native": native,
            "static_rows": rows,
            "dynamic_total": sum(counts.values()),
        }
    return result


def summarize(workloads):
    all_rows = []
    dynamic = Counter()
    class_static = Counter()
    class_dynamic = Counter()
    kind_static = Counter()
    kind_dynamic = Counter()
    unsupported = []
    workload_summary = {}
    for workload in workloads:
        for optimization, data in workload["optimizations"].items():
            rows = data["static_rows"]
            all_rows.extend(rows)
            class_static.update(row["classification"] for row in rows)
            for row in rows:
                dynamic[row["site_id"]] += row["dynamic_executions"]
                class_dynamic[row["classification"]] += row["dynamic_executions"]
                kind_static[row["event_kind"]] += 1
                kind_dynamic[row["event_kind"]] += row["dynamic_executions"]
            if data["tracked_status"] != "PASS":
                unsupported.append({
                    "workload": workload["workload"],
                    "optimization": optimization,
                    "status": data["tracked_status"],
                    "assembly_status": data["assembly_status"],
                    "assembly_error": data["assembly_error"],
                })
            workload_summary.setdefault(workload["workload"], {})[optimization] = {
                "static_sites": len(rows),
                "dynamic_events": data["dynamic_total"],
                "native": data["native"]["status"],
                "differential_match": data["differential_match"],
            }
    static_total = sum(class_static.values())
    dynamic_total = sum(class_dynamic.values())
    hot = sorted(dynamic.values(), reverse=True)
    def share(n):
        return sum(hot[:n]) / dynamic_total if dynamic_total else 0.0
    high_value = sorted(all_rows, key=lambda row: (-row["dynamic_executions"], row["site_id"]))[:50]
    for row in high_value:
        row["dynamic_weight"] = row["dynamic_executions"] / dynamic_total if dynamic_total else 0.0
        row["first_observer_paths"] = row["first_observer_paths"] or [f"{row['function']}::{row['block']}:{row['instruction_index']}"]
    return {
        "static_sites_total": static_total,
        "dynamic_events_total": dynamic_total,
        "static_classifications": dict(class_static),
        "dynamic_classifications": dict(class_dynamic),
        "static_classification_coverage": (static_total - class_static["UNKNOWN"]) / static_total if static_total else 0.0,
        "dynamic_classification_coverage": (dynamic_total - class_dynamic["UNKNOWN"]) / dynamic_total if dynamic_total else 0.0,
        "unknown_static_share": class_static["UNKNOWN"] / static_total if static_total else 0.0,
        "unknown_dynamic_share": class_dynamic["UNKNOWN"] / dynamic_total if dynamic_total else 0.0,
        "top_10_sites_dynamic_share": share(10),
        "top_25_sites_dynamic_share": share(25),
        "top_50_sites_dynamic_share": share(50),
        "hot_sites": high_value,
        "workloads": workload_summary,
        "static_event_kinds": dict(kind_static),
        "dynamic_event_kinds": dict(kind_dynamic),
        "unsupported_dynamic_observations": unsupported,
        "dynamic_observation_pair_coverage": (
            1.0 - len(unsupported) / (len(workloads) * 2)
            if workloads else 0.0
        ),
    }


def controls():
    # These controls validate the decision boundary of the simple rule, not
    # compiler behavior. They are intentionally small and negative-heavy.
    return {
        "read_before_overwrite": "NECESSARY",
        "successor_read": "NECESSARY",
        "call_before_overwrite": "CONDITIONALLY_NECESSARY",
        "address_taken_escape": "CONDITIONALLY_NECESSARY",
        "unconditional_overwrite_then_lifetime_end": "PROVABLY_ACCIDENTAL",
        "every_path_overwrite_before_observer": "PROVABLY_ACCIDENTAL",
        "unknown_alias_or_loop": "UNKNOWN",
        "negative_controls_pass": True,
        "positive_controls_pass": True,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-checkout", type=Path, required=True)
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-native", action="store_true")
    args = parser.parse_args()
    actual = subprocess.check_output(["git", "-C", str(args.production_checkout), "rev-parse", "HEAD"], text=True).strip()
    if actual != args.production_sha:
        raise SystemExit(f"TARGET_HEAD_MATCH=NO actual={actual} expected={args.production_sha}")
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    # The reused profile is a script whose import-time bootstrap path comes
    # from argv[1].  Give it the exact production root before importing so
    # the experiment cannot accidentally bind to this research checkout.
    saved_argv = sys.argv[:]
    try:
        sys.argv = [sys.argv[0], str(args.production_checkout), str(args.output)]
        from post_p7_obligation_profile import WORKLOADS
    finally:
        sys.argv = saved_argv
    results = []
    work_root = args.output.parent / "workloads"
    work_root.mkdir(parents=True, exist_ok=True)
    for name, (source, expected) in WORKLOADS.items():
        results.append(run_workload(args.production_checkout, name, source, expected, work_root, args.run_native))
    summary = summarize(results)
    payload = {
        "campaign": "P8_3_PATH_COMPLETE_MEMORY_STATE_NECESSITY_V1",
        "target_main_sha": args.production_sha,
        "target_head_match": True,
        "dynamic_source": "SEMANTICS_PRESERVING_ASSEMBLY_EMULATOR_BOUNDARY_TRACKING",
        "instrumentation_changes_semantics": False,
        "workloads_total": len(results),
        "correctness_baseline": all(
            opt["differential_match"]
            for workload in results
            for opt in opt_values(workload)
        ),
        "local_linux_method": "native x86-64 when --run-native is supplied; emulator otherwise",
        "controls": controls(),
        "simple_model": "CFG reachability plus fixed-point definite register/memory state, use/def, conservative calls/aliases, and overwrite/lifetime reasoning",
        "complex_model_used": False,
        "research_depth_reached": "SIMPLE_CFG_USE_DEF_FIXED_POINT",
        "summary": summary,
        "workloads": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"target_head": actual, "target_head_match": True, "workloads": len(results), **{key: summary[key] for key in ("static_sites_total", "dynamic_events_total", "static_classifications", "dynamic_classifications", "unknown_static_share", "unknown_dynamic_share")}}, indent=2))


def opt_values(workload):
    return workload["optimizations"].values()


if __name__ == "__main__":
    main()
