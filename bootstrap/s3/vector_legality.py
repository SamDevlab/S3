"""Diagnostic-only vector legality assessment built on existing loop facts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from .ir import IRFunction, IRType, IROpcode
from .ssa_optimizer.loops import analyze_loop_facts


class VectorLegality(StrEnum):
    NOT_VECTORIZABLE = "NOT_VECTORIZABLE"
    UNKNOWN = "UNKNOWN"


def analyze_vector_legality(function: IRFunction) -> dict[str, Any]:
    """Report only legality supported by current proofs; never authorizes codegen."""

    analysis = analyze_loop_facts(function)
    loop_reports: list[dict[str, object]] = []
    for loop in analysis.loops:
        instructions = [
            instruction
            for block in function.blocks
            if block.name in loop.blocks
            for instruction in block.instructions
        ]
        inductions = [
            item for item in analysis.inductions
            if item.update_block in loop.blocks
        ]
        proofs = [item for item in analysis.proofs if item.header == loop.header]
        reductions = [item for item in analysis.reductions if item.loop_header == loop.header]
        strict_fp_reductions = [
            item for item in reductions
            if item.element_type is IRType.F64 and item.ordered
        ]
        if strict_fp_reductions:
            status = VectorLegality.NOT_VECTORIZABLE
            reasons = ["ORDERED_F64_REDUCTION_CANNOT_BE_REASSOCIATED_UNDER_STRICT_FP"]
        else:
            status = VectorLegality.UNKNOWN
            reasons = []
            if not inductions:
                reasons.append("CANONICAL_AFFINE_INDUCTION_NOT_PROVEN")
            if not proofs:
                reasons.append("VECTOR_ACCESS_RANGE_AND_IMMUTABLE_ORIGIN_NOT_PROVEN")
            reasons.append("GENERAL_INTER_ITERATION_MEMORY_DEPENDENCE_NOT_MODELED")

        loop_reports.append(
            {
                "header": loop.header,
                "blocks": sorted(loop.blocks),
                "backedges": list(loop.backedges),
                "exits": list(loop.exits),
                "status": status.value,
                "reasons": reasons,
                "recognized_induction_count": len(inductions),
                "vector_bounds_proof_count": len(proofs),
                "ordered_reduction_count": sum(item.ordered for item in reductions),
                "strict_f64_reduction_count": len(strict_fp_reductions),
                "opcode_counts": {
                    opcode.value: sum(item.opcode is opcode for item in instructions)
                    for opcode in sorted({item.opcode for item in instructions}, key=lambda value: value.value)
                },
                "memory_pattern": "UNKNOWN",
                "dependence": "UNKNOWN",
            }
        )

    return {
        "function": function.name,
        "analysis_kind": "DIAGNOSTIC_ONLY_NO_TRANSFORMATION_AUTHORIZED",
        "loops": loop_reports,
        "summary": {
            "loops_seen": len(analysis.loops),
            "inductions_recognized": analysis.metrics.inductions_recognized,
            "vector_bounds_proofs": len(analysis.proofs),
            "reductions_recognized": len(analysis.reductions),
            "vectorizable_loops": 0,
            "not_vectorizable_loops": sum(
                item["status"] == VectorLegality.NOT_VECTORIZABLE.value for item in loop_reports
            ),
            "unknown_loops": sum(item["status"] == VectorLegality.UNKNOWN.value for item in loop_reports),
        },
    }
