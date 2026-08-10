"""SSA-to-IR lowering helpers for the internal optimizer."""

from __future__ import annotations

from typing import Dict, List

from ..cfg import ControlFlowGraph
from ..ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRMemoryObject,
    IRModule,
    IROpcode,
    IRParameter,
    IRRegister,
    IRType,
)
from ..ssa import SSAFunction, SSAInstruction, SSAPhiNode, SSAValue

def to_ir(ssa_fn: SSAFunction) -> IRFunction:
    """Converts an SSAFunction back into standard IRFunction (out-of-SSA)."""
    ssa_val_to_reg: Dict[str, int] = {}
    ir_registers: List[IRRegister] = []
    next_memory_index = (
        max((memory.index for memory in ssa_fn.memory_objects), default=-1) + 1
    )
    phi_memory: Dict[str, int] = {}
    additional_memory: List[IRMemoryObject] = []

    def get_reg_index(val: SSAValue) -> int:
        if val.name not in ssa_val_to_reg:
            idx = len(ir_registers)
            ssa_val_to_reg[val.name] = idx
            ir_registers.append(IRRegister(index=idx, type=val.type))
        return ssa_val_to_reg[val.name]

    def new_register(type_name: IRType) -> int:
        idx = len(ir_registers)
        ir_registers.append(IRRegister(index=idx, type=type_name))
        return idx

    def zero_index_instruction() -> tuple[IRInstruction, int]:
        idx = new_register(IRType.TRYTE)
        return IRInstruction(opcode=IROpcode.CONST, result=idx, immediate=0), idx

    def phi_memory_index(phi: SSAPhiNode) -> int:
        nonlocal next_memory_index
        if phi.target.name not in phi_memory:
            memory_index = next_memory_index
            next_memory_index += 1
            phi_memory[phi.target.name] = memory_index
            additional_memory.append(
                IRMemoryObject(
                    index=memory_index,
                    element_type=phi.target.type,
                    length=1,
                    mutable=True,
                    location=phi.location,
                )
            )
        return phi_memory[phi.target.name]

    phis_by_block: Dict[str, List[SSAPhiNode]] = {
        block.name: list(block.phis) for block in ssa_fn.blocks if block.phis
    }
    edge_phi_copies: Dict[tuple[str, str], List[tuple[SSAPhiNode, SSAValue]]] = {}
    for block in ssa_fn.blocks:
        for phi in block.phis:
            phi_memory_index(phi)
            for pred_name, op_val in phi.operands.items():
                edge_phi_copies.setdefault((pred_name, block.name), []).append(
                    (phi, op_val)
                )

    def edge_copy_instructions(pred_name: str, succ_name: str) -> List[IRInstruction]:
        copies = edge_phi_copies.get((pred_name, succ_name), [])
        if not copies:
            return []
        zero_inst, zero_reg = zero_index_instruction()
        instructions = [zero_inst]
        for phi, op_val in copies:
            instructions.append(
                IRInstruction(
                    opcode=IROpcode.STORE,
                    operands=(zero_reg, get_reg_index(op_val)),
                    memory=phi_memory_index(phi),
                    location=phi.location,
                )
            )
        return instructions

    used_block_names = {block.name for block in ssa_fn.blocks}

    def sanitize_block_part(value: str) -> str:
        return "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in value)

    def split_block_name(pred_name: str, succ_name: str) -> str:
        base = (
            f"ssa_edge_{sanitize_block_part(pred_name)}"
            f"_to_{sanitize_block_part(succ_name)}"
        )
        candidate = base
        suffix = 1
        while candidate in used_block_names:
            suffix += 1
            candidate = f"{base}_{suffix}"
        used_block_names.add(candidate)
        return candidate

    def convert_instruction(ssa_inst: SSAInstruction) -> IRInstruction:
        res_regs = tuple(get_reg_index(result) for result in ssa_inst.results)
        res_reg = res_regs[0] if len(res_regs) == 1 else None
        op_regs = tuple(get_reg_index(op) for op in ssa_inst.operands)

        imm_val: int | float | None = None
        static_str: str | None = None
        callee_val: str | None = None

        if ssa_inst.opcode is IROpcode.CONST_STR:
            static_str = str(ssa_inst.immediate) if ssa_inst.immediate is not None else None
        elif ssa_inst.opcode is IROpcode.CALL:
            callee_val = str(ssa_inst.immediate) if ssa_inst.immediate is not None else None
        elif isinstance(ssa_inst.immediate, (int, float)):
            imm_val = ssa_inst.immediate

        return IRInstruction(
            opcode=ssa_inst.opcode,
            result=res_reg,
            results=res_regs,
            operands=op_regs,
            immediate=imm_val,
            static_string=static_str,
            callee=callee_val,
            targets=ssa_inst.targets,
            memory=ssa_inst.memory,
            initialization=ssa_inst.initialization,
            location=ssa_inst.location,
        )

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

    ir_blocks: List[IRBasicBlock] = []
    entry_blocks = [b for b in ssa_fn.blocks if b.name == "entry"]
    other_blocks = [b for b in ssa_fn.blocks if b.name != "entry"]
    for block in entry_blocks + other_blocks:

        instructions: List[IRInstruction] = []
        for phi in phis_by_block.get(block.name, []):
            zero_inst, zero_reg = zero_index_instruction()
            instructions.append(zero_inst)
            instructions.append(
                IRInstruction(
                    opcode=IROpcode.LOAD,
                    result=get_reg_index(phi.target),
                    operands=(zero_reg,),
                    memory=phi_memory_index(phi),
                    location=phi.location,
                )
            )

        for ssa_inst in block.instructions:
            instructions.append(convert_instruction(ssa_inst))

        split_blocks: List[IRBasicBlock] = []
        if instructions and instructions[-1].is_terminator:
            terminator = instructions.pop()
            updated_targets: List[str] = []
            direct_edge_copies: List[IRInstruction] = []
            for target in terminator.targets:
                copies = edge_copy_instructions(block.name, target)
                if copies and len(terminator.targets) > 1:
                    edge_name = split_block_name(block.name, target)
                    updated_targets.append(edge_name)
                    split_blocks.append(
                        IRBasicBlock(
                            name=edge_name,
                            instructions=tuple(
                                copies
                                + [
                                    IRInstruction(
                                        opcode=IROpcode.JUMP,
                                        targets=(target,),
                                        location=terminator.location,
                                    )
                                ]
                            ),
                        )
                    )
                else:
                    direct_edge_copies.extend(copies)
                    updated_targets.append(target)

            instructions.extend(direct_edge_copies)
            instructions.append(
                IRInstruction(
                    opcode=terminator.opcode,
                    result=terminator.result,
                    results=terminator.results,
                    operands=terminator.operands,
                    immediate=terminator.immediate,
                    static_string=terminator.static_string,
                    callee=terminator.callee,
                    targets=tuple(updated_targets),
                    memory=terminator.memory,
                    initialization=terminator.initialization,
                    location=terminator.location,
                )
            )

        ir_blocks.append(
            IRBasicBlock(
                name=block.name,
                instructions=tuple(instructions),
            )
        )
        ir_blocks.extend(split_blocks)

    ret_type = getattr(ssa_fn, "return_type", IRType.TRYTE)


    return IRFunction(
        name=ssa_fn.name,
        parameters=tuple(ir_params),
        return_type=ret_type,
        registers=tuple(ir_registers),
        blocks=tuple(ir_blocks),
        memory_objects=ssa_fn.memory_objects + tuple(additional_memory),
        result_types=ssa_fn.result_types,
    )


def _cfg_from_ssa(ssa_fn: SSAFunction) -> ControlFlowGraph:
    """Build a CFG from SSA blocks without lowering Phi edges."""
    blocks: List[IRBasicBlock] = []
    for block in ssa_fn.blocks:
        instructions = tuple(
            IRInstruction(opcode=inst.opcode, targets=inst.targets)
            for inst in block.instructions
        )
        blocks.append(IRBasicBlock(name=block.name, instructions=instructions))
    return ControlFlowGraph.build(
        IRFunction(
            name=ssa_fn.name,
            parameters=(),
            return_type=ssa_fn.return_type,
            registers=(),
            blocks=tuple(blocks),
            memory_objects=ssa_fn.memory_objects,
            result_types=ssa_fn.result_types,
        )
    )
