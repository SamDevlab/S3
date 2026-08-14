"""CFG-aware register liveness analysis for S3 Assembly."""

from __future__ import annotations

from dataclasses import dataclass
from ...assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
)


@dataclass(frozen=True, slots=True)
class InstructionSite:
    """Structural identity of an instruction occurrence within a function."""

    block: str
    index: int


@dataclass(frozen=True, slots=True)
class InstructionLiveness:
    site: InstructionSite
    instruction: AssemblyInstruction
    uses: frozenset[int]
    defs: frozenset[int]
    live_before: frozenset[int]
    live_after: frozenset[int]


@dataclass(frozen=True, slots=True)
class BlockLiveness:
    use: frozenset[int]
    defs: frozenset[int]
    live_in: frozenset[int]
    live_out: frozenset[int]
    instructions: tuple[InstructionLiveness, ...]


@dataclass(frozen=True, slots=True)
class FunctionLiveness:
    blocks: dict[str, BlockLiveness]

    def for_site(self, site: InstructionSite) -> InstructionLiveness:
        try:
            block_liveness = self.blocks[site.block]
            return block_liveness.instructions[site.index]
        except (KeyError, IndexError) as error:
            raise ValueError(f"Instruction site not found: {site!r}") from error

    def live_across_call(self, site: InstructionSite) -> frozenset[int]:
        inst_liveness = self.for_site(site)
        if inst_liveness.instruction.opcode is not AssemblyOpcode.TCALL:
            raise ValueError("Instruction is not a call")
        return (inst_liveness.live_before & inst_liveness.live_after) - inst_liveness.defs


def instruction_use_def(instruction: AssemblyInstruction) -> tuple[frozenset[int], frozenset[int]]:
    """Determine registers used and defined by a single S3 Assembly instruction.

    Fail-closed: if an unknown opcode is encountered, raises a ValueError.
    """
    opcode = instruction.opcode
    regs = instruction.registers

    if opcode is AssemblyOpcode.TCONST:
        return frozenset(), frozenset({regs[0]})
    elif opcode is AssemblyOpcode.TCONST_STR:
        return frozenset(), frozenset({regs[0]})
    elif opcode is AssemblyOpcode.TMOV:
        return frozenset({regs[1]}), frozenset({regs[0]})
    elif opcode in (AssemblyOpcode.TINV, AssemblyOpcode.TCVT):
        return frozenset({regs[1]}), frozenset({regs[0]})
    elif opcode in (
        AssemblyOpcode.TADD,
        AssemblyOpcode.TNDIFF,
        AssemblyOpcode.TMUL,
        AssemblyOpcode.TDIV,
        AssemblyOpcode.TREL,
        AssemblyOpcode.TMIN,
        AssemblyOpcode.TMAX,
        AssemblyOpcode.TCMP,
    ):
        return frozenset({regs[1], regs[2]}), frozenset({regs[0]})
    elif opcode is AssemblyOpcode.TCALL:
        return frozenset(instruction.argument_registers), frozenset(instruction.result_registers)
    elif opcode is AssemblyOpcode.TLOAD:
        return frozenset({regs[1]}), frozenset({regs[0]})
    elif opcode is AssemblyOpcode.TSTORE:
        return frozenset({regs[0], regs[1]}), frozenset()
    elif opcode is AssemblyOpcode.TRET:
        return frozenset(regs), frozenset()
    elif opcode is AssemblyOpcode.TJMP:
        return frozenset(), frozenset()
    elif opcode is AssemblyOpcode.TBR3:
        return frozenset({regs[0]}), frozenset()
    elif opcode is AssemblyOpcode.TADDR:
        return frozenset(regs[1:]), frozenset({regs[0]})
    elif opcode is AssemblyOpcode.TREFLOAD:
        return frozenset({regs[1]}), frozenset({regs[0]})
    elif opcode is AssemblyOpcode.TREFSTORE:
        return frozenset(regs), frozenset()
    elif opcode is AssemblyOpcode.TSLEN:
        return frozenset(regs[1:]), frozenset({regs[0]})
    elif opcode is AssemblyOpcode.TSLOAD:
        return frozenset(regs[1:]), frozenset({regs[0]})
    elif opcode is AssemblyOpcode.TSSTORE:
        return frozenset(regs), frozenset()
    else:
        raise ValueError(f"Unhandled AssemblyOpcode: {opcode}")


def analyze_liveness(function: AssemblyFunction) -> FunctionLiveness:
    """Perform CFG-aware backwards liveness analysis on an AssemblyFunction."""
    # 1. Map blocks by label and find block successors from terminator instruction
    blocks_by_label = {block.label: block for block in function.blocks}
    block_successors: dict[str, frozenset[str]] = {}

    for block in function.blocks:
        if not block.instructions:
            block_successors[block.label] = frozenset()
            continue
        term = block.instructions[-1]
        if term.opcode is AssemblyOpcode.TJMP:
            block_successors[block.label] = frozenset({term.labels[0]})
        elif term.opcode is AssemblyOpcode.TBR3:
            block_successors[block.label] = frozenset(term.labels)
        elif term.opcode is AssemblyOpcode.TRET:
            block_successors[block.label] = frozenset()
        else:
            # Under standard S3 Assembly, blocks always end with a terminator.
            # If not a terminator, we do not assume fallthrough.
            block_successors[block.label] = frozenset()

    # 2. Compute local use and def sets for each block
    block_use: dict[str, frozenset[int]] = {}
    block_def: dict[str, frozenset[int]] = {}

    for block in function.blocks:
        use_set = set()
        def_set = set()
        for inst in block.instructions:
            uses_i, defs_i = instruction_use_def(inst)
            for u in uses_i:
                if u not in def_set:
                    use_set.add(u)
            for d in defs_i:
                def_set.add(d)
        block_use[block.label] = frozenset(use_set)
        block_def[block.label] = frozenset(def_set)

    # 3. Fixed-point iteration for live_in and live_out of each block
    live_in: dict[str, set[int]] = {block.label: set() for block in function.blocks}
    live_out: dict[str, set[int]] = {block.label: set() for block in function.blocks}

    changed = True
    while changed:
        changed = False
        # Iterate in the original block order to ensure determinism
        for block in function.blocks:
            label = block.label
            # live_out[B] = union of live_in[S] for all successors S
            new_live_out = set()
            for succ_label in block_successors[label]:
                if succ_label in live_in:  # ignore unreachable/external blocks not in function
                    new_live_out.update(live_in[succ_label])

            # live_in[B] = use[B] ∪ (live_out[B] - def[B])
            new_live_in = set(block_use[label]) | (new_live_out - block_def[label])

            if new_live_in != live_in[label] or new_live_out != live_out[label]:
                live_in[label] = new_live_in
                live_out[label] = new_live_out
                changed = True

    # 4. Backward scan within each block to compute instruction-level liveness
    blocks_liveness: dict[str, BlockLiveness] = {}

    for block in function.blocks:
        label = block.label
        current_live = set(live_out[label])
        inst_liveness_list: list[InstructionLiveness] = []

        for index, inst in reversed(tuple(enumerate(block.instructions))):
            uses_i, defs_i = instruction_use_def(inst)
            live_after_i = frozenset(current_live)
            live_before_i = frozenset(uses_i | (current_live - defs_i))

            inst_liveness_list.append(
                InstructionLiveness(
                    site=InstructionSite(label, index),
                    instruction=inst,
                    uses=uses_i,
                    defs=defs_i,
                    live_before=live_before_i,
                    live_after=live_after_i,
                )
            )
            current_live = set(live_before_i)

        # Restore original instruction order
        inst_liveness_list.reverse()

        blocks_liveness[label] = BlockLiveness(
            use=block_use[label],
            defs=block_def[label],
            live_in=frozenset(live_in[label]),
            live_out=frozenset(live_out[label]),
            instructions=tuple(inst_liveness_list),
        )

    return FunctionLiveness(blocks=blocks_liveness)
