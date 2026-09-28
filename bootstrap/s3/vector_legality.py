"""Diagnostic-only vector legality assessment built on existing loop facts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from .builtin_effects import BuiltinEffect, builtin_effect
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
        recurrences = [
            item for item in analysis.recurrences
            if item.loop_header == loop.header
        ]
        proofs = [item for item in analysis.proofs if item.header == loop.header]
        reductions = [item for item in analysis.reductions if item.loop_header == loop.header]
        strict_fp_reductions = [
            item for item in reductions
            if item.element_type is IRType.F64 and item.ordered
        ]
        legacy_reduction_memories = {item.accumulator_memory for item in reductions}
        continuation_reductions = [
            item for item in recurrences
            if item.kind == "REDUCTION" and item.memory not in legacy_reduction_memories
        ]
        strict_fp_recurrences = [
            item for item in continuation_reductions
            if item.kind == "REDUCTION" and item.element_type is IRType.F64 and item.ordered
        ]
        unknown_or_mutating_calls = sorted(
            {
                instruction.callee or "<missing-callee>"
                for instruction in instructions
                if instruction.opcode is IROpcode.CALL
                and builtin_effect(instruction.callee)
                not in {BuiltinEffect.PURE, BuiltinEffect.READ_ONLY}
            }
        )
        if strict_fp_reductions or strict_fp_recurrences:
            status = VectorLegality.NOT_VECTORIZABLE
            reasons = ["ORDERED_F64_REDUCTION_CANNOT_BE_REASSOCIATED_UNDER_STRICT_FP"]
        else:
            status = VectorLegality.UNKNOWN
            reasons = []
            continuation_inductions = [item for item in recurrences if item.kind == "INDUCTION"]
            if not inductions and not continuation_inductions:
                reasons.append("CANONICAL_AFFINE_INDUCTION_NOT_PROVEN")
            elif not inductions and continuation_inductions:
                reasons.append("INDUCTION_RECURRENCE_PROVEN_BUT_VECTOR_RANGE_NOT_PROVEN")
            if not proofs:
                reasons.append("VECTOR_ACCESS_RANGE_AND_IMMUTABLE_ORIGIN_NOT_PROVEN")
            if unknown_or_mutating_calls:
                reasons.append("UNKNOWN_OR_MUTATING_CALL_EFFECT")
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
                "recognized_continuation_induction_count": sum(
                    item.kind == "INDUCTION" for item in recurrences
                ),
                "recognized_scalar_recurrence_count": len(recurrences),
                "recurrence_kinds": sorted({item.kind for item in recurrences}),
                "recurrences": [
                    {
                        "memory": item.memory,
                        "condition_memory": item.condition_memory,
                        "condition_relation": item.condition_relation,
                        "element_type": item.element_type.value,
                        "kind": item.kind,
                        "operation": item.operation,
                        "initial_value": item.initial_value,
                        "step": item.step,
                        "update_sites": [list(site) for site in item.update_sites],
                        "backedge_updates": [list(state) for state in item.backedge_updates],
                        "ordered": item.ordered,
                    }
                    for item in recurrences
                ],
                "vector_bounds_proof_count": len(proofs),
                "ordered_reduction_count": sum(item.ordered for item in reductions)
                + sum(item.ordered for item in continuation_reductions),
                "strict_f64_reduction_count": len(strict_fp_reductions)
                + len(strict_fp_recurrences),
                "opcode_counts": {
                    opcode.value: sum(item.opcode is opcode for item in instructions)
                    for opcode in sorted({item.opcode for item in instructions}, key=lambda value: value.value)
                },
                "memory_pattern": "UNKNOWN",
                "dependence": "UNKNOWN",
                "unknown_or_mutating_calls": unknown_or_mutating_calls,
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
            "continuation_inductions_recognized": sum(
                item.kind == "INDUCTION" for item in analysis.recurrences
            ),
            "continuation_reductions_recognized": sum(
                item.kind == "REDUCTION" for item in analysis.recurrences
            ),
            "vectorizable_loops": 0,
            "not_vectorizable_loops": sum(
                item["status"] == VectorLegality.NOT_VECTORIZABLE.value for item in loop_reports
            ),
            "unknown_loops": sum(item["status"] == VectorLegality.UNKNOWN.value for item in loop_reports),
        },
    }
