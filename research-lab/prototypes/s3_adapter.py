"""Adapter from current S3 AssemblyFunction into the generic research CFG.

Unlike the mathematical core prototypes, this file intentionally imports S3
production types.  It is still research-only and must not be imported by the
production compiler.
"""

from __future__ import annotations

from bootstrap.s3.assembly import AssemblyFunction, AssemblyOpcode
from bootstrap.s3.backends.x86_64.liveness import instruction_use_def

from cfg import Block, CFG, Instruction


def _successors(block) -> tuple[str, ...]:
    if not block.instructions:
        return ()
    term = block.instructions[-1]
    if term.opcode is AssemblyOpcode.TJMP:
        return tuple(term.labels[:1])
    if term.opcode is AssemblyOpcode.TBR3:
        return tuple(term.labels)
    return ()


def from_assembly_function(function: AssemblyFunction) -> CFG:
    """Project S3 Assembly into the generic use/def CFG research model."""

    blocks: list[Block] = []
    for block in function.blocks:
        instructions: list[Instruction] = []
        for index, assembly_instruction in enumerate(block.instructions):
            uses, defs = instruction_use_def(assembly_instruction)
            instructions.append(
                Instruction.make(
                    f"{index}:{assembly_instruction.opcode.value}",
                    uses=(str(register) for register in uses),
                    defs=(str(register) for register in defs),
                )
            )
        blocks.append(
            Block.make(
                block.label,
                instructions,
                successors=_successors(block),
            )
        )

    if not blocks:
        raise ValueError("cannot adapt function without basic blocks")
    return CFG.make(blocks[0].name, blocks)


def compare_liveness(function: AssemblyFunction) -> dict[str, object]:
    """Cross-check generic and production block-level liveness.

    This is intended as an early bridge test before novel research analyses are
    trusted on production S3 data.
    """

    from bootstrap.s3.backends.x86_64.liveness import analyze_liveness as s3_liveness
    from liveness import analyze_liveness as research_liveness

    generic = from_assembly_function(function)
    research = research_liveness(generic)
    production = s3_liveness(function)

    mismatches: list[dict[str, object]] = []
    for block_name in generic.order:
        research_block = research.blocks[block_name]
        production_block = production.blocks[block_name]
        research_in = {int(value) for value in research_block.live_in}
        research_out = {int(value) for value in research_block.live_out}
        if research_in != set(production_block.live_in) or research_out != set(
            production_block.live_out
        ):
            mismatches.append(
                {
                    "block": block_name,
                    "research_live_in": sorted(research_in),
                    "production_live_in": sorted(production_block.live_in),
                    "research_live_out": sorted(research_out),
                    "production_live_out": sorted(production_block.live_out),
                }
            )

    return {
        "function": function.name,
        "blocks": len(generic.order),
        "research_iterations": research.iterations,
        "mismatches": mismatches,
        "match": not mismatches,
    }
