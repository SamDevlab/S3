"""SSA representation, phi placement, SSA builder, and validator for S3."""

from __future__ import annotations

from dataclasses import dataclass, field

from .cfg import ControlFlowGraph
from .diagnostics import SourceLocation
from .dominance import DominatorTree
from .ir import (
    IRFunction,
    IROpcode,
    IRType,
)


class SSAValidationError(Exception):
    """Exception raised when SSA validation fails."""

    def __init__(self, message: str, location: SourceLocation | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.location = location


@dataclass(frozen=True, slots=True)
class SSAValue:
    """Represents a single-assignment SSA value."""

    name: str
    original_register: int | None = None
    type: IRType = IRType.TRYTE
    def_block: str | None = None


@dataclass(slots=True)
class SSAPhiNode:
    """Represents a Phi node at the beginning of a basic block in SSA form."""

    target: SSAValue
    original_register: int
    operands: dict[str, SSAValue] = field(default_factory=dict)
    location: SourceLocation | None = None


@dataclass(slots=True)
class SSAInstruction:
    """Represents an IR instruction operating on SSAValues."""

    opcode: IROpcode
    result: SSAValue | None = None
    operands: tuple[SSAValue, ...] = ()
    immediate: int | str | None = None
    targets: tuple[str, ...] = ()
    memory: int | None = None
    initialization: bool = False
    location: SourceLocation | None = None


@dataclass(slots=True)
class SSABlock:
    """Represents a basic block in SSA form."""

    name: str
    phis: list[SSAPhiNode] = field(default_factory=list)
    instructions: list[SSAInstruction] = field(default_factory=list)


@dataclass(slots=True)
class SSAParameter:
    """Represents a function parameter in SSA form."""

    value: SSAValue


@dataclass(slots=True)
class SSAFunction:
    """Represents an IR function in SSA form."""

    name: str
    parameters: tuple[SSAParameter, ...]
    blocks: tuple[SSABlock, ...]
    values: tuple[SSAValue, ...]


@dataclass(slots=True)
class SSAModule:
    """Represents a module of functions in SSA form."""

    functions: tuple[SSAFunction, ...]


class SSABuilder:
    """Converts a standard IRFunction into an SSAFunction."""

    @classmethod
    def build_function(cls, function: IRFunction) -> SSAFunction:
        cfg = ControlFlowGraph.build(function)
        dom_tree = DominatorTree.build(cfg)

        register_types = {r.index: r.type for r in function.registers}

        # 1. Collect def blocks for each register
        def_blocks: dict[int, set[str]] = {}
        for block in function.blocks:
            for inst in block.instructions:
                if inst.result is not None:
                    def_blocks.setdefault(inst.result, set()).add(block.name)

        # 2. Phi placement using Dominance Frontier
        phis_by_block: dict[str, list[SSAPhiNode]] = {b.name: [] for b in function.blocks}
        for reg, blocks_defining in def_blocks.items():
            worklist = sorted(blocks_defining)
            added_phi_blocks: set[str] = set()
            reg_type = register_types.get(reg, IRType.TRYTE)

            while worklist:
                x_name = worklist.pop(0)
                for y_name in sorted(dom_tree.dominance_frontier.get(x_name, set())):
                    if y_name not in added_phi_blocks:
                        added_phi_blocks.add(y_name)
                        dummy_val = SSAValue(
                            name=f"r{reg}_phi",
                            original_register=reg,
                            type=reg_type,
                            def_block=y_name,
                        )
                        phi_node = SSAPhiNode(target=dummy_val, original_register=reg)
                        phis_by_block[y_name].append(phi_node)
                        if y_name not in blocks_defining:
                            worklist.append(y_name)

        # 3. Variable Renaming via Dominator Tree traversal
        stacks: dict[int, list[SSAValue]] = {}
        version_counter: dict[int, int] = {}
        all_ssa_values: list[SSAValue] = []

        def new_version(reg: int, block_name: str) -> SSAValue:
            v = version_counter.get(reg, 0)
            version_counter[reg] = v + 1
            reg_type = register_types.get(reg, IRType.TRYTE)
            val = SSAValue(
                name=f"r{reg}_v{v}",
                original_register=reg,
                type=reg_type,
                def_block=block_name,
            )
            stacks.setdefault(reg, []).append(val)
            all_ssa_values.append(val)
            return val

        def get_current(reg: int) -> SSAValue:
            if reg in stacks and stacks[reg]:
                return stacks[reg][-1]
            reg_type = register_types.get(reg, IRType.TRYTE)
            val = SSAValue(
                name=f"r{reg}_undef",
                original_register=reg,
                type=reg_type,
                def_block=None,
            )
            all_ssa_values.append(val)
            return val

        # Handle function parameters
        ssa_params: list[SSAParameter] = []
        entry_block_name = function.blocks[0].name if function.blocks else "entry"
        for p in function.parameters:
            val = new_version(p.register, entry_block_name)
            ssa_params.append(SSAParameter(value=val))

        ssa_blocks_dict: dict[str, SSABlock] = {}
        for block in function.blocks:
            ssa_blocks_dict[block.name] = SSABlock(
                name=block.name,
                phis=list(phis_by_block[block.name]),
            )

        def rename(block_name: str) -> None:
            pushed_regs: list[int] = []
            ssa_block = ssa_blocks_dict[block_name]

            # Rename phi targets
            for phi in ssa_block.phis:
                new_target = new_version(phi.original_register, block_name)
                phi.target = new_target
                pushed_regs.append(phi.original_register)

            orig_block = next(b for b in function.blocks if b.name == block_name)
            # Rename instruction operands and results
            for inst in orig_block.instructions:
                op_vals = tuple(get_current(op) for op in inst.operands)
                res_val = None
                if inst.result is not None:
                    res_val = new_version(inst.result, block_name)
                    pushed_regs.append(inst.result)

                ssa_inst = SSAInstruction(
                    opcode=inst.opcode,
                    result=res_val,
                    operands=op_vals,
                    immediate=inst.immediate,
                    targets=inst.targets,
                    memory=inst.memory,
                    initialization=inst.initialization,
                    location=inst.location,
                )
                ssa_block.instructions.append(ssa_inst)

            # Update phi operands in CFG successors
            succs = cfg.nodes[block_name].successors if block_name in cfg.nodes else set()
            for succ_name in sorted(succs):
                succ_ssa_block = ssa_blocks_dict[succ_name]
                for phi in succ_ssa_block.phis:
                    phi.operands[block_name] = get_current(phi.original_register)

            # Recurse over dominator tree children
            for child in sorted(dom_tree.children.get(block_name, set())):
                rename(child)

            # Pop stack for registers defined in this block
            for reg in reversed(pushed_regs):
                stacks[reg].pop()

        if function.blocks:
            rename(entry_block_name)

        ssa_blocks_list = tuple(ssa_blocks_dict[b.name] for b in function.blocks)

        return SSAFunction(
            name=function.name,
            parameters=tuple(ssa_params),
            blocks=ssa_blocks_list,
            values=tuple(all_ssa_values),
        )


def validate_ssa(function: SSAFunction, cfg: ControlFlowGraph, dom_tree: DominatorTree) -> None:
    """Validates SSA form correctness for an SSAFunction."""
    defined_values: dict[str, str | None] = {}

    entry = cfg.entry_name
    for param in function.parameters:
        if param.value.name in defined_values:
            raise SSAValidationError(f"duplicate definition of parameter {param.value.name}")
        defined_values[param.value.name] = entry

    # Pass 1: Collect all definitions and check for duplicates
    for block in function.blocks:
        for phi in block.phis:
            if phi.target.name in defined_values:
                raise SSAValidationError(f"duplicate definition of SSA value {phi.target.name} in phi node")
            defined_values[phi.target.name] = block.name

        for inst in block.instructions:
            if inst.result is not None:
                if inst.result.name in defined_values:
                    raise SSAValidationError(f"duplicate definition of SSA value {inst.result.name}")
                defined_values[inst.result.name] = block.name

    # Pass 2: Validate Phi and Instruction Operands & Dominance
    for block in function.blocks:
        # Validate Phi nodes
        for phi in block.phis:
            preds = cfg.nodes[block.name].predecessors if block.name in cfg.nodes else set()
            for pred in preds:
                if pred not in phi.operands:
                    raise SSAValidationError(
                        f"phi node in block {block.name} missing operand for predecessor {pred}"
                    )
                op_val = phi.operands[pred]
                if op_val.name not in defined_values and op_val.def_block is not None:
                    raise SSAValidationError(
                        f"phi node in block {block.name} uses undefined operand {op_val.name}"
                    )

        # Validate non-phi instructions
        for inst in block.instructions:
            for op in inst.operands:
                if op.name not in defined_values and op.def_block is not None:
                    raise SSAValidationError(
                        f"instruction in block {block.name} uses undefined operand {op.name}"
                    )
                if op.def_block is not None:
                    def_b = defined_values.get(op.name)
                    if def_b is not None and def_b != block.name:
                        if not dom_tree.dominates(def_b, block.name):
                            raise SSAValidationError(
                                f"use of {op.name} in {block.name} is not dominated by definition in {def_b}"
                            )
