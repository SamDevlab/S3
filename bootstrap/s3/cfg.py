"""Basic Control Flow Graph (CFG) and reachability analysis for S3 IR."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .ir import IRBasicBlock, IRFunction, IROpcode


@dataclass(slots=True)
class CFGNode:
    """Node in the control flow graph wrapping a basic block."""

    name: str
    block: IRBasicBlock
    predecessors: set[str] = field(default_factory=set)
    successors: set[str] = field(default_factory=set)


@dataclass(slots=True)
class ControlFlowGraph:
    """Control Flow Graph representation for an IR function."""

    entry_name: str
    nodes: dict[str, CFGNode]

    @classmethod
    def build(cls, function: IRFunction) -> ControlFlowGraph:
        nodes: dict[str, CFGNode] = {
            block.name: CFGNode(name=block.name, block=block)
            for block in function.blocks
        }
        for block in function.blocks:
            node = nodes[block.name]
            if not block.instructions:
                continue
            last_inst = block.instructions[-1]
            if last_inst.opcode in {IROpcode.JUMP, IROpcode.BRANCH3}:
                for target in last_inst.targets:
                    if target in nodes:
                        node.successors.add(target)
                        nodes[target].predecessors.add(block.name)

        entry_name = "entry" if "entry" in nodes else (function.blocks[0].name if function.blocks else "entry")
        return cls(entry_name=entry_name, nodes=nodes)


    def reachable_nodes(self) -> set[str]:
        """Returns the set of block names reachable from the entry block."""
        if self.entry_name not in self.nodes:
            return set()
        visited: set[str] = set()
        pending = [self.entry_name]
        while pending:
            curr = pending.pop()
            if curr in visited:
                continue
            visited.add(curr)
            if curr in self.nodes:
                for succ in self.nodes[curr].successors:
                    if succ not in visited:
                        pending.append(succ)
        return visited

    def unreachable_nodes(self) -> set[str]:
        """Returns the set of block names unreachable from the entry block."""
        return set(self.nodes.keys()) - self.reachable_nodes()


def remove_unreachable_blocks_cfg(function: IRFunction) -> IRFunction:
    """Eliminates unreachable basic blocks using CFG reachability analysis."""
    cfg = ControlFlowGraph.build(function)
    reachable = cfg.reachable_nodes()
    return replace(
        function,
        blocks=tuple(block for block in function.blocks if block.name in reachable),
    )
