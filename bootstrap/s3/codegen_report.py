"""Experimental structural attribution for generated x86-64 assembly.

The report correlates generated native-assembly regions with S3 Assembly
functions and blocks. It does not claim byte-level machine-code lineage or
binary .text size; those remain unavailable without an assembled-object map.
"""

from __future__ import annotations

import re
from hashlib import sha256
from collections import Counter
from typing import Any

from .assembly import AssemblyFunction, AssemblyOpcode, AssemblyProgram
from .backends.x86_64.allocation import analyze_allocation
from .backends.x86_64.emitter import function_symbol, mangle_block
from .backends.x86_64.liveness import analyze_liveness
from .backends.x86_64.layout import layout_frame


_INSTRUCTION = re.compile(r"^([A-Za-z][A-Za-z0-9.]*)\s*(.*)$")

_ASSEMBLY_CATEGORIES = {
    AssemblyOpcode.TCONST: "CONSTANT",
    AssemblyOpcode.TCONST_STR: "CONSTANT",
    AssemblyOpcode.TMOV: "MOVE",
    AssemblyOpcode.TINV: "USER_COMPUTE",
    AssemblyOpcode.TADD: "USER_COMPUTE",
    AssemblyOpcode.TNDIFF: "USER_COMPUTE",
    AssemblyOpcode.TMUL: "USER_COMPUTE",
    AssemblyOpcode.TDIV: "USER_COMPUTE",
    AssemblyOpcode.TREL: "USER_COMPUTE",
    AssemblyOpcode.TCVT: "CONVERSION",
    AssemblyOpcode.TMIN: "USER_COMPUTE",
    AssemblyOpcode.TMAX: "USER_COMPUTE",
    AssemblyOpcode.TCMP: "USER_COMPUTE",
    AssemblyOpcode.TCALL: "CALL",
    AssemblyOpcode.TLOAD: "MEMORY_ACCESS",
    AssemblyOpcode.TSTORE: "MEMORY_ACCESS",
    AssemblyOpcode.TADDR: "ADDRESSING",
    AssemblyOpcode.TAGGADDR: "ADDRESSING",
    AssemblyOpcode.TAGGLOAD: "REFERENCE",
    AssemblyOpcode.TAGGFIELDADDR: "ADDRESSING",
    AssemblyOpcode.TREFLOAD: "REFERENCE",
    AssemblyOpcode.TREFSTORE: "REFERENCE",
    AssemblyOpcode.TSLEN: "REFERENCE",
    AssemblyOpcode.TSLOAD: "MEMORY_ACCESS",
    AssemblyOpcode.TSSTORE: "MEMORY_ACCESS",
    AssemblyOpcode.TRET: "CONTROL_FLOW",
    AssemblyOpcode.TJMP: "CONTROL_FLOW",
    AssemblyOpcode.TBR3: "CONTROL_FLOW",
}


def _counters() -> Counter[str]:
    return Counter(
        machine_instruction_count=0,
        memory_operand_instructions=0,
        stack_traffic_instructions=0,
        branches=0,
        calls=0,
        moves=0,
        budget_instructions=0,
    )


def _classify_native_instruction(mnemonic: str, operands: str) -> str:
    if mnemonic.startswith("j") or mnemonic in {"ret", "retq"}:
        return "CONTROL_FLOW"
    if mnemonic in {"call", "callq"}:
        return "CALL"
    if mnemonic in {"push", "pushq", "pop", "popq", "leave", "enter"}:
        return "STACK"
    if mnemonic == "lea" or mnemonic == "leaq":
        return "ADDRESSING"
    if mnemonic.startswith(("mov", "xchg")):
        return "MOVE"
    if "[rbp" in operands or "[rsp" in operands:
        return "STACK"
    return "UNKNOWN"


def _record_instruction(counts: Counter[str], mnemonic: str, operands: str) -> str:
    counts["machine_instruction_count"] += 1
    if "[" in operands:
        counts["memory_operand_instructions"] += 1
    if (
        "[rbp" in operands
        or "[rsp" in operands
        or mnemonic in {"push", "pushq", "pop", "popq", "leave", "enter"}
    ):
        counts["stack_traffic_instructions"] += 1
    if mnemonic.startswith("j") or mnemonic in {"ret", "retq"}:
        counts["branches"] += 1
    if mnemonic in {"call", "callq"}:
        counts["calls"] += 1
    if mnemonic.startswith(("mov", "xchg")):
        counts["moves"] += 1
    if "__s3_instruction_count" in operands or "__s3_budget" in operands:
        counts["budget_instructions"] += 1
    return _classify_native_instruction(mnemonic, operands)


def _frame_layout(function: AssemblyFunction, *, max_instructions: int) -> tuple[int, dict[str, object]]:
    budget_register_enabled = max_instructions <= (1 << 63) - 1
    reserved = frozenset({"r15"}) if budget_register_enabled else frozenset()
    allocation = analyze_allocation(function, reserved_registers=reserved)
    allocator_capacity_probe = None
    if budget_register_enabled:
        counterfactual = analyze_allocation(function)
        allocator_capacity_probe = {
            "comparison": "r15_reserved_for_per_instruction_budget_vs_allocator_may_use_r15",
            "counterfactual_is_executable": False,
            "reserved_stack_resident_virtual_register_count": len(allocation.stack_resident_registers),
            "counterfactual_stack_resident_virtual_register_count": len(counterfactual.stack_resident_registers),
            "stack_resident_delta_counterfactual_minus_reserved": (
                len(counterfactual.stack_resident_registers) - len(allocation.stack_resident_registers)
            ),
            "counterfactual_virtual_registers_assigned_r15": [
                register for register, physical in sorted(counterfactual.allocations.items())
                if physical == "r15"
            ],
            "interpretation": "allocator-capacity sensitivity only; no emitted-code or runtime comparison",
        }
    physical = allocation.used_physical_registers
    if budget_register_enabled:
        physical = (*physical, "r15")
    layout = layout_frame(function, physical)
    liveness = analyze_liveness(function)
    live_across_calls = [
        len(liveness.live_across_call(instruction))
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode is AssemblyOpcode.TCALL
    ]
    live_point_sizes = [
        len(live)
        for block in liveness.blocks.values()
        for instruction in block.instructions
        for live in (instruction.live_before, instruction.live_after)
    ]
    move_count = sum(
        instruction.opcode is AssemblyOpcode.TMOV
        for instruction in function.instructions
    )
    same_physical_location_moves = sum(
        instruction.opcode is AssemblyOpcode.TMOV
        and len(instruction.registers) == 2
        and allocation.physical_register(instruction.registers[0]) is not None
        and allocation.physical_register(instruction.registers[0])
        == allocation.physical_register(instruction.registers[1])
        for instruction in function.instructions
    )
    return layout.frame_size, {
        "virtual_register_count": len(allocation.allocations),
        "physical_register_count": sum(
            color is not None for color in allocation.allocations.values()
        ),
        "stack_resident_virtual_register_count": len(allocation.stack_resident_registers),
        "stack_resident_virtual_registers": list(allocation.stack_resident_registers),
        "address_taken_virtual_register_count": len(allocation.address_taken),
        "used_physical_registers": list(physical),
        "peak_live_virtual_registers": max(live_point_sizes, default=0),
        "call_count": len(live_across_calls),
        "peak_values_live_across_call": max(live_across_calls, default=0),
        "assembly_move_count": move_count,
        "moves_assigned_same_physical_register": same_physical_location_moves,
        "dynamic_spills": None,
        "dynamic_spills_status": "NOT_MEASURED_STATIC_STACK_RESIDENCE_IS_NOT_A_SPILL_COUNTER",
        "budget_register_allocator_capacity_probe": allocator_capacity_probe,
    }


def _assembly_program_text(program: AssemblyProgram) -> str:
    """Render the complete dataclass model without the narrower text adapter."""

    lines = [f".assembly-version {program.version}"]
    for function in program.functions:
        lines.extend((function.render(), ""))
    if program.static_strings:
        lines.append(".static-strings")
        lines.extend(item.render() for item in program.static_strings)
    return "\n".join(lines) + "\n"


def build_codegen_report(
    program: AssemblyProgram,
    native_assembly: str,
    *,
    native_origins: tuple[dict[str, object], ...] = (),
    source_sha256: str,
    optimization: str,
    max_frames: int,
    max_instructions: int,
) -> dict[str, Any]:
    """Build deterministic Assembly/function/block and emitted-text statistics."""

    if not isinstance(program, AssemblyProgram) or not program.functions:
        raise ValueError("codegen report requires a non-empty AssemblyProgram")
    if not isinstance(native_assembly, str):
        raise TypeError("native_assembly must be text")

    functions = {function.name: function for function in program.functions}
    symbols = {function_symbol(function): function.name for function in program.functions if not function.external}
    block_sites = {
        mangle_block(function.name, block.label): (function.name, block.label)
        for function in program.functions
        if not function.external
        for block in function.blocks
    }
    function_counts = {name: _counters() for name in functions}
    function_categories: dict[str, Counter[str]] = {name: Counter() for name in functions}
    block_counts = {
        (function.name, block.label): _counters()
        for function in program.functions
        for block in function.blocks
    }
    block_categories: dict[tuple[str, str], Counter[str]] = {
        key: Counter() for key in block_counts
    }
    origin_categories: Counter[str] = Counter()
    unattributed_counts = _counters()
    unattributed_categories: Counter[str] = Counter()
    current_function: str | None = None
    current_block: tuple[str, str] | None = None
    block_line_numbers: dict[tuple[str, str], list[int]] = {
        key: [] for key in block_counts
    }
    block_origin_spans: dict[tuple[str, str], list[dict[str, object]]] = {
        key: [] for key in block_counts
    }
    function_origin_categories: dict[str, Counter[str]] = {
        name: Counter() for name in functions
    }
    block_origin_categories: dict[tuple[str, str], Counter[str]] = {
        key: Counter() for key in block_counts
    }
    origins_by_line: dict[int, tuple[str, str, str]] = {}
    validated_origin_spans: list[dict[str, object]] = []
    native_lines = native_assembly.splitlines()

    for raw_origin in native_origins:
        origin = dict(raw_origin)
        function_name = origin.get("function")
        block_name = origin.get("block")
        instruction_indexes = origin.get("assembly_instruction_indexes")
        line_range = origin.get("native_assembly_line_range")
        if (
            not isinstance(function_name, str)
            or not isinstance(block_name, str)
            or (function_name, block_name) not in block_counts
            or not isinstance(instruction_indexes, list)
            or not instruction_indexes
        ):
            raise ValueError("native origin has an invalid function, block, or instruction list")
        function = functions[function_name]
        block = next(item for item in function.blocks if item.label == block_name)
        opcodes = origin.get("assembly_opcodes")
        if (
            not isinstance(opcodes, list)
            or len(opcodes) != len(instruction_indexes)
            or any(not isinstance(opcode, str) for opcode in opcodes)
        ):
            raise ValueError("native origin has invalid Assembly opcodes")
        if any(
            isinstance(index, bool)
            or not isinstance(index, int)
            or index < 0
            or index >= len(block.instructions)
            for index in instruction_indexes
        ):
            raise ValueError("native origin instruction index is outside its Assembly block")
        actual_opcodes = [block.instructions[index].opcode.value for index in instruction_indexes]
        if actual_opcodes != opcodes:
            raise ValueError("native origin opcode does not match the AssemblyProgram")
        categories = sorted(
            {_ASSEMBLY_CATEGORIES.get(block.instructions[index].opcode, "UNKNOWN") for index in instruction_indexes}
        )
        origin["assembly_origin_categories"] = categories
        origin["assembly_origin_category"] = categories[0] if len(categories) == 1 else "MIXED"
        status = origin.get("mapping_status")
        if status == "MAPPED":
            if (
                not isinstance(line_range, list)
                or len(line_range) != 2
                or any(isinstance(item, bool) or not isinstance(item, int) for item in line_range)
                or line_range[0] < 1
                or line_range[1] < line_range[0]
            ):
                raise ValueError("mapped native origin has an invalid line range")
            for line_number in range(line_range[0], line_range[1] + 1):
                if line_number > len(native_lines):
                    raise ValueError("native origin line range exceeds emitted assembly")
                if line_number in origins_by_line:
                    raise ValueError("native origin line ranges overlap")
                origins_by_line[line_number] = (
                    function_name,
                    block_name,
                    str(origin["assembly_origin_category"]),
                )
        elif status != "NO_EMITTED_LINES":
            raise ValueError("native origin has an unknown mapping status")
        block_origin_spans[(function_name, block_name)].append(origin)
        validated_origin_spans.append(origin)

    for line_number, raw_line in enumerate(native_lines, start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith(".size "):
            current_function = None
            current_block = None
            continue
        if stripped.endswith(":"):
            label = stripped[:-1]
            if label in symbols:
                current_function = symbols[label]
                current_block = None
                continue
            site = block_sites.get(label)
            if site is not None:
                current_function, block = site
                current_block = site
                continue
            # Other labels inside a function retain their enclosing region.
            continue
        if stripped.startswith("."):
            continue
        match = _INSTRUCTION.fullmatch(stripped)
        if match is None:
            continue
        mnemonic, operands = match.groups()
        counts = function_counts[current_function] if current_function is not None else unattributed_counts
        category = _record_instruction(counts, mnemonic.lower(), operands.lower())
        origin = origins_by_line.get(line_number)
        if origin is None:
            origin_categories["UNMAPPED"] += 1
        else:
            origin_function, origin_block, origin_category = origin
            origin_categories[origin_category] += 1
            function_origin_categories[origin_function][origin_category] += 1
            block_origin_categories[(origin_function, origin_block)][origin_category] += 1
        if current_function is not None:
            function_categories[current_function][category] += 1
            if current_block is not None:
                _record_instruction(block_counts[current_block], mnemonic.lower(), operands.lower())
                block_categories[current_block][category] += 1
                block_line_numbers[current_block].append(line_number)
        else:
            unattributed_categories[category] += 1

    function_reports: list[dict[str, object]] = []
    total_assembly_instructions = 0
    assembly_category_totals: Counter[str] = Counter()
    for function in program.functions:
        assembly_categories: Counter[str] = Counter()
        blocks: list[dict[str, object]] = []
        for block in function.blocks:
            for instruction in block.instructions:
                assembly_categories[_ASSEMBLY_CATEGORIES.get(instruction.opcode, "UNKNOWN")] += 1
            block_native = block_counts[(function.name, block.label)]
            source_locations = {
                instruction.source
                for instruction in block.instructions
                if instruction.source is not None
            }
            source = (
                next(iter(source_locations)).to_dict()
                if len(source_locations) == 1
                else None
            )
            blocks.append(
                {
                    "name": block.label,
                    "source": source,
                    "source_status": "CONSISTENT_INSTRUCTION_LOCATIONS" if len(source_locations) == 1 else "UNKNOWN_OR_MIXED",
                    "assembly_instruction_count": len(block.instructions),
                    "assembly_opcode_counts": dict(sorted(Counter(item.opcode.value for item in block.instructions).items())),
                    "native_assembly": dict(sorted(block_native.items())),
                    "native_machine_opcode_categories": dict(sorted(block_categories[(function.name, block.label)].items())),
                    "native_origin_category": (
                        "UNKNOWN_PER_INSTRUCTION"
                        if not block_origin_categories[(function.name, block.label)]
                        else "ASSEMBLY_OPCODE_LINEAGE"
                    ),
                    "native_origin_category_counts": dict(
                        sorted(block_origin_categories[(function.name, block.label)].items())
                    ),
                    "assembly_to_native_origin_spans": block_origin_spans[(function.name, block.label)],
                    "assembly_to_native_attributed_instruction_count": sum(
                        block_origin_categories[(function.name, block.label)].values()
                    ),
                    "native_assembly_line_range": (
                        [min(block_line_numbers[(function.name, block.label)]), max(block_line_numbers[(function.name, block.label)])]
                        if block_line_numbers[(function.name, block.label)]
                        else None
                    ),
                }
            )
        total_assembly_instructions += sum(len(block.instructions) for block in function.blocks)
        assembly_category_totals.update(assembly_categories)
        frame_bytes, allocation = _frame_layout(function, max_instructions=max_instructions) if not function.external else (None, {})
        native_stats = dict(sorted(function_counts[function.name].items()))
        function_reports.append(
            {
                "name": function.name,
                "external": function.external,
                "assembly_instruction_count": sum(len(block.instructions) for block in function.blocks),
                "assembly_category_counts": dict(sorted(assembly_categories.items())),
                "frame_bytes": frame_bytes,
                "allocation": allocation,
                "native_assembly": native_stats,
                "native_machine_opcode_categories": dict(sorted(function_categories[function.name].items())),
                "assembly_to_native_origin_category_counts": dict(
                    sorted(function_origin_categories[function.name].items())
                ),
                "native_origin_unknown_instruction_count": (
                    native_stats["machine_instruction_count"]
                    - sum(function_origin_categories[function.name].values())
                ),
                "blocks": blocks,
            }
        )

    return {
        "schema_version": "1.0.0",
        "report_kind": "S3_X86_64_CODEGEN_ATTRIBUTION_EXPERIMENTAL",
        "input": {
            "source_sha256": source_sha256,
            "assembly_program_sha256": sha256(_assembly_program_text(program).encode("utf-8")).hexdigest(),
            "native_assembly_sha256": sha256(native_assembly.encode("utf-8")).hexdigest(),
        },
        "configuration": {
            "target": "linux-x86_64",
            "optimization": optimization,
            "register_allocation": True,
            "native_policy": "baseline",
            "instruction_budget_mode": "per-instruction",
            "max_frames": max_frames,
            "max_instructions": max_instructions,
        },
        "summary": {
            "function_count": len(program.functions),
            "block_count": sum(len(function.blocks) for function in program.functions),
            "assembly_instruction_count": total_assembly_instructions,
            "assembly_category_counts": dict(sorted(assembly_category_totals.items())),
            "generated_assembly_text_bytes": len(native_assembly.encode("utf-8")),
            "machine_text_bytes": None,
            "machine_text_bytes_status": "UNAVAILABLE_WITHOUT_ASSEMBLED_OBJECT",
            "native_assembly_instruction_count": sum(counts["machine_instruction_count"] for counts in function_counts.values()) + unattributed_counts["machine_instruction_count"],
            "native_origin_attributed_instructions": sum(
                count for category, count in origin_categories.items() if category != "UNMAPPED"
            ),
            "native_origin_unknown_instructions": origin_categories["UNMAPPED"],
            "native_origin_category_counts": dict(sorted(origin_categories.items())),
            "native_origin_span_count": len(validated_origin_spans),
            "unattributed_generated_runtime": dict(sorted(unattributed_counts.items())),
            "unattributed_machine_opcode_categories": dict(sorted(unattributed_categories.items())),
        },
        "origin_model": {
            "function_regions": "MAPPED_BY_STABLE_FUNCTION_SYMBOL",
            "block_regions": "MAPPED_BY_STABLE_S3_BLOCK_LABEL",
            "instruction_level_lowering_origin": "ASSEMBLY_OPCODE_AND_BLOCK; SOURCE_LOCATION_WHEN_PRESENT",
            "lowering_rule": "UNKNOWN; EMITTER_RULE_ID_NOT_YET_EXPOSED",
            "native_line_ranges": "GENERATED_ASSEMBLY_TEXT_LINES_NOT_BINARY_ADDRESSES",
            "unmapped_lines": "UNMAPPED_AND_COUNTED_EXPLICITLY",
            "syntactic_machine_categories_are_not_semantic_origin": True,
        },
        "functions": function_reports,
    }


def compare_codegen_reports(control: dict[str, Any], candidate: dict[str, Any]) -> dict[str, object]:
    """Compare two report summaries without implying performance causality."""

    control_summary = control["summary"]
    candidate_summary = candidate["summary"]
    metric_names = (
        "assembly_instruction_count",
        "generated_assembly_text_bytes",
        "native_assembly_instruction_count",
        "native_origin_unknown_instructions",
    )
    deltas = {
        name: candidate_summary[name] - control_summary[name]
        for name in metric_names
    }
    return {
        "control_source_sha256": control["input"]["source_sha256"],
        "candidate_source_sha256": candidate["input"]["source_sha256"],
        "metrics_are_static_not_runtime": True,
        "deltas_candidate_minus_control": deltas,
    }
