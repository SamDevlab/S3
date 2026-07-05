"""Conservative, flow-sensitive initialization analysis for verified S3 IR."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
    S3Error,
)
from .ir import IRFunction, IRInstruction, IRModule, IROpcode, IRType
from .ternary import (
    TernaryRangeError,
    TernaryWidth,
    add,
    invert,
)
from .verifier import verify_ir


class InitializationState(Enum):
    UNINITIALIZED = "uninitialized"
    INITIALIZED = "initialized"
    MAYBE_INITIALIZED = "maybe-initialized"


class InitializationAnalysisError(S3Error):
    category = "initialization analysis error"
    diagnostic_category = DiagnosticCategory.VERIFICATION
    diagnostic_code = DiagnosticCode.INITIALIZATION_INVALID_ACCESS
    diagnostic_phase = DiagnosticPhase.INITIALIZATION


Cell = tuple[int, int]
StateMap = dict[Cell, InitializationState]


@dataclass(frozen=True, slots=True)
class FunctionInitialization:
    function: str
    constants: tuple[tuple[int, int], ...]
    entry_states: tuple[tuple[str, tuple[tuple[Cell, str], ...]], ...]
    exit_states: tuple[tuple[str, tuple[tuple[Cell, str], ...]], ...]


@dataclass(frozen=True, slots=True)
class InitializationReport:
    functions: tuple[FunctionInitialization, ...]


def _join_state(
    left: InitializationState,
    right: InitializationState,
) -> InitializationState:
    if left is right:
        return left
    return InitializationState.MAYBE_INITIALIZED


def _join_maps(states: list[StateMap]) -> StateMap:
    assert states
    result = dict(states[0])
    for state in states[1:]:
        for cell in result:
            result[cell] = _join_state(result[cell], state[cell])
    return result


def _width(type_name: IRType) -> TernaryWidth:
    return (
        TernaryWidth.TRIT
        if type_name is IRType.TRIT
        else TernaryWidth.TRYTE
    )


def _constant_values(function: IRFunction) -> dict[int, int]:
    register_types = {
        register.index: register.type for register in function.registers
    }
    constants: dict[int, int] = {}
    changed = True
    while changed:
        changed = False
        for instruction in function.instructions:
            if instruction.result is None or instruction.result in constants:
                continue
            value: int | None = None
            try:
                if (
                    instruction.opcode is IROpcode.CONST
                    and instruction.immediate is not None
                ):
                    value = instruction.immediate
                elif (
                    instruction.opcode is IROpcode.MOVE
                    and instruction.operands[0] in constants
                ):
                    value = constants[instruction.operands[0]]
                elif (
                    instruction.opcode is IROpcode.INVERT
                    and instruction.operands[0] in constants
                ):
                    value = invert(
                        constants[instruction.operands[0]],
                        _width(register_types[instruction.result]),
                    )
                elif (
                    instruction.opcode is IROpcode.ADD
                    and all(
                        operand in constants
                        for operand in instruction.operands
                    )
                ):
                    value = add(
                        constants[instruction.operands[0]],
                        constants[instruction.operands[1]],
                        _width(register_types[instruction.result]),
                    )
            except TernaryRangeError:
                value = None
            if value is not None:
                constants[instruction.result] = value
                changed = True
    return constants


def _initial_state(function: IRFunction) -> StateMap:
    return {
        (memory.index, index): InitializationState.UNINITIALIZED
        for memory in function.memory_objects
        for index in range(memory.length)
    }


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


def _predecessors(
    function: IRFunction,
    successors: dict[str, tuple[str, ...]],
) -> dict[str, set[str]]:
    result = {block.name: set() for block in function.blocks}
    for source, targets in successors.items():
        for target in targets:
            result[target].add(source)
    return result


def _reachable(successors: dict[str, tuple[str, ...]]) -> set[str]:
    result: set[str] = set()
    pending = ["entry"]
    while pending:
        block = pending.pop()
        if block in result:
            continue
        result.add(block)
        pending.extend(
            target
            for target in successors[block]
            if target not in result
        )
    return result


def _constant_index(
    instruction: IRInstruction,
    constants: dict[int, int],
) -> int | None:
    if not instruction.operands:
        return None
    return constants.get(instruction.operands[0])


def _apply_store(
    state: StateMap,
    instruction: IRInstruction,
    constants: dict[int, int],
    memory_lengths: dict[int, int],
) -> None:
    assert instruction.memory is not None
    index = _constant_index(instruction, constants)
    if index is not None and 0 <= index < memory_lengths[instruction.memory]:
        state[(instruction.memory, index)] = InitializationState.INITIALIZED
        return
    for cell, current in tuple(state.items()):
        if cell[0] != instruction.memory:
            continue
        if current is InitializationState.UNINITIALIZED:
            state[cell] = InitializationState.MAYBE_INITIALIZED


def _transfer(
    state: StateMap,
    instructions: tuple[IRInstruction, ...],
    constants: dict[int, int],
    memory_lengths: dict[int, int],
) -> StateMap:
    result = dict(state)
    for instruction in instructions:
        if instruction.opcode is IROpcode.STORE:
            _apply_store(result, instruction, constants, memory_lengths)
    return result


def _analyze_function(function: IRFunction) -> FunctionInitialization:
    successors = _successors(function)
    predecessors = _predecessors(function, successors)
    reachable = _reachable(successors)
    constants = _constant_values(function)
    initial = _initial_state(function)
    memory_lengths = {
        memory.index: memory.length for memory in function.memory_objects
    }
    memory_mutability = {
        memory.index: memory.mutable for memory in function.memory_objects
    }

    entries: dict[str, StateMap] = {}
    exits: dict[str, StateMap] = {}
    changed = True
    while changed:
        changed = False
        for block in function.blocks:
            if block.name not in reachable:
                continue
            incoming = [
                exits[predecessor]
                for predecessor in sorted(predecessors[block.name])
                if predecessor in exits
            ]
            if block.name == "entry":
                incoming.insert(0, initial)
            if not incoming:
                continue
            entry = _join_maps(incoming)
            exit_state = _transfer(
                entry,
                block.instructions,
                constants,
                memory_lengths,
            )
            if entries.get(block.name) != entry:
                entries[block.name] = entry
                changed = True
            if exits.get(block.name) != exit_state:
                exits[block.name] = exit_state
                changed = True

    for block in function.blocks:
        if block.name not in reachable:
            continue
        state = dict(entries[block.name])
        for instruction in block.instructions:
            if instruction.opcode is IROpcode.LOAD:
                assert instruction.memory is not None
                index = _constant_index(instruction, constants)
                if (
                    index is not None
                    and 0 <= index < memory_lengths[instruction.memory]
                    and state[(instruction.memory, index)]
                    is InitializationState.UNINITIALIZED
                ):
                    raise InitializationAnalysisError(
                        f"function '{function.name}', block '{block.name}', "
                        f"load: memory m{instruction.memory} index {index} is "
                        "definitely uninitialized",
                        instruction.location,
                        diagnostic_category=DiagnosticCategory.UNINITIALIZED,
                        diagnostic_code=(
                            DiagnosticCode.INITIALIZATION_UNINITIALIZED
                        ),
                        diagnostic_context={
                            "function": function.name,
                            "block": block.name,
                            "opcode": instruction.opcode.value,
                            "memory": f"m{instruction.memory}",
                            "index": index,
                        },
                    )
            elif instruction.opcode is IROpcode.STORE:
                assert instruction.memory is not None
                index = _constant_index(instruction, constants)
                if (
                    not memory_mutability[instruction.memory]
                    and index is not None
                    and 0 <= index < memory_lengths[instruction.memory]
                    and state[(instruction.memory, index)]
                    is InitializationState.INITIALIZED
                ):
                    raise InitializationAnalysisError(
                        f"function '{function.name}', block '{block.name}', "
                        f"store: immutable memory m{instruction.memory} index "
                        f"{index} is definitely already initialized",
                        instruction.location,
                        diagnostic_category=DiagnosticCategory.IMMUTABLE_WRITE,
                        diagnostic_code=(
                            DiagnosticCode.INITIALIZATION_IMMUTABLE_WRITE
                        ),
                        diagnostic_context={
                            "function": function.name,
                            "block": block.name,
                            "opcode": instruction.opcode.value,
                            "memory": f"m{instruction.memory}",
                            "index": index,
                        },
                    )
                _apply_store(state, instruction, constants, memory_lengths)

    def freeze(states: dict[str, StateMap]):
        return tuple(
            (
                name,
                tuple(
                    (cell, state.value)
                    for cell, state in sorted(states[name].items())
                ),
            )
            for name in sorted(states)
        )

    return FunctionInitialization(
        function.name,
        tuple(sorted(constants.items())),
        freeze(entries),
        freeze(exits),
    )


def analyze_initialization(module: IRModule) -> InitializationReport:
    verify_ir(module)
    return InitializationReport(
        tuple(_analyze_function(function) for function in module.functions)
    )
