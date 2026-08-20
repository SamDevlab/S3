"""Measured, semantics-preserving native codegen optimizations for M1.99."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .assembly import AssemblyBlock, AssemblyFunction, AssemblyInstruction, AssemblyOpcode, AssemblyProgram


@dataclass(frozen=True, slots=True)
class NativeOptimizationReport:
    input_instruction_count: int
    output_instruction_count: int
    removed_noop_moves: int

    @property
    def changed(self) -> bool:
        return self.removed_noop_moves > 0


def eliminate_redundant_noop_moves(program: AssemblyProgram) -> tuple[AssemblyProgram, NativeOptimizationReport]:
    """Remove only `TMOV rN, rN`; no memory/control-flow instruction is touched."""

    if not isinstance(program, AssemblyProgram) or not program.functions:
        raise ValueError("native optimization requires a non-empty AssemblyProgram")
    input_count = sum(len(block.instructions) for function in program.functions for block in function.blocks)
    removed = 0
    functions: list[AssemblyFunction] = []
    for function in program.functions:
        blocks: list[AssemblyBlock] = []
        for block in function.blocks:
            instructions: list[AssemblyInstruction] = []
            for instruction in block.instructions:
                if instruction.opcode is AssemblyOpcode.TMOV and len(instruction.registers) == 2 and instruction.registers[0] == instruction.registers[1]:
                    removed += 1
                    continue
                instructions.append(instruction)
            blocks.append(replace(block, instructions=tuple(instructions)))
        functions.append(replace(function, blocks=tuple(blocks)))
    optimized = replace(program, functions=tuple(functions))
    return optimized, NativeOptimizationReport(input_count, input_count - removed, removed)
