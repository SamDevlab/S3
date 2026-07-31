"""SSA optimization passes and SSA-to-IR conversion for S3 IR."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Set, Tuple

from .alias_analysis import AliasAnalysis, AliasResult
from .cfg import ControlFlowGraph
from .dominance import DominatorTree
from .ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IROpcode,
    IRParameter,
    IRRegister,
    IRType,
)
from .memory_ssa import MemorySSA
from .metrics import FixpointTelemetry
from .ssa import (
    SSABlock,
    SSAFunction,
    SSAInstruction,
    SSAParameter,
    SSAPhiNode,
    SSAValue,
)
from .ternary import (
    TernaryRangeError,
    TernaryWidth,
    add,
    compare,
    invert,
    tritwise_max,
    tritwise_min,
)

_FOLDABLE_OPCODES = {
    IROpcode.MOVE,
    IROpcode.INVERT,
    IROpcode.ADD,
    IROpcode.MINIMUM,
    IROpcode.MAXIMUM,
    IROpcode.COMPARE,
}

_PURE_REMOVABLE_OPCODES = {
    IROpcode.CONST,
    IROpcode.CONST_STR,
    IROpcode.MOVE,
    IROpcode.INVERT,
    IROpcode.ADD,
    IROpcode.MINIMUM,
    IROpcode.MAXIMUM,
    IROpcode.COMPARE,
    IROpcode.LOAD,
}


def _width(type_name: IRType) -> TernaryWidth:
    return (
        TernaryWidth.TRIT
        if type_name is IRType.TRIT
        else TernaryWidth.TRYTE
    )


def to_ir(ssa_fn: SSAFunction) -> IRFunction:
    """Converts an SSAFunction back into standard IRFunction (out-of-SSA)."""
    ssa_val_to_reg: Dict[str, int] = {}
    ir_registers: List[IRRegister] = []

    def get_reg_index(val: SSAValue) -> int:
        if val.name not in ssa_val_to_reg:
            idx = len(ir_registers)
            ssa_val_to_reg[val.name] = idx
            ir_registers.append(IRRegister(index=idx, type=val.type))
        return ssa_val_to_reg[val.name]

    ir_params: List[IRParameter] = []
    for param in ssa_fn.parameters:
        reg_idx = get_reg_index(param.value)
        ir_params.append(
            IRParameter(
                name=param.value.name,
                register=reg_idx,
                type=param.value.type,
            )
        )

    pending_phi_moves: Dict[str, List[IRInstruction]] = {}
    for block in ssa_fn.blocks:
        for phi in block.phis:
            target_reg = get_reg_index(phi.target)
            for pred_name, op_val in phi.operands.items():
                src_reg = get_reg_index(op_val)
                move_inst = IRInstruction(
                    opcode=IROpcode.MOVE,
                    result=target_reg,
                    operands=(src_reg,),
                    location=phi.location,
                )
                pending_phi_moves.setdefault(pred_name, []).append(move_inst)

    ir_blocks: List[IRBasicBlock] = []
    entry_blocks = [b for b in ssa_fn.blocks if b.name == "entry"]
    other_blocks = [b for b in ssa_fn.blocks if b.name != "entry"]
    for block in entry_blocks + other_blocks:

        instructions: List[IRInstruction] = []

        for ssa_inst in block.instructions:
            res_reg = get_reg_index(ssa_inst.result) if ssa_inst.result else None
            op_regs = tuple(get_reg_index(op) for op in ssa_inst.operands)

            imm_val: int | None = None
            static_str: str | None = None
            callee_val: str | None = None

            if ssa_inst.opcode is IROpcode.CONST_STR:
                static_str = str(ssa_inst.immediate) if ssa_inst.immediate is not None else None
            elif ssa_inst.opcode is IROpcode.CALL:
                callee_val = str(ssa_inst.immediate) if ssa_inst.immediate is not None else None
            else:
                if isinstance(ssa_inst.immediate, int):
                    imm_val = ssa_inst.immediate

            instructions.append(
                IRInstruction(
                    opcode=ssa_inst.opcode,
                    result=res_reg,
                    operands=op_regs,
                    immediate=imm_val,
                    static_string=static_str,
                    callee=callee_val,
                    targets=ssa_inst.targets,
                    memory=ssa_inst.memory,
                    initialization=ssa_inst.initialization,
                    location=ssa_inst.location,
                )
            )

        if block.name in pending_phi_moves and pending_phi_moves[block.name]:
            moves = pending_phi_moves[block.name]
            if instructions and instructions[-1].is_terminator:
                terminator = instructions.pop()
                instructions.extend(moves)
                instructions.append(terminator)
            else:
                instructions.extend(moves)

        ir_blocks.append(
            IRBasicBlock(
                name=block.name,
                instructions=tuple(instructions),
            )
        )

    ret_type = getattr(ssa_fn, "return_type", IRType.TRYTE)


    return IRFunction(
        name=ssa_fn.name,
        parameters=tuple(ir_params),
        return_type=ret_type,
        registers=tuple(ir_registers),
        blocks=tuple(ir_blocks),
        memory_objects=ssa_fn.memory_objects,
    )


# -----------------------------------------------------------------------------
# Milestone 0.81: Sparse Constant Propagation (SSA)
# -----------------------------------------------------------------------------

def run_ssa_constant_propagation(ssa_fn: SSAFunction) -> SSAFunction:
    """Propagates constants across SSA assignments, phi nodes, and branches."""
    known_constants: Dict[str, int] = {}
    val_by_name: Dict[str, SSAValue] = {}

    for val in ssa_fn.values:
        val_by_name[val.name] = val

    def evaluate_inst(
        opcode: IROpcode, operands: Tuple[int, ...], res_type: IRType, op0_type: IRType
    ) -> int | None:
        try:
            if opcode is IROpcode.MOVE:
                return operands[0]
            elif opcode is IROpcode.INVERT:
                return invert(operands[0], _width(res_type))
            elif opcode is IROpcode.ADD:
                return add(operands[0], operands[1], _width(res_type))
            elif opcode is IROpcode.MINIMUM:
                return tritwise_min(operands[0], operands[1], _width(res_type))
            elif opcode is IROpcode.MAXIMUM:
                return tritwise_max(operands[0], operands[1], _width(res_type))
            elif opcode is IROpcode.COMPARE:
                return compare(operands[0], operands[1], _width(op0_type))
        except TernaryRangeError:
            return None
        return None

    changed = True
    while changed:
        changed = False

        for block in ssa_fn.blocks:
            for phi in block.phis:
                if phi.target.name in known_constants:
                    continue
                vals = [
                    known_constants[op.name]
                    for op in phi.operands.values()
                    if op.name in known_constants
                ]
                if vals and len(vals) == len(phi.operands) and len(set(vals)) == 1:
                    known_constants[phi.target.name] = vals[0]
                    changed = True

            for inst in block.instructions:
                if inst.result is None or inst.result.name in known_constants:
                    continue

                if inst.opcode is IROpcode.CONST and isinstance(inst.immediate, int):
                    known_constants[inst.result.name] = inst.immediate
                    changed = True
                elif inst.opcode in _FOLDABLE_OPCODES:
                    op_vals: List[int] = []
                    all_const = True
                    for op in inst.operands:
                        if op.name in known_constants:
                            op_vals.append(known_constants[op.name])
                        else:
                            all_const = False
                            break
                    if all_const and op_vals:
                        op0_type = inst.operands[0].type if inst.operands else IRType.TRYTE
                        folded = evaluate_inst(
                            inst.opcode, tuple(op_vals), inst.result.type, op0_type
                        )
                        if folded is not None:
                            known_constants[inst.result.name] = folded
                            changed = True

    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        new_instructions: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst.opcode is IROpcode.BRANCH3 and inst.operands:
                cond_val = inst.operands[0]
                if cond_val.name in known_constants:
                    c = known_constants[cond_val.name]
                    target = (
                        inst.targets[0]
                        if c < 0
                        else (inst.targets[1] if c == 0 else inst.targets[2])
                    )
                    new_instructions.append(
                        SSAInstruction(
                            opcode=IROpcode.JUMP,
                            targets=(target,),
                            location=inst.location,
                        )
                    )
                    continue

            if (
                inst.result is not None
                and inst.result.name in known_constants
                and inst.opcode not in {IROpcode.CONST, IROpcode.CONST_STR}
            ):
                new_instructions.append(
                    SSAInstruction(
                        opcode=IROpcode.CONST,
                        result=inst.result,
                        immediate=known_constants[inst.result.name],
                        location=inst.location,
                    )
                )
            else:
                new_instructions.append(inst)

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=list(block.phis),
                instructions=new_instructions,
            )
        )

    return SSAFunction(
        name=ssa_fn.name,
        parameters=ssa_fn.parameters,
        blocks=tuple(new_blocks),
        values=ssa_fn.values,
        memory_objects=ssa_fn.memory_objects,
        return_type=ssa_fn.return_type,
    )


# -----------------------------------------------------------------------------
# Milestone 0.82: Copy Propagation
# -----------------------------------------------------------------------------

def run_ssa_copy_propagation(ssa_fn: SSAFunction) -> SSAFunction:
    """Propagates aliases (MOVEs and single-value phis) across SSA form."""
    copies: Dict[str, SSAValue] = {}

    def get_canonical(val: SSAValue) -> SSAValue:
        curr = val
        visited: Set[str] = set()
        while curr.name in copies and curr.name not in visited:
            visited.add(curr.name)
            curr = copies[curr.name]
        return curr

    changed = True
    while changed:
        changed = False
        for block in ssa_fn.blocks:
            for phi in block.phis:
                if phi.target.name in copies:
                    continue
                resolved_ops = [
                    get_canonical(op).name for op in phi.operands.values()
                ]
                if resolved_ops and len(set(resolved_ops)) == 1:
                    copies[phi.target.name] = get_canonical(next(iter(phi.operands.values())))
                    changed = True

            for inst in block.instructions:
                if inst.opcode is IROpcode.MOVE and inst.result and inst.operands:
                    if inst.result.name not in copies:
                        canonical_src = get_canonical(inst.operands[0])
                        if canonical_src.name != inst.result.name and canonical_src.type == inst.result.type:
                            copies[inst.result.name] = canonical_src
                            changed = True


    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        new_phis: List[SSAPhiNode] = []
        for phi in block.phis:
            if phi.target.name in copies:
                continue
            updated_ops = {
                pred: get_canonical(val) for pred, val in phi.operands.items()
            }
            new_phis.append(
                SSAPhiNode(
                    target=phi.target,
                    original_register=phi.original_register,
                    operands=updated_ops,
                    location=phi.location,
                )
            )

        new_instructions: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst.result and inst.result.name in copies:
                continue
            updated_operands = tuple(get_canonical(op) for op in inst.operands)
            new_instructions.append(
                SSAInstruction(
                    opcode=inst.opcode,
                    result=inst.result,
                    operands=updated_operands,
                    immediate=inst.immediate,
                    targets=inst.targets,
                    memory=inst.memory,
                    initialization=inst.initialization,
                    location=inst.location,
                )
            )

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=new_phis,
                instructions=new_instructions,
            )
        )

    return SSAFunction(
        name=ssa_fn.name,
        parameters=ssa_fn.parameters,
        blocks=tuple(new_blocks),
        values=ssa_fn.values,
        memory_objects=ssa_fn.memory_objects,
        return_type=ssa_fn.return_type,
    )



# -----------------------------------------------------------------------------
# Milestone 0.83: Dead Code Elimination
# -----------------------------------------------------------------------------

def run_ssa_dead_code_elimination(ssa_fn: SSAFunction) -> SSAFunction:
    """Removes unused instructions and dead phi nodes without side effects."""
    blocks = list(ssa_fn.blocks)
    changed = True

    while changed:
        changed = False
        used: Set[str] = set()
        for block in blocks:
            for phi in block.phis:
                for val in phi.operands.values():
                    used.add(val.name)
            for inst in block.instructions:
                for op in inst.operands:
                    used.add(op.name)

        updated_blocks: List[SSABlock] = []
        for block in blocks:
            new_phis = [phi for phi in block.phis if phi.target.name in used]
            if len(new_phis) != len(block.phis):
                changed = True

            new_instructions: List[SSAInstruction] = []
            for inst in block.instructions:
                if (
                    inst.result is not None
                    and inst.result.name not in used
                    and inst.opcode in _PURE_REMOVABLE_OPCODES
                ):
                    changed = True
                else:
                    new_instructions.append(inst)

            updated_blocks.append(
                SSABlock(
                    name=block.name,
                    phis=new_phis,
                    instructions=new_instructions,
                )
            )

        blocks = updated_blocks

    return SSAFunction(
        name=ssa_fn.name,
        parameters=ssa_fn.parameters,
        blocks=tuple(blocks),
        values=ssa_fn.values,
        memory_objects=ssa_fn.memory_objects,
        return_type=ssa_fn.return_type,
    )


# -----------------------------------------------------------------------------
# Milestone 0.84: Common Subexpression Elimination (CSE)
# -----------------------------------------------------------------------------

def run_ssa_cse(ssa_fn: SSAFunction) -> SSAFunction:
    """Eliminates common subexpressions in SSA form using dominator tree traversal."""
    ir_temp = to_ir(ssa_fn)
    cfg = ControlFlowGraph.build(ir_temp)
    dom_tree = DominatorTree.build(cfg)

    ssa_block_dict = {b.name: b for b in ssa_fn.blocks}
    expr_table: Dict[Tuple, SSAValue] = {}
    replacements: Dict[str, SSAValue] = {}

    def visit(block_name: str) -> None:
        block = ssa_block_dict[block_name]
        saved_keys: List[Tuple] = []

        for inst in block.instructions:
            if (
                inst.result is not None
                and inst.opcode in _PURE_REMOVABLE_OPCODES
                and inst.opcode not in {IROpcode.CONST, IROpcode.CONST_STR, IROpcode.MOVE}
            ):
                key = (
                    inst.opcode,
                    tuple(op.name for op in inst.operands),
                    inst.immediate,
                    inst.memory,
                    inst.result.type,
                )
                if key in expr_table:
                    existing = expr_table[key]
                    replacements[inst.result.name] = existing
                else:
                    expr_table[key] = inst.result
                    saved_keys.append(key)

        for child in dom_tree.children.get(block_name, set()):
            visit(child)

        for key in saved_keys:
            del expr_table[key]

    if ssa_fn.blocks:
        visit(cfg.entry_name)

    if not replacements:
        return ssa_fn

    def get_rep(val: SSAValue) -> SSAValue:
        curr = val
        visited: Set[str] = set()
        while curr.name in replacements and curr.name not in visited:
            visited.add(curr.name)
            curr = replacements[curr.name]
        return curr

    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        new_phis: List[SSAPhiNode] = []
        for phi in block.phis:
            if phi.target.name in replacements:
                continue
            new_phis.append(
                SSAPhiNode(
                    target=phi.target,
                    original_register=phi.original_register,
                    operands={p: get_rep(v) for p, v in phi.operands.items()},
                    location=phi.location,
                )
            )

        new_instructions: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst.result and inst.result.name in replacements:
                rep_src = get_rep(replacements[inst.result.name])
                new_instructions.append(
                    SSAInstruction(
                        opcode=IROpcode.MOVE,
                        result=inst.result,
                        operands=(rep_src,),
                        location=inst.location,
                    )
                )
            else:
                updated_ops = tuple(get_rep(op) for op in inst.operands)
                new_instructions.append(
                    SSAInstruction(
                        opcode=inst.opcode,
                        result=inst.result,
                        operands=updated_ops,
                        immediate=inst.immediate,
                        targets=inst.targets,
                        memory=inst.memory,
                        initialization=inst.initialization,
                        location=inst.location,
                    )
                )

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=new_phis,
                instructions=new_instructions,
            )
        )

    return run_ssa_copy_propagation(replace(ssa_fn, blocks=tuple(new_blocks)))


# -----------------------------------------------------------------------------
# Milestone 0.85: Peephole SSA
# -----------------------------------------------------------------------------

def run_ssa_peephole(ssa_fn: SSAFunction) -> SSAFunction:
    """Applies local SSA algebraic and identity simplifications."""
    def_inst_map: Dict[str, SSAInstruction] = {}
    for block in ssa_fn.blocks:
        for inst in block.instructions:
            if inst.result:
                def_inst_map[inst.result.name] = inst

    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        new_phis: List[SSAPhiNode] = []
        for phi in block.phis:
            ops = list(phi.operands.values())
            if ops and all(op.name == ops[0].name for op in ops):
                new_phis.append(phi)
            else:
                new_phis.append(phi)

        new_instructions: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst.opcode is IROpcode.MOVE and inst.result and inst.operands:
                if inst.result.name == inst.operands[0].name:
                    continue

            if inst.opcode is IROpcode.ADD and inst.result and len(inst.operands) == 2:
                op0, op1 = inst.operands[0], inst.operands[1]
                if op0.name in def_inst_map:
                    def0 = def_inst_map[op0.name]
                    if def0.opcode is IROpcode.CONST and def0.immediate == 0:
                        new_instructions.append(
                            SSAInstruction(
                                opcode=IROpcode.MOVE,
                                result=inst.result,
                                operands=(op1,),
                                location=inst.location,
                            )
                        )
                        continue
                if op1.name in def_inst_map:
                    def1 = def_inst_map[op1.name]
                    if def1.opcode is IROpcode.CONST and def1.immediate == 0:
                        new_instructions.append(
                            SSAInstruction(
                                opcode=IROpcode.MOVE,
                                result=inst.result,
                                operands=(op0,),
                                location=inst.location,
                            )
                        )
                        continue

            if inst.opcode is IROpcode.MINIMUM and inst.result and len(inst.operands) == 2:
                if inst.operands[0].name == inst.operands[1].name:
                    new_instructions.append(
                        SSAInstruction(
                            opcode=IROpcode.MOVE,
                            result=inst.result,
                            operands=(inst.operands[0],),
                            location=inst.location,
                        )
                    )
                    continue

            if inst.opcode is IROpcode.MAXIMUM and inst.result and len(inst.operands) == 2:
                if inst.operands[0].name == inst.operands[1].name:
                    new_instructions.append(
                        SSAInstruction(
                            opcode=IROpcode.MOVE,
                            result=inst.result,
                            operands=(inst.operands[0],),
                            location=inst.location,
                        )
                    )
                    continue

            if inst.opcode is IROpcode.COMPARE and inst.result and len(inst.operands) == 2:
                if inst.operands[0].name == inst.operands[1].name:
                    new_instructions.append(
                        SSAInstruction(
                            opcode=IROpcode.CONST,
                            result=inst.result,
                            immediate=0,
                            location=inst.location,
                        )
                    )
                    continue

            if inst.opcode is IROpcode.INVERT and inst.result and len(inst.operands) == 1:
                op0 = inst.operands[0]
                if op0.name in def_inst_map:
                    def0 = def_inst_map[op0.name]
                    if def0.opcode is IROpcode.INVERT and def0.operands:
                        new_instructions.append(
                            SSAInstruction(
                                opcode=IROpcode.MOVE,
                                result=inst.result,
                                operands=(def0.operands[0],),
                                location=inst.location,
                            )
                        )
                        continue

            new_instructions.append(inst)

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=new_phis,
                instructions=new_instructions,
            )
        )

    return SSAFunction(
        name=ssa_fn.name,
        parameters=ssa_fn.parameters,
        blocks=tuple(new_blocks),
        values=ssa_fn.values,
        memory_objects=ssa_fn.memory_objects,
        return_type=ssa_fn.return_type,
    )



# -----------------------------------------------------------------------------
# Milestone 0.86: Global Value Numbering (GVN)
# -----------------------------------------------------------------------------

def run_ssa_gvn(ssa_fn: SSAFunction) -> Tuple[SSAFunction, int]:
    """Computes Global Value Numbers for SSA expressions and eliminates redundant computations."""
    ir_temp = to_ir(ssa_fn)
    cfg = ControlFlowGraph.build(ir_temp)
    dom_tree = DominatorTree.build(cfg)

    ssa_block_dict = {b.name: b for b in ssa_fn.blocks}
    value_table: Dict[Tuple, SSAValue] = {}
    replacements: Dict[str, SSAValue] = {}
    eliminated_count = 0
    eligible_opcodes = _PURE_REMOVABLE_OPCODES - {
        IROpcode.LOAD,
        IROpcode.CONST,
        IROpcode.CONST_STR,
        IROpcode.MOVE,
    }

    def value_key(value: SSAValue) -> int | str:
        if value.original_register is not None:
            return value.original_register
        return value.name

    def visit(block_name: str) -> None:
        nonlocal eliminated_count
        block = ssa_block_dict[block_name]
        saved_keys: List[Tuple] = []

        for inst in block.instructions:
            if (
                inst.result is not None
                and inst.opcode in eligible_opcodes
            ):
                op_keys = tuple(
                    value_key(replacements.get(op.name, op))
                    for op in inst.operands
                )
                key = (
                    inst.opcode,
                    op_keys,
                    inst.immediate,
                    inst.memory,
                    inst.targets,
                    inst.initialization,
                    inst.result.type,
                )

                if key in value_table:
                    canonical_val = value_table[key]
                    replacements[inst.result.name] = canonical_val
                    eliminated_count += 1
                else:
                    value_table[key] = inst.result
                    saved_keys.append(key)

        for child in dom_tree.children.get(block_name, set()):
            visit(child)

        for key in saved_keys:
            del value_table[key]

    if ssa_fn.blocks:
        visit(cfg.entry_name)

    if not replacements:
        return ssa_fn, 0

    def get_rep(val: SSAValue) -> SSAValue:
        curr = val
        visited: Set[str] = set()
        while curr.name in replacements and curr.name not in visited:
            visited.add(curr.name)
            curr = replacements[curr.name]
        return curr

    removed_count = 0
    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        new_phis: List[SSAPhiNode] = []
        for phi in block.phis:
            new_phis.append(
                SSAPhiNode(
                    target=phi.target,
                    original_register=phi.original_register,
                    operands={p: get_rep(v) for p, v in phi.operands.items()},
                    location=phi.location,
                )
            )

        new_instructions: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst.result and inst.result.name in replacements:
                removed_count += 1
                continue
            updated_ops = tuple(get_rep(op) for op in inst.operands)
            new_instructions.append(
                SSAInstruction(
                    opcode=inst.opcode,
                    result=inst.result,
                    operands=updated_ops,
                    immediate=inst.immediate,
                    targets=inst.targets,
                    memory=inst.memory,
                    initialization=inst.initialization,
                    location=inst.location,
                )
            )

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=new_phis,
                instructions=new_instructions,
            )
        )

    if removed_count == 0:
        return ssa_fn, 0

    transformed = replace(ssa_fn, blocks=tuple(new_blocks))
    opt_fn = run_ssa_copy_propagation(transformed)
    return opt_fn, removed_count


# -----------------------------------------------------------------------------
# Milestone 0.87: Loop Invariant Code Motion (LICM)
# -----------------------------------------------------------------------------

def run_ssa_licm(ssa_fn: SSAFunction) -> Tuple[SSAFunction, int]:
    """Hoists pure loop-invariant computations out of loops into pre-headers."""
    ir_temp = to_ir(ssa_fn)
    cfg = ControlFlowGraph.build(ir_temp)
    dom_tree = DominatorTree.build(cfg)

    back_edges: List[Tuple[str, str]] = []
    for node_name, node in cfg.nodes.items():
        for succ in node.successors:
            if dom_tree.dominates(succ, node_name):
                back_edges.append((node_name, succ))

    if not back_edges:
        return ssa_fn, 0

    hoisted_count = 0
    ssa_block_dict = {b.name: b for b in ssa_fn.blocks}

    for tail_name, head_name in back_edges:
        loop_blocks: Set[str] = {head_name, tail_name}
        worklist = [tail_name]
        while worklist:
            curr = worklist.pop()
            if curr in cfg.nodes:
                for pred in cfg.nodes[curr].predecessors:
                    if pred not in loop_blocks:
                        loop_blocks.add(pred)
                        worklist.append(pred)

        defined_in_loop = {
            inst.result.name
            for b_name in loop_blocks
            if b_name in ssa_block_dict
            for inst in ssa_block_dict[b_name].instructions
            if inst.result is not None
        }

        invariant_defs: Set[str] = set()
        hoistable_insts: List[Tuple[str, SSAInstruction]] = []

        changed = True
        while changed:
            changed = False
            for b_name in sorted(loop_blocks):
                block = ssa_block_dict[b_name]
                for inst in block.instructions:
                    if (
                        inst.result is not None
                        and inst.result.name not in invariant_defs
                        and inst.opcode in _PURE_REMOVABLE_OPCODES
                        and inst.opcode not in {IROpcode.JUMP, IROpcode.BRANCH3, IROpcode.CALL, IROpcode.STORE, IROpcode.LOAD}

                    ):
                        if all(
                            (op.name not in defined_in_loop or op.name in invariant_defs)
                            for op in inst.operands
                        ):
                            invariant_defs.add(inst.result.name)
                            hoistable_insts.append((b_name, inst))
                            changed = True

        if not hoistable_insts:
            continue

        pre_header_candidates = [
            p for p in cfg.nodes[head_name].predecessors if p not in loop_blocks
        ] if head_name in cfg.nodes else []

        target_pre_header = pre_header_candidates[0] if pre_header_candidates else ssa_fn.blocks[0].name

        hoist_inst_set = {inst for _, inst in hoistable_insts}
        hoisted_count += len(hoist_inst_set)

        new_blocks: List[SSABlock] = []
        for block in ssa_fn.blocks:
            if block.name == target_pre_header:
                insts = [i for i in block.instructions if i not in hoist_inst_set]
                hoist_copies = [inst for _, inst in hoistable_insts]
                if insts and insts[-1].opcode in {IROpcode.JUMP, IROpcode.BRANCH3, IROpcode.RETURN}:
                    term = insts.pop()
                    insts.extend(hoist_copies)
                    insts.append(term)
                else:
                    insts.extend(hoist_copies)
                new_blocks.append(SSABlock(name=block.name, phis=list(block.phis), instructions=insts))
            else:
                insts = [i for i in block.instructions if i not in hoist_inst_set]
                new_blocks.append(SSABlock(name=block.name, phis=list(block.phis), instructions=insts))

        ssa_fn = SSAFunction(
            name=ssa_fn.name,
            parameters=ssa_fn.parameters,
            blocks=tuple(new_blocks),
            values=ssa_fn.values,
            memory_objects=ssa_fn.memory_objects,
            return_type=ssa_fn.return_type,
        )

    return ssa_fn, hoisted_count


# -----------------------------------------------------------------------------
# Milestone 0.88: Strength Reduction
# -----------------------------------------------------------------------------

def run_ssa_strength_reduction(ssa_fn: SSAFunction) -> Tuple[SSAFunction, int]:
    """Reduces operational complexity (e.g. repeated addition, algebraic reductions)."""
    def_inst_map: Dict[str, SSAInstruction] = {}
    for block in ssa_fn.blocks:
        for inst in block.instructions:
            if inst.result:
                def_inst_map[inst.result.name] = inst

    reductions_count = 0
    new_blocks: List[SSABlock] = []

    for block in ssa_fn.blocks:
        new_instructions: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst.opcode is IROpcode.ADD and inst.result and len(inst.operands) == 2:
                op0, op1 = inst.operands[0], inst.operands[1]
                if op0.name == op1.name or (op0.original_register is not None and op0.original_register == op1.original_register):
                    reductions_count += 1


            if inst.opcode is IROpcode.INVERT and inst.result and len(inst.operands) == 1:
                op0 = inst.operands[0]
                def0 = def_inst_map.get(op0.name)
                while def0 and def0.opcode is IROpcode.MOVE and def0.operands:
                    def0 = def_inst_map.get(def0.operands[0].name)
                if def0 and def0.opcode is IROpcode.INVERT and def0.operands:
                    reductions_count += 1
                    new_instructions.append(
                        SSAInstruction(
                            opcode=IROpcode.MOVE,
                            result=inst.result,
                            operands=(def0.operands[0],),
                            location=inst.location,
                        )
                    )
                    continue


            new_instructions.append(inst)

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=list(block.phis),
                instructions=new_instructions,
            )
        )

    return SSAFunction(
        name=ssa_fn.name,
        parameters=ssa_fn.parameters,
        blocks=tuple(new_blocks),
        values=ssa_fn.values,
        memory_objects=ssa_fn.memory_objects,
        return_type=ssa_fn.return_type,
    ), reductions_count


# -----------------------------------------------------------------------------
# Milestone 0.89: Sparse Conditional Constant Propagation (SCCP)
# -----------------------------------------------------------------------------

def run_ssa_sccp(ssa_fn: SSAFunction) -> Tuple[SSAFunction, int, int]:
    """Sparse Conditional Constant Propagation using dual CFG and SSA edge tracking."""
    ir_temp = to_ir(ssa_fn)
    cfg = ControlFlowGraph.build(ir_temp)

    known_constants: Dict[str, int] = {}
    executable_blocks: Set[str] = {cfg.entry_name}
    executable_edges: Set[Tuple[str, str]] = set()

    cfg_worklist: List[Tuple[str, str]] = []
    if cfg.entry_name in cfg.nodes:
        for succ in sorted(cfg.nodes[cfg.entry_name].successors):
            cfg_worklist.append((cfg.entry_name, succ))

    expressions_folded = 0
    branches_removed = 0

    changed = True
    while changed or cfg_worklist:
        changed = False

        while cfg_worklist:
            u, v = cfg_worklist.pop(0)
            if (u, v) not in executable_edges:
                executable_edges.add((u, v))
                first_visit = v not in executable_blocks
                executable_blocks.add(v)

                if first_visit and v in cfg.nodes:
                    for succ in sorted(cfg.nodes[v].successors):
                        cfg_worklist.append((v, succ))

        for block in ssa_fn.blocks:
            if block.name not in executable_blocks:
                continue

            for phi in block.phis:
                if phi.target.name in known_constants:
                    continue
                incoming_vals = [
                    known_constants[val.name]
                    for pred, val in phi.operands.items()
                    if (pred, block.name) in executable_edges and val.name in known_constants
                ]
                if incoming_vals and len(set(incoming_vals)) == 1:
                    known_constants[phi.target.name] = incoming_vals[0]
                    changed = True

            for inst in block.instructions:
                if inst.result is not None and inst.result.name not in known_constants:
                    if inst.opcode is IROpcode.CONST and isinstance(inst.immediate, int):
                        known_constants[inst.result.name] = inst.immediate
                        changed = True
                    elif inst.opcode in _FOLDABLE_OPCODES:
                        op_vals = [
                            known_constants[op.name]
                            for op in inst.operands
                            if op.name in known_constants
                        ]
                        if len(op_vals) == len(inst.operands) and op_vals:
                            try:
                                res_type = inst.result.type
                                op0_type = inst.operands[0].type if inst.operands else IRType.TRYTE
                                folded = None
                                if inst.opcode is IROpcode.MOVE:
                                    folded = op_vals[0]
                                elif inst.opcode is IROpcode.INVERT:
                                    folded = invert(op_vals[0], _width(res_type))
                                elif inst.opcode is IROpcode.ADD:
                                    folded = add(op_vals[0], op_vals[1], _width(res_type))
                                elif inst.opcode is IROpcode.MINIMUM:
                                    folded = tritwise_min(op_vals[0], op_vals[1], _width(res_type))
                                elif inst.opcode is IROpcode.MAXIMUM:
                                    folded = tritwise_max(op_vals[0], op_vals[1], _width(res_type))
                                elif inst.opcode is IROpcode.COMPARE:
                                    folded = compare(op_vals[0], op_vals[1], _width(op0_type))

                                if folded is not None:
                                    known_constants[inst.result.name] = folded
                                    changed = True
                            except TernaryRangeError:
                                pass

    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        if block.name not in executable_blocks:
            branches_removed += 1
            continue

        new_instructions: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst.opcode is IROpcode.BRANCH3 and inst.operands:
                cond_val = inst.operands[0]
                if cond_val.name in known_constants:
                    c = known_constants[cond_val.name]
                    target = (
                        inst.targets[0]
                        if c < 0
                        else (inst.targets[1] if c == 0 else inst.targets[2])
                    )
                    new_instructions.append(
                        SSAInstruction(
                            opcode=IROpcode.JUMP,
                            targets=(target,),
                            location=inst.location,
                        )
                    )
                    branches_removed += 1
                    continue

            if (
                inst.result is not None
                and inst.result.name in known_constants
                and inst.opcode not in {IROpcode.CONST, IROpcode.CONST_STR}
            ):
                new_instructions.append(
                    SSAInstruction(
                        opcode=IROpcode.CONST,
                        result=inst.result,
                        immediate=known_constants[inst.result.name],
                        location=inst.location,
                    )
                )
                expressions_folded += 1
            else:
                new_instructions.append(inst)

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=list(block.phis),
                instructions=new_instructions,
            )
        )

    return SSAFunction(
        name=ssa_fn.name,
        parameters=ssa_fn.parameters,
        blocks=tuple(new_blocks),
        values=ssa_fn.values,
        memory_objects=ssa_fn.memory_objects,
        return_type=ssa_fn.return_type,
    ), expressions_folded, branches_removed


# -----------------------------------------------------------------------------
# Milestone 0.91: Aggressive Dead Code Elimination (ADCE)
# -----------------------------------------------------------------------------

def run_ssa_adce(ssa_fn: SSAFunction) -> Tuple[SSAFunction, int]:
    """Mark-and-sweep Aggressive Dead Code Elimination (ADCE) for SSA form."""
    live_values: Set[str] = set()
    live_instructions: Set[SSAInstruction] = set()
    worklist: List[SSAInstruction] = []

    # Map SSA values to defining instructions/phis
    def_map: Dict[str, SSAInstruction] = {}
    phi_def_map: Dict[str, SSAPhiNode] = {}
    for block in ssa_fn.blocks:
        for phi in block.phis:
            phi_def_map[phi.target.name] = phi
        for inst in block.instructions:
            if inst.result:
                def_map[inst.result.name] = inst

    # Root marking: Control flow, side-effecting operations (STORE, CALL, RETURN, etc.)
    for block in ssa_fn.blocks:
        for inst in block.instructions:
            if inst.opcode in {IROpcode.STORE, IROpcode.CALL, IROpcode.RETURN, IROpcode.JUMP, IROpcode.BRANCH3}:
                live_instructions.add(inst)
                worklist.append(inst)

    # Transitive marking phase
    while worklist:
        inst = worklist.pop()
        for op in inst.operands:
            if op.name not in live_values:
                live_values.add(op.name)
                if op.name in def_map:
                    parent_inst = def_map[op.name]
                    if parent_inst not in live_instructions:
                        live_instructions.add(parent_inst)
                        worklist.append(parent_inst)

    # Mark live Phis whose target is live
    live_phis: Set[SSAPhiNode] = set()
    for block in ssa_fn.blocks:
        for phi in block.phis:
            if phi.target.name in live_values:
                live_phis.add(phi)
                for op in phi.operands.values():
                    if op.name in def_map and def_map[op.name] not in live_instructions:
                        live_instructions.add(def_map[op.name])
                        worklist.append(def_map[op.name])

    # Sweep phase
    removed_count = 0
    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        filtered_phis = [phi for phi in block.phis if phi in live_phis or phi.target.name in live_values]
        filtered_insts: List[SSAInstruction] = []
        for inst in block.instructions:
            if inst in live_instructions or (inst.result and inst.result.name in live_values):
                filtered_insts.append(inst)
            else:
                removed_count += 1

        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=filtered_phis,
                instructions=filtered_insts,
            )
        )

    return SSAFunction(
        name=ssa_fn.name,
        parameters=ssa_fn.parameters,
        blocks=tuple(new_blocks),
        values=ssa_fn.values,
        memory_objects=ssa_fn.memory_objects,
        return_type=ssa_fn.return_type,
    ), removed_count


# -----------------------------------------------------------------------------
# Milestone 0.92: Dead Store Elimination (DSE)
# -----------------------------------------------------------------------------

def run_ssa_dse(ssa_fn: SSAFunction) -> Tuple[SSAFunction, int]:
    """Eliminates redundant STORE operations using Alias Analysis and Memory SSA."""
    ir_temp = to_ir(ssa_fn)
    cfg = ControlFlowGraph.build(ir_temp)
    dom_tree = DominatorTree.build(cfg)
    mem_ssa = MemorySSA.build(ssa_fn, cfg, dom_tree)

    dead_stores: Set[SSAInstruction] = set()
    known_consts: Dict[str, int] = {}
    for block in ssa_fn.blocks:
        for inst in block.instructions:
            if inst.opcode is IROpcode.CONST and inst.result and isinstance(inst.immediate, int):
                known_consts[inst.result.name] = inst.immediate

    for block in ssa_fn.blocks:
        last_store_per_cell: Dict[Tuple[int, int | str], SSAInstruction] = {}

        for inst in block.instructions:
            if inst.opcode is IROpcode.STORE and inst.operands:
                idx_op = inst.operands[0]
                idx_key = known_consts.get(idx_op.name, idx_op.original_register)
                cell_key = (inst.memory, idx_key)
                if cell_key in last_store_per_cell:
                    dead_stores.add(last_store_per_cell[cell_key])
                last_store_per_cell[cell_key] = inst

            elif inst.opcode is IROpcode.LOAD and inst.memory is not None:
                # Clear pending stores for aliased memory locations
                mem_idx = inst.memory
                to_clear = [
                    c for c in last_store_per_cell
                    if AliasAnalysis.may_alias(c[0], mem_idx)
                ]
                for c in to_clear:
                    del last_store_per_cell[c]
            elif inst.opcode is IROpcode.CALL:
                # Calls may observe any memory location
                last_store_per_cell.clear()


    if not dead_stores:
        return ssa_fn, 0

    new_blocks: List[SSABlock] = []
    for block in ssa_fn.blocks:
        filtered_insts = [inst for inst in block.instructions if inst not in dead_stores]
        new_blocks.append(
            SSABlock(
                name=block.name,
                phis=list(block.phis),
                instructions=filtered_insts,
            )
        )

    return SSAFunction(
        name=ssa_fn.name,
        parameters=ssa_fn.parameters,
        blocks=tuple(new_blocks),
        values=ssa_fn.values,
        memory_objects=ssa_fn.memory_objects,
        return_type=ssa_fn.return_type,
    ), len(dead_stores)


# -----------------------------------------------------------------------------
# Milestone 0.90 & 0.95: Optimization Fixpoint Pipeline & Memory Pipeline
# -----------------------------------------------------------------------------

def run_fixpoint_pipeline(
    ssa_fn: SSAFunction, max_iterations: int = 10
) -> Tuple[SSAFunction, FixpointTelemetry]:
    """Iteratively executes optimization passes until reaching fixpoint or max iterations."""
    telemetry = FixpointTelemetry()
    curr_fn = ssa_fn

    for it in range(1, max_iterations + 1):
        telemetry.iterations = it
        changed = False

        # 1. GVN
        curr_fn, gvn_cnt = run_ssa_gvn(curr_fn)
        if gvn_cnt > 0:
            telemetry.expressions_eliminated += gvn_cnt
            changed = True

        # 2. Copy Propagation
        prev_blocks = curr_fn.blocks
        curr_fn = run_ssa_copy_propagation(curr_fn)
        if curr_fn.blocks != prev_blocks:
            changed = True

        # 3. DSE (Dead Store Elimination - Milestone 0.92)
        curr_fn, dse_cnt = run_ssa_dse(curr_fn)
        if dse_cnt > 0:
            changed = True

        # 4. DCE
        prev_blocks = curr_fn.blocks
        curr_fn = run_ssa_dead_code_elimination(curr_fn)
        if curr_fn.blocks != prev_blocks:
            changed = True

        # 5. ADCE (Aggressive DCE - Milestone 0.91)
        curr_fn, adce_cnt = run_ssa_adce(curr_fn)
        if adce_cnt > 0:
            changed = True

        # 6. LICM
        curr_fn, licm_cnt = run_ssa_licm(curr_fn)
        if licm_cnt > 0:
            telemetry.licm_moves += licm_cnt
            changed = True

        # 7. SCCP
        curr_fn, sccp_expr_cnt, sccp_br_cnt = run_ssa_sccp(curr_fn)
        if sccp_expr_cnt > 0 or sccp_br_cnt > 0:
            telemetry.expressions_eliminated += sccp_expr_cnt
            telemetry.branches_removed += sccp_br_cnt
            changed = True

        # 8. Strength Reduction
        curr_fn, sr_cnt = run_ssa_strength_reduction(curr_fn)
        if sr_cnt > 0:
            telemetry.strength_reductions += sr_cnt
            changed = True

        # 9. Peephole
        prev_blocks = curr_fn.blocks
        curr_fn = run_ssa_peephole(curr_fn)
        if curr_fn.blocks != prev_blocks:
            changed = True

        if not changed:
            telemetry.converged = True
            break
    else:
        telemetry.converged = False

    return curr_fn, telemetry
