"""Experimental logical-instruction budget planning for x86-64 emission."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from statistics import median

from ...assembly import AssemblyFunction, AssemblyOpcode


MIN_FAST_SEGMENT_WEIGHT = 2


class InstructionBudgetMode(str, Enum):
    PER_INSTRUCTION = "per-instruction"
    EXACT_SEGMENT = "exact-segment"
    LOOP_HYBRID = "loop-hybrid"


def parse_instruction_budget_mode(
    value: InstructionBudgetMode | str | None,
) -> InstructionBudgetMode:
    if value is None:
        return InstructionBudgetMode.PER_INSTRUCTION
    if isinstance(value, InstructionBudgetMode):
        return value
    try:
        return InstructionBudgetMode(value)
    except (TypeError, ValueError) as error:
        choices = ", ".join(mode.value for mode in InstructionBudgetMode)
        raise ValueError(
            f"instruction budget mode must be one of: {choices}"
        ) from error


def natural_loop_block_labels(function: AssemblyFunction) -> frozenset[str]:
    """Return blocks in natural loops, using CFG reachability and dominance."""
    blocks = {block.label: block for block in function.blocks}
    if not function.blocks:
        return frozenset()

    successors: dict[str, set[str]] = {}
    predecessors: dict[str, set[str]] = {label: set() for label in blocks}
    for block in function.blocks:
        terminator = block.instructions[-1] if block.instructions else None
        if terminator is None:
            targets: set[str] = set()
        elif terminator.opcode is AssemblyOpcode.TJMP:
            targets = set(terminator.labels[:1])
        elif terminator.opcode is AssemblyOpcode.TBR3:
            targets = set(terminator.labels)
        else:
            targets = set()
        targets.intersection_update(blocks)
        successors[block.label] = targets
        for target in targets:
            predecessors[target].add(block.label)

    entry = function.blocks[0].label
    reachable: set[str] = set()
    pending = [entry]
    while pending:
        label = pending.pop()
        if label in reachable:
            continue
        reachable.add(label)
        pending.extend(sorted(successors[label] - reachable, reverse=True))

    dominators = {
        label: ({entry} if label == entry else set(reachable))
        for label in reachable
    }
    changed = True
    while changed:
        changed = False
        for label in sorted(reachable - {entry}):
            incoming = predecessors[label] & reachable
            common = set.intersection(*(dominators[item] for item in incoming)) if incoming else set()
            updated = {label} | common
            if updated != dominators[label]:
                dominators[label] = updated
                changed = True

    loop_blocks: set[str] = set()
    for tail in sorted(reachable):
        for header in sorted(successors[tail]):
            if header not in dominators[tail]:
                continue
            loop = {header, tail}
            worklist = [tail]
            while worklist:
                current = worklist.pop()
                for predecessor in sorted(predecessors[current], reverse=True):
                    if (
                        predecessor in reachable
                        and predecessor not in loop
                        and header in dominators[predecessor]
                    ):
                        loop.add(predecessor)
                        worklist.append(predecessor)
            loop_blocks.update(loop)
    return frozenset(loop_blocks)


@dataclass(frozen=True, slots=True)
class BudgetSegment:
    function: str
    block: str
    first_instruction_index: int
    last_instruction_index: int
    instruction_indexes: tuple[int, ...]
    logical_weight: int
    barrier_type: str


@dataclass(frozen=True, slots=True)
class FunctionBudgetPlan:
    function: str
    logical_instruction_count: int
    segments: tuple[BudgetSegment, ...]


def _barrier_type(opcode: AssemblyOpcode) -> str | None:
    if opcode is AssemblyOpcode.TCALL:
        return "call"
    if opcode in {AssemblyOpcode.TBR3, AssemblyOpcode.TJMP}:
        return "branch"
    if opcode is AssemblyOpcode.TRET:
        return "return"
    return None


def plan_budget_segments(function: AssemblyFunction) -> FunctionBudgetPlan:
    """Partition validated Assembly instructions without crossing barriers."""

    segments: list[BudgetSegment] = []
    logical_instruction_count = 0
    if function.external:
        return FunctionBudgetPlan(function.name, 0, ())

    for block in function.blocks:
        instructions = block.instructions
        logical_instruction_count += len(instructions)
        start = 0
        for index, instruction in enumerate(instructions):
            barrier = _barrier_type(instruction.opcode)
            if barrier is None:
                continue
            indexes = tuple(range(start, index + 1))
            segments.append(
                BudgetSegment(
                    function.name,
                    block.label,
                    start,
                    index,
                    indexes,
                    len(indexes),
                    barrier,
                )
            )
            start = index + 1
        if start < len(instructions):
            indexes = tuple(range(start, len(instructions)))
            segments.append(
                BudgetSegment(
                    function.name,
                    block.label,
                    start,
                    len(instructions) - 1,
                    indexes,
                    len(indexes),
                    "block-end",
                )
            )

    return FunctionBudgetPlan(
        function.name,
        logical_instruction_count,
        tuple(segments),
    )


def budget_plan_diagnostics(
    function: AssemblyFunction,
    *,
    max_instructions: int,
    minimum_fast_segment_weight: int = MIN_FAST_SEGMENT_WEIGHT,
) -> dict[str, object]:
    if isinstance(max_instructions, bool) or not isinstance(max_instructions, int):
        raise TypeError("max_instructions must be an integer")
    if max_instructions < 1:
        raise ValueError("max_instructions must be at least 1")
    if minimum_fast_segment_weight < 1:
        raise ValueError("minimum fast segment weight must be positive")

    plan = plan_budget_segments(function)
    weights = [segment.logical_weight for segment in plan.segments]

    def is_fast_eligible(segment: BudgetSegment) -> bool:
        return (
            segment.logical_weight >= minimum_fast_segment_weight
            and segment.logical_weight <= max_instructions
        )

    fast_segments = [
        segment for segment in plan.segments if is_fast_eligible(segment)
    ]
    histogram: dict[int, int] = {}
    for weight in weights:
        histogram[weight] = histogram.get(weight, 0) + 1

    return {
        "logical_instruction_count": plan.logical_instruction_count,
        "segment_count": len(plan.segments),
        "fast_segment_count": len(fast_segments),
        "scalar_sites": sum(
            segment.logical_weight
            for segment in plan.segments
            if not is_fast_eligible(segment)
        ),
        "max_segment_weight": max(weights, default=0),
        "mean_segment_weight": (
            sum(weights) / len(weights) if weights else 0.0
        ),
        "median_segment_weight": median(weights) if weights else 0,
        "segment_weight_histogram": [
            {"weight": weight, "segments": histogram[weight]}
            for weight in sorted(histogram)
        ],
        "call_barriers": sum(
            segment.barrier_type == "call" for segment in plan.segments
        ),
        "branch_barriers": sum(
            segment.barrier_type == "branch" for segment in plan.segments
        ),
        "return_barriers": sum(
            segment.barrier_type == "return" for segment in plan.segments
        ),
        "other_barriers": 0,
        "segments": [
            {
                "function": segment.function,
                "block": segment.block,
                "first_instruction_index": segment.first_instruction_index,
                "last_instruction_index": segment.last_instruction_index,
                "instruction_indexes": list(segment.instruction_indexes),
                "logical_weight": segment.logical_weight,
                "barrier_type": segment.barrier_type,
                "fast_path_eligible": is_fast_eligible(segment),
            }
            for segment in plan.segments
        ],
    }
