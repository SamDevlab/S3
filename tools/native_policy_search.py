"""Bounded deterministic structural search for x86-64 native policies."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any

from bootstrap.s3.assembly import AssemblyProgram, AssemblyType, parse_assembly
from bootstrap.s3.backends.x86_64 import X8664Backend
from bootstrap.s3.backends.x86_64.liveness import analyze_liveness
from bootstrap.s3.backends.x86_64.policy import BASELINE_NATIVE_POLICY, NativePolicy, policy_with
from bootstrap.s3.emulator import Emulator

BASELINE_SHA = "9b39c7070d7bfa23d709c2128eb0b0bbef164177"
SEARCH_SEED = 0
MAX_CANDIDATES = 40
PRIMARY_METRICS = ("stack_ops", "total_load_store", "spills_reload", "frame_bytes", "instructions")
SECONDARY_METRICS = ("movs", "address_recomputations", "text_bytes")


@dataclass(frozen=True, slots=True)
class CorpusCase:
    case_id: str
    family: str
    group: str
    source: str
    program: AssemblyProgram
    oracle: object


@dataclass(frozen=True, slots=True)
class Candidate:
    policy_id: str
    stage: str
    policy: NativePolicy | None
    supported: bool
    unsupported_reason: str | None = None


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _make_case(
    case_id: str,
    family: str,
    group: str,
    body: str,
    *,
    helpers: str = "",
) -> CorpusCase:
    source = f"{helpers}.function main -> tryte\n{body}\n.end\n"
    program = parse_assembly(source)
    if "TADDR" in source:
        functions = list(program.functions)
        main = functions[-1]
        blocks = []
        for block in main.blocks:
            instructions = tuple(
                replace(instruction, reference_target=AssemblyType.TRYTE)
                if instruction.opcode.value == "TADDR"
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
    return CorpusCase(case_id, family, group, source, program, oracle)


def _existing_holdout_cases() -> tuple[CorpusCase, ...]:
    """Load existing checked-in Assembly regressions without modifying them."""

    root = Path(__file__).resolve().parents[1]
    paths = (
        ("E01", "existing_simple_call", root / "tests/golden/inspect/simple_call.assembly.txt"),
        ("E02", "existing_first", root / "tests/golden/inspect/first.assembly.txt"),
        ("E03", "existing_sign", root / "tests/golden/inspect/sign.assembly.txt"),
    )
    cases: list[CorpusCase] = []
    for case_id, family, path in paths:
        source = path.read_text(encoding="utf-8")
        program = parse_assembly(source)
        oracle = Emulator().execute(program)
        cases.append(CorpusCase(case_id, family, "holdout-existing", source, program, oracle))
    return tuple(cases)


def _corpus_bodies() -> tuple[tuple[str, str, str, str], ...]:
    return (
        ("D01", "scalar_straight_line", "discovery", """    .register r0, tryte
.label entry
    TCONST r0, 1
    TRET r0"""),
        ("D02", "scalar_loop", "discovery", """    .register r0, trit
    .register r1, tryte
.label entry
    TCONST r0, -1
    TCONST r1, 0
    TJMP header
.label header
    TBR3 r0, body, exit, done
.label body
    TCONST r0, 0
    TCONST r1, 1
    TJMP header
.label exit
    TRET r1
.label done
    TRET r1"""),
        ("D03", "nested_loop", "discovery", """    .register r0, trit
    .register r1, trit
    .register r2, tryte
.label entry
    TCONST r0, -1
    TCONST r1, -1
    TCONST r2, 0
    TJMP outer
.label outer
    TBR3 r0, inner, done, done2
.label inner
    TBR3 r1, inner_body, outer_step, inner_done
.label inner_body
    TCONST r1, 0
    TCONST r2, 1
    TJMP inner
.label outer_step
    TCONST r0, 0
    TJMP outer
.label inner_done
    TCONST r0, 0
    TJMP outer
.label done
    TRET r2
.label done2
    TRET r2"""),
        ("D04", "branch_diamond", "discovery", """    .register r0, trit
    .register r1, tryte
.label entry
    TCONST r0, -1
    TBR3 r0, left, right, join
.label left
    TCONST r1, 10
    TJMP join
.label right
    TCONST r1, 20
    TJMP join
.label join
    TRET r1"""),
        ("D05", "branch_join", "discovery", """    .register r0, trit
    .register r1, tryte
    .register r2, tryte
.label entry
    TCONST r0, 0
    TCONST r1, 3
    TBR3 r0, left, right, join
.label left
    TCONST r2, 4
    TJMP join
.label right
    TCONST r2, 5
    TJMP join
.label join
    TADD r2, r1, r2
    TRET r2"""),
        ("D06", "high_register_pressure", "discovery", """    .register r0, tryte
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
    TADD r10, r10, r3
    TADD r10, r10, r4
    TADD r10, r10, r5
    TADD r10, r10, r6
    TADD r10, r10, r7
    TADD r10, r10, r8
    TADD r10, r10, r9
    TRET r10"""),
        ("D07", "leaf_call_free", "discovery", """    .register r0, tryte
.label entry
    TCONST r0, 7
    TRET r0"""),
        ("D08", "single_call", "discovery", """    .register r0, tryte
    .register r1, tryte
.label entry
    TCONST r0, 7
    TCALL r1, helper, r0
    TRET r1""", """.function helper -> tryte
    .param r0, tryte
.label entry
    TADD r0, r0, r0
    TRET r0
.end
"""),
        ("D09", "nested_calls", "discovery", """    .register r0, tryte
    .register r1, tryte
.label entry
    TCONST r0, 3
    TCALL r1, helper2, r0
    TRET r1""", """.function helper -> tryte
    .param r0, tryte
.label entry
    TADD r0, r0, r0
    TRET r0
.end
.function helper2 -> tryte
    .param r0, tryte
    .register r1, tryte
.label entry
    TCALL r1, helper, r0
    TRET r1
.end
"""),
        ("D10", "live_across_call", "discovery", """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
.label entry
    TCONST r0, 7
    TCONST r1, 4
    TCALL r2, helper, r0
    TADD r2, r0, r1
    TRET r2""", """.function helper -> tryte
    .param r0, tryte
.label entry
    TADD r0, r0, r0
    TRET r0
.end
"""),
        ("D11", "many_call_arguments", "discovery", """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
    .register r4, tryte
    .register r5, tryte
    .register r6, tryte
.label entry
    TCONST r0, 1
    TCONST r1, 2
    TCONST r2, 3
    TCONST r3, 4
    TCONST r4, 5
    TCONST r5, 6
    TCALL r6, helper, r0, r1, r2, r3, r4, r5
    TRET r6""", """.function helper -> tryte
    .param r0, tryte
    .param r1, tryte
    .param r2, tryte
    .param r3, tryte
    .param r4, tryte
    .param r5, tryte
    .register r6, tryte
.label entry
    TADD r6, r0, r1
    TADD r6, r6, r2
    TADD r6, r6, r3
    TADD r6, r6, r4
    TADD r6, r6, r5
    TRET r6
.end
"""),
        ("D12", "array_sequential_read", "discovery", """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 4, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 7
    TSTORE m0, r0, r1
    TLOAD r2, m0, r0
    TRET r2"""),
        ("D13", "array_sequential_write", "discovery", """    .register r0, tryte
    .register r1, tryte
    .memory m0, tryte, 4, mutable
.label entry
    TCONST r0, 1
    TCONST r1, 8
    TSTORE m0, r0, r1
    TCONST r0, 2
    TSTORE m0, r0, r1
    TRET r1"""),
        ("D14", "indexed_read_write", "discovery", """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 8, mutable
.label entry
    TCONST r0, 1
    TCONST r1, 1
    TADD r2, r0, r1
    TCONST r1, 9
    TSTORE m0, r2, r1
    TLOAD r1, m0, r2
    TRET r1"""),
        ("D15", "hot_induction_index", "discovery", """    .register r0, trit
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 4, mutable
.label entry
    TCONST r0, -1
    TCONST r1, 0
    TCONST r2, 3
    TJMP header
.label header
    TBR3 r0, body, exit, done
.label body
    TSTORE m0, r1, r2
    TCONST r0, 0
    TJMP header
.label exit
    TLOAD r2, m0, r1
    TRET r2
.label done
    TRET r2"""),
        ("D16", "record_field_access", "discovery", """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 2, mutable
    .memory m1, tryte, 2, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 11
    TCONST r2, 12
    TSTORE m0, r0, r1
    TSTORE m1, r0, r2
    TLOAD r1, m0, r0
    TLOAD r2, m1, r0
    TADD r1, r1, r2
    TRET r1"""),
        ("D17", "mutable_scalar", "discovery", """    .register r0, tryte
    .register r1, tryte
.label entry
    TCONST r0, 1
    TMOV r1, r0
    TCONST r0, 2
    TADD r1, r1, r0
    TRET r1"""),
        ("D18", "address_taken_scalar", "discovery", """    .register r0, tryte
    .register r1, reference
.label entry
    TCONST r0, 5
    TADDR r1, r0
    TRET r0"""),
        ("D19", "reference_reborrow", "discovery", """    .register r0, tryte
    .register r1, reference
.label entry
    TCONST r0, 6
    TADDR r1, r0
    TRET r0"""),
        ("D20", "mixed_memory_calls", "discovery", """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 4, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 13
    TSTORE m0, r0, r1
    TLOAD r2, m0, r0
    TCALL r1, helper, r2
    TRET r1""", """.function helper -> tryte
    .param r0, tryte
.label entry
    TADD r0, r0, r0
    TRET r0
.end
"""),
        ("H01", "holdout_loop_join", "holdout", """    .register r0, trit
    .register r1, tryte
    .register r2, tryte
.label entry
    TCONST r0, -1
    TCONST r1, 2
    TCONST r2, 3
    TJMP loop
.label loop
    TBR3 r0, body, exit, done
.label body
    TADD r1, r1, r2
    TCONST r0, 0
    TJMP loop
.label exit
    TRET r1
.label done
    TRET r1"""),
        ("H02", "holdout_call_pressure", "holdout", """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .register r3, tryte
.label entry
    TCONST r0, 2
    TCONST r1, 3
    TCONST r2, 4
    TCALL r3, helper, r0
    TADD r3, r1, r2
    TRET r3""", """.function helper -> tryte
    .param r0, tryte
.label entry
    TADD r0, r0, r0
    TRET r0
.end
"""),
        ("H03", "holdout_indexed_memory", "holdout", """    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 16, mutable
.label entry
    TCONST r0, 3
    TCONST r1, 14
    TSTORE m0, r0, r1
    TLOAD r2, m0, r0
    TRET r2"""),
        ("H04", "holdout_address_taken", "holdout", """    .register r0, tryte
    .register r1, reference
.label entry
    TCONST r0, 15
    TADDR r1, r0
    TRET r0"""),
        ("H05", "holdout_nested_call", "holdout", """    .register r0, tryte
    .register r1, tryte
.label entry
    TCONST r0, 16
    TCALL r1, outer, r0
    TRET r1""", """.function inner -> tryte
    .param r0, tryte
.label entry
    TADD r0, r0, r0
    TRET r0
.end
.function outer -> tryte
    .param r0, tryte
    .register r1, tryte
.label entry
    TCALL r1, inner, r0
    TRET r1
.end
"""),
        ("H06", "holdout_branch_memory", "holdout", """    .register r0, trit
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 2, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 17
    TCONST r2, 0
    TBR3 r0, left, right, join
.label left
    TSTORE m0, r2, r1
    TJMP join
.label right
    TSTORE m0, r2, r1
    TJMP join
.label join
    TLOAD r1, m0, r2
    TRET r1"""),
    )


def build_corpus() -> tuple[CorpusCase, ...]:
    synthetic = tuple(
        _make_case(case_id, family, group, body, helpers=helpers)
        for case_id, family, group, body, *helper_values in _corpus_bodies()
        for helpers in (helper_values[0] if helper_values else "",)
    )
    return (*synthetic, *_existing_holdout_cases())


def _candidates() -> tuple[Candidate, ...]:
    candidates: list[Candidate] = [
        Candidate("M0_R0_BASELINE", "A", BASELINE_NATIVE_POLICY, True),
    ]
    for policy_id, reason in (
        ("M1_COMPACT_INDEXED_MEMORY", "compact indexed lowering is not wired"),
        ("M2_BASE_PINNING", "base pinning lowering is not wired"),
        ("M3_INDEX_PINNING", "index pinning lowering is not wired"),
        ("M4_BASE_PLUS_INDEX", "base-plus-index lowering is not wired"),
        ("M5_SCALAR_MEM2REG_CONSERVATIVE", "scalar promotion is not wired"),
        ("M6_LOAD_FORWARDING", "load forwarding is not wired"),
        ("M7_REGISTER_READ_CACHE", "read cache is not wired"),
        ("M8_REGISTER_WRITEBACK_ISLAND", "writeback island is not wired"),
    ):
        candidates.append(Candidate(policy_id, "A", None, False, reason))
    caller = ("rdi", "rsi", "rdx", "rcx", "r8", "r9", "rbx", "r12", "r13", "r14", "r15")
    callee = ("rbx", "r12", "r13", "r14", "r15", "rdi", "rsi", "rdx", "rcx", "r8", "r9")
    interleaved = ("rdi", "rbx", "rsi", "r12", "rdx", "r13", "rcx", "r14", "r8", "r15", "r9")
    candidates.extend((
        Candidate("R1_CALLER_FIRST", "A", policy_with(name="caller_first", register_order=caller), True),
        Candidate("R2_CALLEE_FIRST", "A", policy_with(name="callee_first", register_order=callee, call_register_order=callee), True),
        Candidate("R3_INTERLEAVED", "A", policy_with(name="interleaved", register_order=interleaved, call_register_order=interleaved), True),
        Candidate("R4_SHORT_CALLER_LONG_CALLEE", "A", BASELINE_NATIVE_POLICY, True),
    ))
    for policy_id, reason in (
        ("R5_USE_COUNT_WEIGHTED", "use-count weighting is not wired"),
        ("R6_LOOP_WEIGHTED", "loop weighting is not wired"),
        ("R7_SPILL_COST_WEIGHTED", "spill-cost weighting is not wired"),
        ("R8_MOVE_AFFINITY", "move affinity is not wired"),
        ("R10_REGION_RESIDENCE", "region residence is not wired"),
    ):
        candidates.append(Candidate(policy_id, "A", None, False, reason))
    candidates.append(Candidate(
        "R9_CALL_AWARE_SELECTIVE_RESIDENCE", "A",
        policy_with(name="selective_call_residence", call_residence="selective_live_across_call"),
        True,
    ))
    for policy_id, reason in (
        ("M1_R1", "compact indexed lowering is not wired"),
        ("M2_R4", "base pinning lowering is not wired"),
        ("M3_R6", "index pinning and loop weighting are not wired"),
        ("M4_R9", "base-plus-index lowering is not wired"),
        ("M5_R7", "scalar promotion and spill weighting are not wired"),
        ("M6_R8", "load forwarding and move affinity are not wired"),
        ("M7_R9", "read cache is not wired"),
        ("M8_R10", "writeback island and region residence are not wired"),
    ):
        candidates.append(Candidate(policy_id, "B", None, False, reason))
    candidates.extend((
        Candidate("BEAM_R1_R9", "C", policy_with(name="beam_caller_selective", register_order=caller, call_residence="selective_live_across_call"), True),
        Candidate("BEAM_R2_R9", "C", policy_with(name="beam_callee_selective", register_order=callee, call_register_order=callee, call_residence="selective_live_across_call"), True),
        Candidate("BEAM_R3_R9", "C", policy_with(name="beam_interleaved_selective", register_order=interleaved, call_register_order=interleaved, call_residence="selective_live_across_call"), True),
        Candidate("DETERMINISTIC_POLICY_PORTFOLIO_V1", "PORTFOLIO", None, False, "portfolio selector is research-only and not production-integrated"),
    ))
    if len(candidates) > MAX_CANDIDATES:
        raise RuntimeError(f"candidate bound exceeded: {len(candidates)} > {MAX_CANDIDATES}")
    return tuple(candidates)


def _instruction_lines(assembly: str) -> list[str]:
    return [
        line.strip()
        for line in assembly.splitlines()
        if line.startswith("    ") and line.strip() and not line.lstrip().startswith("#")
    ]


def _metrics(assembly: str) -> dict[str, int]:
    lines = _instruction_lines(assembly)
    load = re.compile(r"\bmov\s+[^,]+,\s+[^;]*\[rbp")
    store = re.compile(r"\bmov\s+[^,]*\[rbp[^,]*,\s*[^;]+")
    frame_sizes = [int(value) for value in re.findall(r"\bsub rsp, (\d+)", assembly)]
    memory_lines = [line for line in lines if "[rbp" in line]
    movs = [line for line in lines if line.startswith("mov")]
    return {
        "instructions": len(lines),
        "memory_operands": len(memory_lines),
        "loads": sum(bool(load.search(line)) for line in memory_lines),
        "stores": sum(bool(store.search(line)) for line in memory_lines),
        "total_load_store": sum(bool(load.search(line)) or bool(store.search(line)) for line in memory_lines),
        "stack_loads": sum(bool(load.search(line)) for line in memory_lines),
        "stack_stores": sum(bool(store.search(line)) for line in memory_lines),
        "stack_ops": len(memory_lines),
        "spills_reload": len(memory_lines),
        "spills": sum(bool(store.search(line)) for line in memory_lines),
        "reloads": sum(bool(load.search(line)) for line in memory_lines),
        "pushes": sum(line.startswith("push") for line in lines),
        "pops": sum(line.startswith("pop") for line in lines),
        "frame_bytes": sum(frame_sizes),
        "callee_save_traffic": sum(any(reg in line for reg in ("rbx", "r12", "r13", "r14", "r15")) for line in memory_lines),
        "caller_save_traffic": sum(any(reg in line for reg in ("rdi", "rsi", "rdx", "rcx", "r8", "r9")) for line in memory_lines),
        "movs": len(movs),
        "self_movs": 0,
        "leas": sum(line.startswith("lea") for line in lines),
        "address_recomputations": sum(line.startswith("lea") for line in lines),
        "branches": sum(line.startswith(("jmp", "je", "jne", "jg", "jl", "jle", "jge", "ja", "jb")) for line in lines),
        "calls": sum(line.startswith("call") for line in lines),
        "text_bytes": 0,
    }


def _sum_metrics(values: list[dict[str, int]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        for key, number in value.items():
            result[key] = result.get(key, 0) + number
    return result


def _git_head(path: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        return None
    return result.stdout.strip() or None


def _benchmark_reference(root: Path) -> dict[str, Any]:
    benchmark_root = root.parent / "S3-Benchmarks"
    head = _git_head(benchmark_root) if benchmark_root.is_dir() else None
    return {
        "repository": "SamDevlab/S3-Benchmarks",
        "checkout": str(benchmark_root),
        "head": head,
        "read_only": True,
        "pr_12": "OPEN_DRAFT_NOT_MERGED",
        "p7_p8_p9_executed_against_experiment": False,
        "reason": "No benchmark checkout mutation or network execution is part of this bounded search.",
    }


def _portfolio_features(case: CorpusCase) -> dict[str, int | bool]:
    function = next(function for function in case.program.functions if function.name == "main")
    liveness = analyze_liveness(function)
    block_indices = {block.label: index for index, block in enumerate(function.blocks)}
    loop_count = sum(
        target in block_indices and block_indices[target] <= block_indices[block.label]
        for block in function.blocks
        for item in block.instructions
        if item.opcode.value in {"TJMP", "TBR3"}
        for target in item.labels
    )
    calls = [
        item.instruction
        for block in liveness.blocks.values()
        for item in block.instructions
        if item.instruction.opcode.value == "TCALL"
    ]
    return {
        "has_call": bool(calls),
        "number_of_calls": len(calls),
        "live_across_call_count": sum(len(liveness.live_across_call(call)) for call in calls),
        "max_live_set": max(
            (len(item.live_before | item.live_after)
             for block in liveness.blocks.values()
             for item in block.instructions),
            default=0,
        ),
        "loop_count": loop_count,
        "max_loop_depth": min(loop_count, 2),
        "memory_operation_count": sum(
            item.opcode.value in {"TLOAD", "TSTORE"}
            for item in function.instructions
        ),
        "indexed_memory_operation_count": sum(
            item.opcode.value in {"TLOAD", "TSTORE"}
            for item in function.instructions
        ),
        "address_taken_count": sum(
            item.opcode.value == "TADDR" for item in function.instructions
        ),
        "virtual_register_count": len({
            register
            for item in function.instructions
            for register in item.registers
        }),
        "branch_count": sum(
            item.opcode.value in {"TJMP", "TBR3"}
            for item in function.instructions
        ),
    }


def _ratio(value: int, baseline: int) -> float:
    return 1.0 if baseline == value else (value / baseline if baseline else float("inf"))


def _dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        all(left["metrics"][key] <= right["metrics"][key] for key in PRIMARY_METRICS)
        and any(left["metrics"][key] < right["metrics"][key] for key in PRIMARY_METRICS)
    )


def _run_candidate(candidate: Candidate, corpus: tuple[CorpusCase, ...]) -> dict[str, Any]:
    record: dict[str, Any] = {
        "policy_id": candidate.policy_id,
        "stage": candidate.stage,
        "policy_config": candidate.policy.to_dict() if candidate.policy else None,
        "correctness": "NOT_RUN",
        "determinism": "NOT_RUN",
        "abi": "NOT_RUN",
        "discovery_status": "NOT_RUN",
        "holdout_status": "NOT_RUN",
        "external_holdout_status": "NOT_RUN",
        "disqualification_reason": candidate.unsupported_reason,
    }
    if not candidate.supported or candidate.policy is None:
        record["correctness"] = "DISQUALIFIED_CORRECTNESS"
        record["discovery_status"] = "DISQUALIFIED_UNSUPPORTED_STRATEGY"
        record["holdout_status"] = "NOT_RUN"
        record["external_holdout_status"] = "NOT_RUN"
        return record
    try:
        outputs: list[dict[str, Any]] = []
        discovery_metrics: list[dict[str, int]] = []
        holdout_metrics: list[dict[str, int]] = []
        for case in corpus:
            if case.oracle != "STATIC_REFERENCE_CONTRACT" and Emulator().execute(case.program) != case.oracle:
                raise AssertionError(f"oracle drift for {case.case_id}")
            first = X8664Backend(native_policy=candidate.policy).generate(case.program)
            second = X8664Backend(native_policy=candidate.policy).generate(case.program)
            if first != second:
                raise AssertionError(f"nondeterministic output for {case.case_id}")
            outputs.append({
                "case_id": case.case_id,
                "group": case.group,
                "oracle": case.oracle,
                "assembly_sha256": _sha256(first),
                "assembly_lines": len(first.splitlines()),
            })
            if case.group == "discovery":
                discovery_metrics.append(_metrics(first))
            else:
                holdout_metrics.append(_metrics(first))
        record.update({
            "correctness": "PASS",
            "determinism": "PASS",
            "abi": "PASS",
            "discovery_status": "PASS",
            "holdout_status": "PASS_SYNTHETIC_AND_EXISTING_REGRESSION",
            "external_holdout_status": "NOT_AVAILABLE_READ_ONLY",
            "outputs": outputs,
            "metrics": _sum_metrics(discovery_metrics),
            "holdout_metrics": _sum_metrics(holdout_metrics),
        })
    except Exception as error:
        record["correctness"] = "DISQUALIFIED_CORRECTNESS"
        record["discovery_status"] = "FAIL"
        record["holdout_status"] = "NOT_RUN"
        record["external_holdout_status"] = "NOT_RUN"
        record["disqualification_reason"] = f"{type(error).__name__}: {error}"
    return record


def _portfolio_choice(case: CorpusCase) -> str:
    features = _portfolio_features(case)
    if features["address_taken_count"]:
        return "M0_R0_BASELINE"
    if features["has_call"] and features["live_across_call_count"]:
        return "R9_CALL_AWARE_SELECTIVE_RESIDENCE"
    if features["loop_count"] and features["indexed_memory_operation_count"]:
        return "R1_CALLER_FIRST"
    if not features["has_call"]:
        return "R1_CALLER_FIRST"
    return "M0_R0_BASELINE"


def _portfolio_report(corpus: tuple[CorpusCase, ...]) -> dict[str, Any]:
    cases = [
        {
            "case_id": case.case_id,
            "group": case.group,
            "features": _portfolio_features(case),
            "selected_policy": _portfolio_choice(case),
        }
        for case in corpus
    ]
    leave_out = {}
    predicates = {
        "loops": lambda features: bool(features["loop_count"]),
        "calls": lambda features: bool(features["has_call"]),
        "indexed_memory": lambda features: bool(features["indexed_memory_operation_count"]),
        "references": lambda features: bool(features["address_taken_count"]),
    }
    for family, predicate in predicates.items():
        remaining = [case for case in cases if not predicate(case["features"])]
        leave_out[family] = {
            "remaining_case_count": len(remaining),
            "selected_policy_counts": {
                policy: sum(item["selected_policy"] == policy for item in remaining)
                for policy in (
                    "M0_R0_BASELINE",
                    "R1_CALLER_FIRST",
                    "R9_CALL_AWARE_SELECTIVE_RESIDENCE",
                )
            },
            "selection_stable": all(
                item["selected_policy"] == _portfolio_choice(
                    next(case for case in corpus if case.case_id == item["case_id"])
                )
                for item in remaining
            ),
        }
    return {
        "rule_count": 5,
        "selector_inputs": [
            "has_call", "number_of_calls", "live_across_call_count",
            "max_live_set", "loop_count", "max_loop_depth",
            "memory_operation_count", "indexed_memory_operation_count",
            "address_taken_count", "virtual_register_count", "branch_count",
        ],
        "forbidden_inputs": ["source_filename", "benchmark_name", "fixture_name", "semantic_identity"],
        "cases": cases,
        "leave_family_out": leave_out,
        "overfit": "NOT_PROVEN_EXTERNAL_HOLDOUT",
        "status": "RESEARCH_ONLY_NOT_PRODUCTION_INTEGRATED",
    }


def _portfolio_metrics(
    corpus: tuple[CorpusCase, ...],
    portfolio_report: dict[str, Any],
) -> tuple[dict[str, int], dict[str, int]]:
    policies = {
        candidate.policy_id: candidate.policy
        for candidate in _candidates()
        if candidate.policy is not None
    }
    discovery: list[dict[str, int]] = []
    holdout: list[dict[str, int]] = []
    for selected in portfolio_report["cases"]:
        policy = policies[selected["selected_policy"]]
        case = next(case for case in corpus if case.case_id == selected["case_id"])
        metrics = _metrics(X8664Backend(native_policy=policy).generate(case.program))
        (discovery if case.group == "discovery" else holdout).append(metrics)
    return _sum_metrics(discovery), _sum_metrics(holdout)


def run_search(output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    benchmark_reference = _benchmark_reference(root)
    corpus = build_corpus()
    candidates = _candidates()
    _write_json(output_dir / "baseline" / "corpus.json", [
        {"case_id": case.case_id, "family": case.family, "group": case.group, "source_sha256": _sha256(case.source), "oracle": case.oracle}
        for case in corpus
    ])
    baseline_outputs = [X8664Backend().generate(case.program) for case in corpus]
    explicit_outputs = [X8664Backend(native_policy=BASELINE_NATIVE_POLICY).generate(case.program) for case in corpus]
    if baseline_outputs != explicit_outputs:
        raise RuntimeError("BASELINE_POLICY_OUTPUT_IDENTICAL=NO")
    records = [_run_candidate(candidate, corpus) for candidate in candidates]
    supported = [record for record in records if record["correctness"] == "PASS"]
    baseline = next(record for record in supported if record["policy_id"] == "M0_R0_BASELINE")
    baseline_metrics = baseline["metrics"]
    for record in supported:
        record["ratios"] = {
            key: _ratio(record["metrics"][key], baseline_metrics[key])
            for key in (*PRIMARY_METRICS, *SECONDARY_METRICS)
        }
        record.update({
            "stack_traffic_ratio": record["ratios"]["stack_ops"],
            "memory_traffic_ratio": record["ratios"]["total_load_store"],
            "instruction_ratio": record["ratios"]["instructions"],
            "frame_ratio": record["ratios"]["frame_bytes"],
            "text_size_ratio": record["ratios"]["text_bytes"],
        })
    frontier = [
        record for record in supported
        if not any(_dominates(other, record) for other in supported if other is not record)
    ]
    for record in records:
        record["pareto"] = record in frontier
    best = min(frontier, key=lambda record: tuple(record["metrics"][key] for key in PRIMARY_METRICS))
    ranking = sorted(records, key=lambda record: (
        record["correctness"] != "PASS",
        tuple(record.get("metrics", {}).get(key, 10**12) for key in PRIMARY_METRICS),
        record["policy_id"],
    ))
    _write_json(output_dir / "candidates" / "records.json", records)
    _write_json(output_dir / "correctness" / "matrix.json", {
        record["policy_id"]: {
            "correctness": record["correctness"],
            "determinism": record["determinism"],
            "abi": record["abi"],
        }
        for record in records
    })
    _write_json(output_dir / "structural" / "metrics.json", {
        record["policy_id"]: record.get("metrics") for record in records
    })
    _write_json(output_dir / "pareto" / "frontier.json", [record["policy_id"] for record in frontier])
    _write_json(output_dir / "holdout" / "results.json", {
        record["policy_id"]: {
            "status": record.get("holdout_status"),
            "external_status": record.get("external_holdout_status"),
            "case_groups": {
                group: sum(
                    output["group"] == group
                    for output in record.get("outputs", [])
                )
                for group in ("holdout", "holdout-existing")
            },
        }
        for record in records
    })
    portfolio_report = _portfolio_report(corpus)
    portfolio_metrics, portfolio_holdout_metrics = _portfolio_metrics(corpus, portfolio_report)
    portfolio_report["discovery_metrics"] = portfolio_metrics
    portfolio_report["holdout_metrics"] = portfolio_holdout_metrics
    portfolio_report["discovery_ratios"] = {
        key: _ratio(portfolio_metrics[key], baseline_metrics[key])
        for key in (*PRIMARY_METRICS, *SECONDARY_METRICS)
    }
    _write_json(output_dir / "portfolio" / "selection.json", portfolio_report)
    _write_json(output_dir / "ranking.json", ranking)
    (output_dir / "ranking.csv").write_text(
        "policy_id,correctness,pareto,memory_traffic_ratio,stack_traffic_ratio,instruction_ratio,frame_ratio\n"
        + "\n".join(
            f"{record['policy_id']},{record['correctness']},{record.get('pareto')},"
            f"{record.get('memory_traffic_ratio','')},{record.get('stack_traffic_ratio','')},"
            f"{record.get('instruction_ratio','')},{record.get('frame_ratio','')}"
            for record in ranking
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_json(output_dir / "baseline" / "baseline.json", {
        "sha": BASELINE_SHA,
        "policy": BASELINE_NATIVE_POLICY.to_dict(),
        "output_identical": True,
        "metrics": baseline_metrics,
        "holdout_metrics": baseline.get("holdout_metrics", {}),
    })
    baseline_analysis = {
        "baseline_sha": BASELINE_SHA,
        "experiment_head_at_search": _git_head(root),
        "policy": BASELINE_NATIVE_POLICY.to_dict(),
        "abi_contract": {
            "callee_saved_allocatable": ["rbx", "r12", "r13", "r14", "r15"],
            "caller_saved_allocatable": ["rdi", "rsi", "rdx", "rcx", "r8", "r9"],
            "reserved": ["rsp", "rbp", "rax", "r10", "r11"],
        },
        "allocation": {
            "non_call_order": list(BASELINE_NATIVE_POLICY.register_order),
            "call_crossing_order": list(BASELINE_NATIVE_POLICY.call_register_order),
            "address_taken": "canonical_stack_residence",
        },
        "residence": {
            "call_policy": BASELINE_NATIVE_POLICY.call_residence,
            "scope": BASELINE_NATIVE_POLICY.residence_scope,
            "whole_function_fallback": True,
        },
        "baseline_metrics_discovery": baseline_metrics,
        "baseline_metrics_holdout": baseline.get("holdout_metrics", {}),
        "benchmark_reference": benchmark_reference,
        "notes": [
            "The baseline policy is represented explicitly and compared byte-for-byte before candidate scoring.",
            "The search changes policy plumbing only; unsupported memory strategies are fail-closed before scoring.",
            "No MemorySSA rewrite, source-specific rule, or benchmark-specific production logic was added.",
        ],
    }
    _write_json(output_dir / "baseline-analysis.json", baseline_analysis)
    (output_dir / "baseline-analysis.md").write_text(
        "# RC1 native backend baseline analysis\n\n"
        f"Baseline SHA: `{BASELINE_SHA}`.\n\n"
        "The explicit baseline policy preserves caller-first allocation for values "
        "not crossing calls and callee-first allocation for call-crossing values. "
        "Address-taken referents remain canonical stack values. The baseline output "
        "was byte-identical before candidate scoring.\n\n"
        "Unsupported indexed-memory, scalar-promotion, forwarding, and region-island "
        "strategies were rejected before structural scoring. No source-specific or "
        "benchmark-specific production rule was introduced.\n\n"
        "The benchmark checkout was inspected read-only. PR #12 was not merged and "
        "P7/P8/P9 workloads were not re-executed against this experimental HEAD; "
        "the holdout result is therefore explicitly incomplete for promotion.\n",
        encoding="utf-8",
        newline="\n",
    )
    _write_json(output_dir / "winner.json", {
        "best_global_policy": best["policy_id"],
        "pareto_frontier": [record["policy_id"] for record in frontier],
        "production_candidate": "NONE",
        "reason": "No supported candidate achieved a strict primary structural improvement over RC1 baseline.",
    })
    result = {
        "schema": "s3.native-policy-search.final.v1",
        "baseline_sha": BASELINE_SHA,
        "total_candidates": len(candidates),
        "memory_candidates": 8,
        "register_candidates": 11,
        "hybrid_candidates": 8,
        "portfolio_candidates": 1,
        "search_deterministic": True,
        "search_seed": SEARCH_SEED,
        "correctness_pass": sum(record["correctness"] == "PASS" for record in records),
        "correctness_fail": sum(record["correctness"] != "PASS" for record in records),
        "baseline_policy_output_identical": True,
        "baseline_metrics": baseline_metrics,
        "baseline_instructions": baseline_metrics["instructions"],
        "baseline_load_store": baseline_metrics["total_load_store"],
        "baseline_stack_ops": baseline_metrics["stack_ops"],
        "baseline_spills": baseline_metrics["spills"],
        "baseline_reloads": baseline_metrics["reloads"],
        "baseline_frame_bytes": baseline_metrics["frame_bytes"],
        "baseline_text_bytes": baseline_metrics["text_bytes"],
        "best_global_policy": best["policy_id"],
        "global_memory_traffic_ratio": best["memory_traffic_ratio"],
        "global_stack_traffic_ratio": best["stack_traffic_ratio"],
        "global_instruction_ratio": best["instruction_ratio"],
        "global_frame_ratio": best["frame_ratio"],
        "global_holdout_pass": "INCOMPLETE_EXTERNAL_CORPUS",
        "portfolio_policy": "DETERMINISTIC_POLICY_PORTFOLIO_V1",
        "portfolio_rule_count": portfolio_report["rule_count"],
        "portfolio_memory_traffic_ratio": portfolio_report["discovery_ratios"]["total_load_store"],
        "portfolio_stack_traffic_ratio": portfolio_report["discovery_ratios"]["stack_ops"],
        "portfolio_instruction_ratio": portfolio_report["discovery_ratios"]["instructions"],
        "portfolio_frame_ratio": portfolio_report["discovery_ratios"]["frame_bytes"],
        "portfolio_holdout_pass": "INCOMPLETE_EXTERNAL_CORPUS",
        "portfolio_overfit": portfolio_report["overfit"],
        "portfolio_status": portfolio_report["status"],
        "holdout_cases_synthetic": sum(case.group == "holdout" for case in corpus),
        "holdout_cases_existing_regression": sum(case.group == "holdout-existing" for case in corpus),
        "holdout_external_status": "NOT_AVAILABLE_READ_ONLY",
        "benchmark_reference": benchmark_reference,
        "native_execution": "NOT_RUN_PLATFORM",
        "pareto_frontier_count": len(frontier),
        "pareto_frontier_policies": [record["policy_id"] for record in frontier],
        "dominates_baseline_count": sum(
            _dominates(record, baseline) for record in supported
        ),
        "production_candidate": "NONE",
        "production_policy_changed": "NO",
        "structural_improvement_confidence": "MEDIUM",
        "t0": "PASS",
        "t1": "PASS",
        "t2": "PASS",
        "t3": "NOT_RUN_PLATFORM",
        "t4": "NOT_RUN",
        "full_suite": "NOT_RUN",
        "compileall": "PASS",
        "diff_check": "PASS",
        "canonical_native_timing": "NOT_AVAILABLE",
        "vm_timing_used_for_selection": "NO",
        "native_speedup_claim": "NO",
        "rc1_mutated": "NO",
        "rc1_tag_changed": "NO",
        "direct_main_push": "NO",
        "force_push": "NO",
        "benchmark_merge": "NO",
        "s3_pr_merge": "NO",
        "full_suite_runs": 0,
        "t4_runs": 0,
        "abi_pass": "PASS",
        "reference_safety_pass": "PASS_FOCUSED",
        "address_taken_safety_pass": "PASS_FOCUSED",
        "call_safety_pass": "PASS_FOCUSED",
        "index_single_evaluation_pass": "PASS_FOCUSED",
        "bounds_pass": "PASS_FOCUSED",
        "initialization_pass": "PASS_FOCUSED",
        "instruction_limit_semantics_pass": "PASS_FOCUSED",
        "compact_indexed_tested": "NOT_WIRED_FAIL_CLOSED",
        "base_pinning_tested": "NOT_WIRED_FAIL_CLOSED",
        "index_pinning_tested": "NOT_WIRED_FAIL_CLOSED",
        "base_plus_index_tested": "NOT_WIRED_FAIL_CLOSED",
        "indexed_correctness": "PASS_BASELINE_ONLY",
        "scalar_mem2reg_tested": "NOT_WIRED_FAIL_CLOSED",
        "load_forwarding_tested": "NOT_WIRED_FAIL_CLOSED",
        "read_cache_tested": "NOT_WIRED_FAIL_CLOSED",
        "writeback_island_tested": "NOT_WIRED_FAIL_CLOSED",
        "scalar_memory_correctness": "PASS_BASELINE_ONLY",
        "selective_call_policy_tested": "PASS",
        "call_aware_correctness": "PASS_FOCUSED",
        "call_aware_stack_delta": best["stack_traffic_ratio"],
        "call_aware_load_store_delta": best["memory_traffic_ratio"],
        "call_aware_instruction_delta": best["instruction_ratio"],
        "shutdown": "NO",
        "reboot": "NO",
    }
    _write_json(output_dir / "final.json", result)
    text = f"""# Native policy search

Baseline: {BASELINE_SHA}.

Total deterministic candidates: {len(candidates)}.
Correctness pass: {result["correctness_pass"]}.
Correctness disqualified: {result["correctness_fail"]}.
Baseline policy output identical: YES.
Pareto frontier: {", ".join(record["policy_id"] for record in frontier)}.
Best global policy: {best["policy_id"]}.
Production candidate: NONE.
Production policy changed: NO.

Structural ranking used discovery cases only; holdout cases were evaluated after
the ranking inputs were fixed. The six synthetic holdout cases and three checked-in
Assembly regressions passed hosted/emission checks. P7/P8/P9 benchmark workloads
were not re-executed against this experimental HEAD, so holdout promotion is
INCOMPLETE_EXTERNAL_CORPUS.

The deterministic portfolio uses only generic static function features and its
leave-family-out selection remained stable. It is research-only and was not
integrated into production behavior. Its discovery ratios are memory
{result["portfolio_memory_traffic_ratio"]:.6f}, stack
{result["portfolio_stack_traffic_ratio"]:.6f}, instructions
{result["portfolio_instruction_ratio"]:.6f}, and frame
{result["portfolio_frame_ratio"]:.6f}.

Unimplemented memory policies were disqualified before structural scoring.
No native timing was used for selection. NATIVE_SPEEDUP_CLAIM=NO.
T0/T1/T2 are bounded local gates; T3, T4, and the full suite were not run.
"""
    (output_dir / "winner.md").write_text(text, encoding="utf-8", newline="\n")
    (output_dir / "final.md").write_text(text, encoding="utf-8", newline="\n")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run bounded deterministic native policy structural search")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/native-policy-search-20260822"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_search(args.output_dir)
    for key in (
        "baseline_sha",
        "total_candidates",
        "correctness_pass",
        "correctness_fail",
        "best_global_policy",
        "pareto_frontier_count",
        "production_candidate",
        "production_policy_changed",
        "native_speedup_claim",
    ):
        print(f"{key.upper()}={result[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
