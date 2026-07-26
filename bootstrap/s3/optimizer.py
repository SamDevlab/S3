"""Verified conservative O0/O1 optimization pipeline for S3 IR."""

from __future__ import annotations

from dataclasses import replace
from enum import Enum

from .initialization import analyze_initialization
from .ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRModule,
    IROpcode,
    IRType,
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


def _successors(function: IRFunction) -> dict[str, tuple[str, ...]]:
    return {
        block.name: (
            block.instructions[-1].targets
            if block.instructions[-1].opcode
            in {IROpcode.JUMP, IROpcode.BRANCH3}
            else ()
        )
        for block in function.blocks
    }


def _reachable(function: IRFunction) -> set[str]:
    successors = _successors(function)
    result: set[str] = set()
    pending = ["entry"]
    while pending:
        name = pending.pop()
        if name in result:
            continue
        result.add(name)
        pending.extend(
            target for target in successors[name] if target not in result
        )
    return result


def _remove_unreachable(function: IRFunction) -> IRFunction:
    reachable = _reachable(function)
    return replace(
        function,
        blocks=tuple(
            block for block in function.blocks if block.name in reachable
        ),
    )


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
            value = invert(operands[0], _width(result_type))
        elif instruction.opcode is IROpcode.ADD:
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
        instruction.result
        for block in blocks
        for instruction in block.instructions
        if instruction.result is not None
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


_O1_PASSES = (
    _FunctionPass("remove-unreachable-blocks", _remove_unreachable),
    _FunctionPass("thread-empty-jumps", _thread_jumps),
    _FunctionPass("fold-constants", _fold_constants),
    _FunctionPass(
        "eliminate-dead-pure-instructions",
        _eliminate_dead_pure_instructions,
    ),
)


def _o1_passes() -> tuple[_FunctionPass, ...]:
    return _O1_PASSES


def optimize_ir(
    module: IRModule,
    level: OptimizationLevel | str = OptimizationLevel.O0,
) -> IRModule:
    selected = OptimizationLevel.parse(level)
    verify_ir(module)
    analyze_initialization(module)
    if selected is OptimizationLevel.O0:
        return module
    optimized = _PassManager(_O1_PASSES).run(module)
    verify_ir(optimized)
    analyze_initialization(optimized)
    return optimized
