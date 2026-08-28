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
BitState = tuple[int, int]


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


def _memory_layout(
    function: IRFunction,
) -> tuple[dict[int, int], dict[int, int], dict[int, int], int]:
    """Assign each memory cell one bit position for flow analysis.

    The previous implementation copied a dictionary entry for every cell into
    every reachable block.  Large generated functions therefore consumed
    memory proportional to ``blocks * cells``.  Bitsets retain the same three
    state lattice while making block states compact.
    """

    offsets: dict[int, int] = {}
    masks: dict[int, int] = {}
    lengths: dict[int, int] = {}
    offset = 0
    for memory in sorted(function.memory_objects, key=lambda item: item.index):
        offsets[memory.index] = offset
        lengths[memory.index] = memory.length
        masks[memory.index] = ((1 << memory.length) - 1) << offset
        offset += memory.length
    return offsets, masks, lengths, offset


def _cell_bit(
    memory: int,
    index: int | None,
    offsets: dict[int, int],
    lengths: dict[int, int],
) -> int:
    if index is None or memory not in offsets:
        return 0
    if index < 0 or index >= lengths[memory]:
        return 0
    return 1 << (offsets[memory] + index)


def _join_bit_states(states: list[BitState], full_mask: int) -> BitState:
    assert states
    initialized = states[0][0]
    uninitialized = full_mask & ~(states[0][0] | states[0][1])
    for state_initialized, state_maybe in states[1:]:
        initialized &= state_initialized
        uninitialized &= full_mask & ~(state_initialized | state_maybe)
    maybe = full_mask & ~(initialized | uninitialized)
    return initialized, maybe


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
    state: BitState,
    instruction: IRInstruction,
    constants: dict[int, int],
    offsets: dict[int, int],
    memory_lengths: dict[int, int],
    memory_masks: dict[int, int],
) -> BitState:
    assert instruction.memory is not None
    initialized, maybe = state
    index = _constant_index(instruction, constants)
    bit = _cell_bit(
        instruction.memory,
        index,
        offsets,
        memory_lengths,
    )
    if bit:
        return initialized | bit, maybe & ~bit
    memory_mask = memory_masks[instruction.memory]
    uninitialized = memory_mask & ~(initialized | maybe)
    return initialized, maybe | uninitialized


def _transfer(
    state: BitState,
    instructions: tuple[IRInstruction, ...],
    constants: dict[int, int],
    offsets: dict[int, int],
    memory_lengths: dict[int, int],
    memory_masks: dict[int, int],
) -> BitState:
    result = state
    for instruction in instructions:
        if instruction.opcode is IROpcode.STORE:
            result = _apply_store(
                result,
                instruction,
                constants,
                offsets,
                memory_lengths,
                memory_masks,
            )
    return result


def _analyze_function(
    function: IRFunction,
    *,
    include_states: bool,
) -> FunctionInitialization:
    blocks = {block.name: block for block in function.blocks}
    successors = _successors(function)
    predecessors = _predecessors(function, successors)
    reachable = _reachable(successors)
    constants = _constant_values(function)
    offsets, memory_masks, memory_lengths, total_cells = _memory_layout(function)
    full_mask = (1 << total_cells) - 1 if total_cells else 0
    initial: BitState = (0, 0)
    memory_mutability = {
        memory.index: memory.mutable for memory in function.memory_objects
    }

    entries: dict[str, BitState] = {}
    exits: dict[str, BitState] = {}
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
            entry = _join_bit_states(incoming, full_mask)
            exit_state = _transfer(
                entry,
                block.instructions,
                constants,
                offsets,
                memory_lengths,
                memory_masks,
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
        state = entries[block.name]
        for instruction in block.instructions:
            if instruction.opcode is IROpcode.LOAD:
                assert instruction.memory is not None
                index = _constant_index(instruction, constants)
                bit = _cell_bit(
                    instruction.memory,
                    index,
                    offsets,
                    memory_lengths,
                )
                if bit and not (state[0] & bit) and not (state[1] & bit):
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
                bit = _cell_bit(
                    instruction.memory,
                    index,
                    offsets,
                    memory_lengths,
                )
                if (
                    not memory_mutability[instruction.memory]
                    and bit
                    and state[0] & bit
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
                state = _apply_store(
                    state,
                    instruction,
                    constants,
                    offsets,
                    memory_lengths,
                    memory_masks,
                )

    def freeze(states: dict[str, BitState]):
        if not include_states:
            return ()
        cells = tuple(
            (memory.index, index)
            for memory in sorted(
                function.memory_objects,
                key=lambda item: item.index,
            )
            for index in range(memory.length)
        )
        return tuple(
            (
                name,
                tuple(
                    (
                        cell,
                        (
                            InitializationState.INITIALIZED
                            if states[name][0]
                            & (1 << (offsets[cell[0]] + cell[1]))
                            else InitializationState.MAYBE_INITIALIZED
                            if states[name][1]
                            & (1 << (offsets[cell[0]] + cell[1]))
                            else InitializationState.UNINITIALIZED
                        ).value,
                    )
                    for cell in cells
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


def analyze_initialization(
    module: IRModule,
    *,
    include_states: bool = True,
) -> InitializationReport:
    verify_ir(module)
    return InitializationReport(
        tuple(
            _analyze_function(function, include_states=include_states)
            for function in module.functions
            if not function.external
        )
    )
