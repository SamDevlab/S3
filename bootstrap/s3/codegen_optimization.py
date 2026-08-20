"""Candidate analysis for semantics-preserving native codegen optimizations."""

from __future__ import annotations

from dataclasses import dataclass

from .assembly import AssemblyOpcode, AssemblyProgram


@dataclass(frozen=True, slots=True)
class NativeOptimizationReport:
    input_instruction_count: int
    output_instruction_count: int
    candidate_noop_moves: int

    @property
    def changed(self) -> bool:
        return self.candidate_noop_moves > 0


def analyze_redundant_noop_moves(program: AssemblyProgram) -> tuple[AssemblyProgram, NativeOptimizationReport]:
    """Analyze native self-move candidates without changing Assembly semantics."""

    if not isinstance(program, AssemblyProgram) or not program.functions:
        raise ValueError("native optimization requires a non-empty AssemblyProgram")
    input_count = sum(len(block.instructions) for function in program.functions for block in function.blocks)
    candidates = 0
    for function in program.functions:
        for block in function.blocks:
            for instruction in block.instructions:
                if instruction.opcode is AssemblyOpcode.TMOV and len(instruction.registers) == 2 and instruction.registers[0] == instruction.registers[1]:
                    candidates += 1
    return program, NativeOptimizationReport(input_count, input_count, candidates)


def eliminate_redundant_noop_moves(program: AssemblyProgram) -> tuple[AssemblyProgram, NativeOptimizationReport]:
    """Compatibility name for candidate analysis; Assembly is never rewritten."""

    return analyze_redundant_noop_moves(program)
