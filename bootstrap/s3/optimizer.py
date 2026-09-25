"""Verified conservative O0/O1 optimization pipeline for S3 IR."""

from __future__ import annotations

from dataclasses import replace
from enum import Enum

from .cfg import ControlFlowGraph, remove_unreachable_blocks_cfg
from .initialization import analyze_initialization
from .ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRModule,
    IROpcode,
    IRType,
)
from .memory_effects import (
    function_has_alias_observable_memory,
    function_has_memory_effects,
)
from .passes import _FunctionPass, _PassManager
from .ternary import (
    TernaryRangeError,
    TernaryWidth,
    add,
    compare,
    invert,
    tritwise_max,
    tritwise_min,
)
from .verifier import verify_ir
from .numeric import checked_i64_add, checked_i64_neg, validate_f64


class OptimizationLevel(Enum):
    O0 = "O0"
    O1 = "O1"

    @classmethod
    def parse(cls, value: str | OptimizationLevel) -> OptimizationLevel:
        if isinstance(value, cls):
            return value
        normalized = value.upper()
        if not normalized.startswith("O"):
            normalized = f"O{normalized}"
        try:
            return cls(normalized)
        except ValueError as error:
            raise ValueError(f"unsupported optimization level {value!r}") from error


_FOLDABLE = {
    IROpcode.MOVE,
    IROpcode.INVERT,
    IROpcode.ADD,
    IROpcode.MINIMUM,
    IROpcode.MAXIMUM,
    IROpcode.COMPARE,
}

_REMOVABLE_WHEN_DEAD = {
    IROpcode.CONST,
    IROpcode.CONST_STR,
    IROpcode.MOVE,
    IROpcode.INVERT,
    IROpcode.MINIMUM,
    IROpcode.MAXIMUM,
    IROpcode.COMPARE,
}


def instruction_count(module: IRModule) -> int:
    return sum(
        len(block.instructions)
        for function in module.functions
        for block in function.blocks
    )





def _remove_unreachable(function: IRFunction) -> IRFunction:
    return remove_unreachable_blocks_cfg(function)


def _jump_redirects(function: IRFunction) -> dict[str, str]:
    return {
        block.name: block.instructions[0].targets[0]
        for block in function.blocks
        if block.name != "entry"
        and len(block.instructions) == 1
        and block.instructions[0].opcode is IROpcode.JUMP
    }


def _resolve_redirect(
    target: str,
    redirects: dict[str, str],
) -> str:
    current = target
    seen: set[str] = set()
    while current in redirects and current not in seen:
        seen.add(current)
        current = redirects[current]
    return target if current in seen else current


def _thread_jumps(function: IRFunction) -> IRFunction:
    redirects = _jump_redirects(function)
    if not redirects:
        return function
    blocks: list[IRBasicBlock] = []
    for block in function.blocks:
        instructions = list(block.instructions)
        terminator = instructions[-1]
        if terminator.opcode in {IROpcode.JUMP, IROpcode.BRANCH3}:
            targets = tuple(
                _resolve_redirect(target, redirects)
                for target in terminator.targets
            )
            if (
                terminator.opcode is IROpcode.BRANCH3
                and len(set(targets)) == 1
            ):
                instructions[-1] = replace(
                    terminator,
                    opcode=IROpcode.JUMP,
                    operands=(),
                    targets=(targets[0],),
                )
            elif (
                terminator.opcode is not IROpcode.BRANCH3
                or len(set(targets)) == len(targets)
            ):
                instructions[-1] = replace(terminator, targets=targets)
        blocks.append(replace(block, instructions=tuple(instructions)))
    return _remove_unreachable(replace(function, blocks=tuple(blocks)))


def _width(type_name: IRType) -> TernaryWidth:
    return (
        TernaryWidth.TRIT
        if type_name is IRType.TRIT
        else TernaryWidth.TRYTE
    )


def _fold_instruction(
    instruction: IRInstruction,
    constants: dict[int, int],
    register_types: dict[int, IRType],
) -> IRInstruction:
    if instruction.result is None or instruction.opcode not in _FOLDABLE:
        return instruction
    if not all(operand in constants for operand in instruction.operands):
        return instruction
    operands = tuple(constants[operand] for operand in instruction.operands)
    result_type = register_types[instruction.result]
    try:
        if instruction.opcode is IROpcode.MOVE:
            value = operands[0]
        elif instruction.opcode is IROpcode.INVERT:
            if result_type is IRType.I64:
                value = checked_i64_neg(operands[0])
            elif result_type is IRType.F64:
                value = validate_f64(-float(operands[0]))
            else:
                value = invert(operands[0], _width(result_type))
        elif instruction.opcode is IROpcode.ADD:
            if result_type is IRType.I64:
                value = checked_i64_add(operands[0], operands[1])
            elif result_type is IRType.F64:
                value = validate_f64(float(operands[0]) + float(operands[1]))
            else:
                value = add(operands[0], operands[1], _width(result_type))
        elif instruction.opcode is IROpcode.MINIMUM:
            value = tritwise_min(
                operands[0],
                operands[1],
                _width(result_type),
            )
        elif instruction.opcode is IROpcode.MAXIMUM:
            value = tritwise_max(
                operands[0],
                operands[1],
                _width(result_type),
            )
        else:
            source_type = register_types[instruction.operands[0]]
            value = compare(
                operands[0],
                operands[1],
                _width(source_type),
            )
    except TernaryRangeError:
        return instruction
    return IRInstruction(
        IROpcode.CONST,
        result=instruction.result,
        immediate=value,
        location=instruction.location,
    )


def _fold_constants(function: IRFunction) -> IRFunction:
    register_types = {
        register.index: register.type for register in function.registers
    }
    blocks: list[IRBasicBlock] = []
    for block in function.blocks:
        constants: dict[int, int] = {}
        instructions: list[IRInstruction] = []
        for instruction in block.instructions:
            folded = _fold_instruction(
                instruction,
                constants,
                register_types,
            )
            instructions.append(folded)
            if folded.result is not None:
                if (
                    folded.opcode is IROpcode.CONST
                    and folded.immediate is not None
                ):
                    constants[folded.result] = folded.immediate
                else:
                    constants.pop(folded.result, None)
        blocks.append(replace(block, instructions=tuple(instructions)))
    return replace(function, blocks=tuple(blocks))


def _eliminate_dead_pure_instructions(function: IRFunction) -> IRFunction:
    blocks = list(function.blocks)
    changed = True
    while changed:
        used = {
            operand
            for block in blocks
            for instruction in block.instructions
            for operand in instruction.operands
        }
        changed = False
        updated: list[IRBasicBlock] = []
        for block in blocks:
            instructions = tuple(
                instruction
                for instruction in block.instructions
                if not (
                    instruction.result is not None
                    and instruction.result not in used
                    and instruction.opcode in _REMOVABLE_WHEN_DEAD
                )
            )
            if len(instructions) != len(block.instructions):
                changed = True
            updated.append(replace(block, instructions=instructions))
        blocks = updated

    defined = {
        parameter.register for parameter in function.parameters
    } | {
        result
        for block in blocks
        for instruction in block.instructions
        for result in instruction.results
    }
    return replace(
        function,
        registers=tuple(
            register
            for register in function.registers
            if register.index in defined
        ),
        blocks=tuple(blocks),
    )


def _run_ssa_optimizations(
    function: IRFunction,
    *,
    preserve_memory_observability: bool = False,
) -> IRFunction:
    if (
        function_has_memory_effects(function)
        and function_has_alias_observable_memory(function)
    ):
        # Avoid broad SSA rewrites here: memory-observable loops can have
        # incomplete undef inputs in the current out-of-SSA representation.
        # This IR-level pass moves only proven immutable vector-length queries.
        from .ssa_optimizer.loops import hoist_readonly_vector_length_queries

        optimized, _hoisted = hoist_readonly_vector_length_queries(function)
        return optimized
    from .ssa import SSABuilder
    from .ssa_opt import run_fixpoint_pipeline

    ssa_fn = SSABuilder.build_function(function)
    disabled_passes = {"global_dse"} if preserve_memory_observability else set()
    ssa_fn, _telemetry = run_fixpoint_pipeline(ssa_fn, disabled_passes=disabled_passes)
    optimized = ssa_fn.to_ir()
    if _has_undefined_register_use(optimized):
        return function
    return optimized


def _has_undefined_register_use(function: IRFunction) -> bool:
    defined = {parameter.register for parameter in function.parameters}
    for block in function.blocks:
        for instruction in block.instructions:
            for operand in instruction.operands:
                if operand not in defined:
                    return True
            defined.update(instruction.results)
    return False


_O1_PASSES = (
    _FunctionPass("remove-unreachable-blocks", _remove_unreachable),
    _FunctionPass("thread-empty-jumps", _thread_jumps),
    _FunctionPass("ssa-optimizations", _run_ssa_optimizations),
    _FunctionPass("fold-constants", _fold_constants),
    _FunctionPass(
        "eliminate-dead-pure-instructions",
        _eliminate_dead_pure_instructions,
    ),
)


def _o1_passes(*, preserve_memory_observability: bool = False) -> tuple[_FunctionPass, ...]:
    if not preserve_memory_observability:
        return _O1_PASSES
    return (
        _O1_PASSES[0],
        _O1_PASSES[1],
        _FunctionPass(
            "ssa-optimizations-preserve-memory",
            lambda function: _run_ssa_optimizations(
                function,
                preserve_memory_observability=True,
            ),
        ),
        _O1_PASSES[3],
        _O1_PASSES[4],
    )


def optimize_ir(
    module: IRModule,
    level: OptimizationLevel | str = OptimizationLevel.O0,
    *,
    preserve_memory_observability: bool = False,
) -> IRModule:
    selected = OptimizationLevel.parse(level)
    verify_ir(module)
    analyze_initialization(module)
    if selected is OptimizationLevel.O0:
        return module
    optimized = _PassManager(
        _o1_passes(preserve_memory_observability=preserve_memory_observability)
    ).run(module)
    verify_ir(optimized)
    analyze_initialization(optimized)
    return optimized


def optimize_dynamic_ir(
    module: IRModule,
    level: OptimizationLevel | str = OptimizationLevel.O0,
) -> IRModule:
    """Run only transformations proven safe for dynamic/reference-bearing IR."""
    selected = OptimizationLevel.parse(level)
    verify_ir(module)
    analyze_initialization(module)
    if selected is OptimizationLevel.O0:
        return module

    from .ssa_optimizer.loops import hoist_readonly_vector_length_queries

    optimized = replace(
        module,
        functions=tuple(
            hoist_readonly_vector_length_queries(function)[0]
            for function in module.functions
        ),
    )
    verify_ir(optimized)
    analyze_initialization(optimized)
    return optimized
