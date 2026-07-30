"""Memory SSA Infrastructure for S3 IR memory optimizations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from .cfg import ControlFlowGraph
from .dominance import DominatorTree
from .ir import IROpcode
from .ssa import SSABlock, SSAFunction, SSAInstruction, SSAValue


@dataclass(frozen=True, slots=True)
class MemoryDef:
    """Represents a memory mutation (STORE or call with memory side effects)."""

    target_version: str
    src_version: str
    memory_index: int
    instruction: SSAInstruction


@dataclass(frozen=True, slots=True)
class MemoryUse:
    """Represents a memory access/read (LOAD)."""

    version: str
    memory_index: int
    instruction: SSAInstruction


@dataclass(frozen=True, slots=True)
class MemoryPhi:
    """Represents a memory version merge at CFG join points."""

    target_version: str
    operands: Dict[str, str]
    memory_index: int


@dataclass(slots=True)
class MemorySSA:
    """Memory SSA representation constructed over an SSAFunction."""

    function: SSAFunction
    defs: List[MemoryDef] = field(default_factory=list)
    uses: List[MemoryUse] = field(default_factory=list)
    phis: List[MemoryPhi] = field(default_factory=list)

    @classmethod
    def build(
        cls,
        ssa_fn: SSAFunction,
        cfg: ControlFlowGraph,
        dom_tree: DominatorTree,
    ) -> MemorySSA:
        """Constructs Memory SSA form for the given SSAFunction."""
        mem_ssa = cls(function=ssa_fn)
        version_counter: Dict[int, int] = {}
        current_version: Dict[int, str] = {}

        def new_version(mem_idx: int) -> str:
            v = version_counter.get(mem_idx, 0)
            version_counter[mem_idx] = v + 1
            ver_str = f"m{mem_idx}_v{v}"
            current_version[mem_idx] = ver_str
            return ver_str

        def get_current(mem_idx: int) -> str:
            if mem_idx in current_version:
                return current_version[mem_idx]
            ver_str = f"m{mem_idx}_v0"
            current_version[mem_idx] = ver_str
            return ver_str

        for block in ssa_fn.blocks:
            for inst in block.instructions:
                if inst.memory is not None:
                    mem_idx = inst.memory
                    if inst.opcode is IROpcode.STORE:
                        src_v = get_current(mem_idx)
                        tgt_v = new_version(mem_idx)
                        mem_ssa.defs.append(
                            MemoryDef(
                                target_version=tgt_v,
                                src_version=src_v,
                                memory_index=mem_idx,
                                instruction=inst,
                            )
                        )
                    elif inst.opcode is IROpcode.LOAD:
                        curr_v = get_current(mem_idx)
                        mem_ssa.uses.append(
                            MemoryUse(
                                version=curr_v,
                                memory_index=mem_idx,
                                instruction=inst,
                            )
                        )

        return mem_ssa
