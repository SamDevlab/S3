from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bootstrap.s3.cfg import ControlFlowGraph
from bootstrap.s3.initialization import analyze_initialization
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa import SSABuilder
from bootstrap.s3.ssa_optimizer.lowering import to_ir


def analyze(source_path: Path, output_path: Path) -> None:
    source = source_path.read_text(encoding="utf-8")
    modes = {}
    for optimization in ("O0", "O1"):
        compilation = compile_source(source, optimization)
        functions = []
        phi_count = 0
        phi_edge_copy_count = 0
        critical_edge_count = 0
        backedge_count = 0
        for function in compilation.ir.functions:
            if function.external:
                continue
            cfg = ControlFlowGraph.build(function)
            critical = []
            backedges = []
            order = {block.name: index for index, block in enumerate(function.blocks)}
            for block in function.blocks:
                targets = tuple(cfg.nodes[block.name].successors)
                for target in targets:
                    if len(targets) > 1 and len(cfg.nodes[target].predecessors) > 1:
                        critical.append((block.name, target))
                    if order.get(target, 10**9) <= order.get(block.name, -1):
                        backedges.append((block.name, target))
            ssa = SSABuilder.build_function(function)
            function_phis = sum(len(block.phis) for block in ssa.blocks)
            function_edge_copies = sum(
                len(phi.operands)
                for block in ssa.blocks
                for phi in block.phis
            )
            phi_count += function_phis
            phi_edge_copy_count += function_edge_copies
            critical_edge_count += len(critical)
            backedge_count += len(backedges)
            out_of_ssa = to_ir(ssa)
            functions.append(
                {
                    "function": function.name,
                    "blocks": len(function.blocks),
                    "ir_instructions": len(function.instructions),
                    "memory_objects": len(function.memory_objects),
                    "ssa_phis": function_phis,
                    "ssa_phi_edge_operands": function_edge_copies,
                    "out_of_ssa_added_memory_objects": (
                        len(out_of_ssa.memory_objects) - len(function.memory_objects)
                    ),
                    "critical_edges": critical,
                    "backedges": backedges,
                    "initialization_stores": sum(
                        instruction.initialization
                        for instruction in function.instructions
                    ),
                    "loads": sum(
                        instruction.opcode.value in {"load", "slice_load"}
                        for instruction in function.instructions
                    ),
                    "stores": sum(
                        instruction.opcode.value in {"store", "slice_store"}
                        for instruction in function.instructions
                    ),
                }
            )
        try:
            initialization = analyze_initialization(compilation.ir)
            init_status = "PASS"
            init_error = None
            state_counts = {}
            for report in initialization.functions:
                for _, states in report.entry_states:
                    for _, state in states:
                        state_counts[state] = state_counts.get(state, 0) + 1
        except Exception as error:
            init_status = "EXPECTED_OR_RECORDED_FAILURE"
            init_error = str(error)
            state_counts = {}
        modes[optimization] = {
            "functions": functions,
            "phi_count": phi_count,
            "phi_edge_copy_count": phi_edge_copy_count,
            "critical_edge_count": critical_edge_count,
            "backedge_count": backedge_count,
            "initialization_analysis": init_status,
            "initialization_error": init_error,
            "initialization_entry_state_counts": state_counts,
        }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps({"source": str(source_path), "modes": modes}, indent=2)
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: p5_static_semantics.py SOURCE OUTPUT")
    analyze(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
