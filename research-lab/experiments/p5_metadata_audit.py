from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def _offset(text: str) -> int | None:
    match = re.search(r"\[rbp(?:\s*([+-])\s*(\d+))?\]", text)
    if not match:
        return None
    if not match.group(1):
        return 0
    value = int(match.group(2))
    return -value if match.group(1) == "-" else value


def _region_contains(region: object, offset: int) -> bool:
    return region.first_address <= offset <= region.last_address


def _slot_kind(layout: object, line: str, offset: int | None) -> str:
    # A trit array is byte-addressed too.  P4's metric did not distinguish
    # its data bytes from the initialized-state bytes, so classify both exact
    # addresses and indexed forms such as [rbp + r10 - 407].
    address = line[line.find("[rbp") + 1 : line.find("]", line.find("[rbp"))]
    dynamic = bool(re.search(r"rbp\s*[+-]\s*[a-z]+", address))
    base_match = re.search(r"(?:^|[+-])\s*(\d+)\s*$", address)
    base = -int(base_match.group(1)) if base_match and "-" in base_match.group(0) else None
    for slot in layout.registers:
        if offset is not None and _region_contains(slot.initialized, offset):
            return "REGISTER_INITIALIZATION"
    for slot in layout.memories:
        if offset is not None and _region_contains(slot.initialized, offset):
            return "MEMORY_INITIALIZATION"
        if offset is not None and _region_contains(slot.data, offset):
            return "MEMORY_DATA"
        if dynamic and base == slot.initialized.first_address:
            return "MEMORY_INITIALIZATION"
        if dynamic and base == slot.data.first_address:
            return "MEMORY_DATA"
    return "OTHER_BYTE_FRAME_STATE"


def _line_kind(line: str, slot_kind: str) -> str:
    if "cmp byte ptr" in line or re.search(r"(?:movsx|movzx|mov)\s+[^,]+,\s*byte ptr", line):
        operation = "LOAD"
    elif re.search(r"mov byte ptr", line):
        operation = "STORE"
    else:
        operation = "OTHER"
    return f"{slot_kind}_{operation}"


def _frame_metrics(text: str) -> dict[str, int]:
    rows: Counter[str] = Counter()
    for line in text.splitlines():
        if "rbp" not in line:
            continue
        rows["all"] += 1
        if re.search(r"mov(?:sx|zx)?\s+[^,]+,\s+qword ptr \[rbp", line):
            rows["loads"] += 1
        if re.search(r"mov(?:sx|zx)?\s+qword ptr \[rbp", line):
            rows["stores"] += 1
        if "byte ptr [rbp" in line:
            rows["metadata"] += 1
    return dict(rows)


def _metadata_lines(native: str, compilation: object) -> tuple[Counter[str], list[dict[str, object]]]:
    from bootstrap.s3.backends.x86_64.emitter import function_symbol
    from bootstrap.s3.backends.x86_64.layout import layout_frame
    from bootstrap.s3.backends.x86_64.allocation import analyze_allocation

    functions = {function_symbol(function): function for function in compilation.assembly.functions}
    layouts = {}
    for function in compilation.assembly.functions:
        if function.external:
            continue
        allocation = analyze_allocation(function)
        layouts[function_symbol(function)] = layout_frame(function, allocation.used_physical_registers)

    current_function: str | None = None
    current_block: str = "<prologue>"
    seen_block = False
    counts: Counter[str] = Counter()
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(native.splitlines(), 1):
        stripped = line.strip()
        if stripped.endswith(":") and stripped[:-1] in functions:
            current_function = stripped[:-1]
            current_block = "<prologue>"
            seen_block = False
            continue
        if current_function and stripped.startswith(".L_s3_") and stripped.endswith(":"):
            current_block = stripped[3:-1]
            seen_block = True
        if "byte ptr [rbp" not in line:
            continue
        if current_function is None or current_function not in layouts:
            family = "UNMAPPED_BYTE_FRAME_STATE"
            function_name = "<unmapped>"
            block_name = "<unmapped>"
        else:
            address = _offset(line)
            slot_kind = _slot_kind(layouts[current_function], line, address)
            family = _line_kind(line, slot_kind)
            function_name = functions[current_function].name
            block_name = current_block
        counts[family] += 1
        rows.append({
            "function": function_name,
            "block": block_name,
            "line": line_number,
            "family": family,
            "text": line.strip(),
            "weight_kind": "UNKNOWN",
            "dynamic_weight": None,
            "semantic_necessity": (
                "REQUIRED_OR_CONDITIONALLY_AVOIDABLE"
                if family.startswith(("REGISTER_INITIALIZATION", "MEMORY_INITIALIZATION"))
                else "UNKNOWN"
            ),
        })
    return counts, rows


def _cfg_summary(compilation: object) -> dict[str, object]:
    from bootstrap.s3.assembly import AssemblyOpcode

    functions: list[dict[str, object]] = []
    total_critical = 0
    total_backedges = 0
    for function in compilation.assembly.functions:
        if function.external:
            continue
        blocks = {block.label: block for block in function.blocks}
        successors: dict[str, tuple[str, ...]] = {}
        for block in function.blocks:
            last = block.instructions[-1] if block.instructions else None
            successors[block.label] = last.labels if last and last.opcode in {
                AssemblyOpcode.TJMP, AssemblyOpcode.TBR3
            } else ()
        predecessors: dict[str, set[str]] = {name: set() for name in blocks}
        for source, targets in successors.items():
            for target in targets:
                predecessors.setdefault(target, set()).add(source)
        critical = [
            [source, target]
            for source, targets in successors.items()
            if len(targets) > 1
            for target in targets
            if len(predecessors.get(target, ())) > 1
        ]
        order = {block.label: index for index, block in enumerate(function.blocks)}
        backedges = [
            [source, target]
            for source, targets in successors.items()
            for target in targets
            if order.get(target, 10**9) <= order.get(source, -1)
        ]
        total_critical += len(critical)
        total_backedges += len(backedges)
        functions.append({
            "function": function.name,
            "blocks": len(function.blocks),
            "instructions": len(function.instructions),
            "calls": sum(item.opcode is AssemblyOpcode.TCALL for item in function.instructions),
            "critical_edges": critical,
            "backedges_estimated_by_block_order": backedges,
            "phi_nodes_explicit_in_assembly": 0,
            "parallel_copy_nodes_explicit_in_assembly": 0,
        })
    return {
        "functions": functions,
        "critical_edge_count": total_critical,
        "backedge_count_estimated_by_block_order": total_backedges,
        "phi_lowering_model": "NO_EXPLICIT_PHI_OR_EDGE_COPY_IN_ASSEMBLY_IR; SSA IS LOWERED BEFORE ASSEMBLY IR",
        "parallel_copy_model": "NOT_EXPLICIT_IN_ASSEMBLY_IR",
    }


def _ir_summary(compilation: object) -> dict[str, object]:
    from bootstrap.s3.ir import IROpcode

    opcode_counts: Counter[str] = Counter()
    function_rows: list[dict[str, object]] = []
    for function in compilation.ir.functions:
        if function.external:
            continue
        counts = Counter(item.opcode.value for item in function.instructions)
        opcode_counts.update(counts)
        function_rows.append({
            "function": function.name,
            "blocks": len(function.blocks),
            "instructions": len(function.instructions),
            "memory_objects": len(function.memory_objects),
            "opcodes": dict(sorted(counts.items())),
            "explicit_phi_opcodes": 0,
        })
    return {
        "opcode_counts": dict(sorted(opcode_counts.items())),
        "functions": function_rows,
        "ssa_phi_available_in_this_pipeline": False,
        "note": "compile_source returns ordinary IR lowered to Assembly IR; internal SSA helpers are not an input to this path",
    }


def _run(repo: Path, source_path: Path, output: Path) -> None:
    sys.path.insert(0, str(repo))
    from bootstrap.s3.backends.x86_64 import X8664Backend
    from bootstrap.s3.optimizer import OptimizationLevel
    from bootstrap.s3.pipeline import compile_source

    source = source_path.read_text(encoding="utf-8")
    compilation = compile_source(source, OptimizationLevel.O1)
    results: dict[str, object] = {
        "audit_base": "a0b694fadc985c0b8e0944fb7844e14f72a838d8",
        "source": str(source_path),
        "source_outside_production_audit_base": True,
        "assembly_functions": len(compilation.assembly.functions),
        "assembly_instructions": sum(len(function.instructions) for function in compilation.assembly.functions),
        "assembly_memory_objects": sum(len(function.memory_objects) for function in compilation.assembly.functions),
        "ir": _ir_summary(compilation),
        "cfg": _cfg_summary(compilation),
        "modes": {},
    }
    for mode, enabled in (("RA_OFF", False), ("RA_ON", True)):
        native = X8664Backend(register_allocation=enabled).generate(compilation.assembly)
        family_counts, rows = _metadata_lines(native, compilation)
        results["modes"][mode] = {
            "frame_metrics": _frame_metrics(native),
            "metadata_family_counts": dict(sorted(family_counts.items())),
            "metadata_lines": rows,
            "memory_initialization_rep_stosb_instructions": native.count("rep stosb"),
            "metadata_metric_definition": "all emitted lines containing byte ptr [rbp",
        }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: p5_metadata_audit.py REPO SOURCE OUTPUT")
    _run(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
