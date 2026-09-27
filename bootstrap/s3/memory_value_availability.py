"""Conservative CFG dataflow for direct frame-memory value availability.

This analysis is diagnostic and experimental. It does not authorize or apply
IR transformations. Indirect writes and calls invalidate tracked facts.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum

from .alias_analysis import AliasAnalysis, AliasResult
from .ir import IROpcode
from .ssa import SSAFunction, SSAInstruction, SSAValue


class AvailabilityKind(str, Enum):
    AVAILABLE = "AVAILABLE"
    KILLED = "KILLED"
    MAYBE_AVAILABLE = "MAYBE_AVAILABLE"
    UNKNOWN = "UNKNOWN"
    UNINITIALIZED = "UNINITIALIZED"


@dataclass(frozen=True, slots=True)
class StorageIdentity:
    """Identity for one directly indexed frame-memory cell."""

    memory_object: int
    index: int | str

    def sort_key(self) -> tuple[int, int, int | str]:
        if isinstance(self.index, int):
            return self.memory_object, 0, self.index
        return self.memory_object, 1, self.index


@dataclass(frozen=True, slots=True)
class AvailabilityState:
    kind: AvailabilityKind
    value: SSAValue | None = None
    store_blocks: tuple[str, ...] = ()
    store_sites: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class LoadAvailability:
    block: str
    instruction_index: int
    result: SSAValue | None
    storage: StorageIdentity | None
    state: AvailabilityState
    reason: str

    @property
    def forwardable(self) -> bool:
        return (
            self.state.kind is AvailabilityKind.AVAILABLE
            and self.state.value is not None
            and self.result is not None
            and self.state.value.type is self.result.type
        )

    @property
    def cross_block_available(self) -> bool:
        return self.forwardable and any(
            block != self.block for block in self.state.store_blocks
        )


@dataclass(frozen=True, slots=True)
class MemoryValueAvailabilityReport:
    function: str
    loads: tuple[LoadAvailability, ...]
    block_updates: int

    @property
    def forwardable_load_count(self) -> int:
        return sum(load.forwardable for load in self.loads)


@dataclass(frozen=True, slots=True)
class LoadReuseState:
    kind: AvailabilityKind
    value: SSAValue | None = None
    load_sites: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class RepeatedLoadCandidate:
    block: str
    instruction_index: int
    result: SSAValue | None
    storage: StorageIdentity | None
    state: LoadReuseState
    reason: str

    @property
    def forwardable(self) -> bool:
        return (
            self.state.kind is AvailabilityKind.AVAILABLE
            and self.state.value is not None
            and self.result is not None
            and self.state.value.type is self.result.type
        )

    @property
    def cross_block_available(self) -> bool:
        return self.forwardable and any(
            source_block != self.block
            for source_block, _ in self.state.load_sites
        )


@dataclass(frozen=True, slots=True)
class RepeatedLoadAvailabilityReport:
    function: str
    candidates: tuple[RepeatedLoadCandidate, ...]
    block_updates: int

    @property
    def cross_block_candidate_count(self) -> int:
        return sum(candidate.cross_block_available for candidate in self.candidates)


_UNKNOWN = AvailabilityState(AvailabilityKind.UNKNOWN)
_UNINITIALIZED = AvailabilityState(AvailabilityKind.UNINITIALIZED)
_KILLED = AvailabilityState(AvailabilityKind.KILLED)
_MAYBE = AvailabilityState(AvailabilityKind.MAYBE_AVAILABLE)
_LOAD_UNKNOWN = LoadReuseState(AvailabilityKind.UNKNOWN)
_LOAD_UNINITIALIZED = LoadReuseState(AvailabilityKind.UNINITIALIZED)
_LOAD_KILLED = LoadReuseState(AvailabilityKind.KILLED)
_LOAD_MAYBE = LoadReuseState(AvailabilityKind.MAYBE_AVAILABLE)
_NON_WRITING_OPCODES = frozenset(
    {
        IROpcode.CONST,
        IROpcode.CONST_STR,
        IROpcode.MOVE,
        IROpcode.INVERT,
        IROpcode.ADD,
        IROpcode.NUMERIC_DIFFERENCE,
        IROpcode.MULTIPLY,
        IROpcode.DIVIDE,
        IROpcode.RELATE,
        IROpcode.CONVERT,
        IROpcode.MINIMUM,
        IROpcode.MAXIMUM,
        IROpcode.COMPARE,
        IROpcode.LOAD,
        IROpcode.ADDRESS_OF,
        IROpcode.AGGREGATE_ADDRESS_OF,
        IROpcode.AGGREGATE_FIELD_LOAD,
        IROpcode.AGGREGATE_FIELD_ADDRESS,
        IROpcode.REFERENCE_LOAD,
        IROpcode.SLICE_LENGTH,
        IROpcode.SLICE_LOAD,
        IROpcode.RETURN,
        IROpcode.JUMP,
        IROpcode.BRANCH3,
    }
)


def _same_value(left: SSAValue | None, right: SSAValue | None) -> bool:
    return (
        left is not None
        and right is not None
        and left.name == right.name
        and left.type is right.type
    )


def _join(states: tuple[AvailabilityState, ...]) -> AvailabilityState:
    if not states:
        return _UNINITIALIZED
    first = states[0]
    if all(state.kind is first.kind for state in states[1:]):
        if first.kind is AvailabilityKind.AVAILABLE:
            if all(_same_value(state.value, first.value) for state in states[1:]):
                return AvailabilityState(
                    AvailabilityKind.AVAILABLE,
                    first.value,
                    tuple(
                        sorted(
                            {
                                block
                                for state in states
                                for block in state.store_blocks
                            }
                        )
                    ),
                    tuple(
                        sorted(
                            {
                                site
                                for state in states
                                for site in state.store_sites
                            }
                        )
                    ),
                )
        else:
            return first
    if any(state.kind is AvailabilityKind.UNKNOWN for state in states):
        return _UNKNOWN
    if all(
        state.kind in {AvailabilityKind.KILLED, AvailabilityKind.UNINITIALIZED}
        for state in states
    ):
        return _KILLED if any(state.kind is AvailabilityKind.KILLED for state in states) else _UNINITIALIZED
    return _MAYBE


def _cfg(function: SSAFunction) -> tuple[dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    block_names = {block.name for block in function.blocks}
    successors: dict[str, tuple[str, ...]] = {}
    predecessors: dict[str, list[str]] = {block.name: [] for block in function.blocks}
    for block in function.blocks:
        if not block.instructions:
            targets: tuple[str, ...] = ()
        else:
            terminator = block.instructions[-1]
            if terminator.opcode in {IROpcode.JUMP, IROpcode.BRANCH3}:
                targets = tuple(
                    target for target in terminator.targets if target in block_names
                )
            else:
                targets = ()
        successors[block.name] = tuple(dict.fromkeys(targets))
        for target in successors[block.name]:
            predecessors[target].append(block.name)
    return successors, {
        name: tuple(sorted(items)) for name, items in predecessors.items()
    }


def _constant_indices(function: SSAFunction) -> dict[str, int]:
    return {
        instruction.result.name: instruction.immediate
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode is IROpcode.CONST
        and instruction.result is not None
        and isinstance(instruction.immediate, int)
        and not isinstance(instruction.immediate, bool)
    }


def _storage_identity(
    instruction: SSAInstruction,
    constants: dict[str, int],
) -> StorageIdentity | None:
    if instruction.memory is None or not instruction.operands:
        return None
    index_value = instruction.operands[0]
    if index_value.def_block is None:
        return None
    index: int | str = constants.get(index_value.name, index_value.name)
    return StorageIdentity(instruction.memory, index)


def _alias(left: StorageIdentity, right: StorageIdentity) -> AliasResult:
    return AliasAnalysis.alias_cell(
        left.memory_object,
        left.index,
        right.memory_object,
        right.index,
    )


def _direct_store_value(instruction: SSAInstruction) -> SSAValue | None:
    if instruction.opcode is not IROpcode.STORE or len(instruction.operands) < 2:
        return None
    value = instruction.operands[1]
    return value if value.def_block is not None else None


def _apply_instruction(
    state: AvailabilityState,
    instruction: SSAInstruction,
    target: StorageIdentity,
    constants: dict[str, int],
    block: str,
    instruction_index: int,
) -> AvailabilityState:
    if instruction.opcode is IROpcode.STORE:
        storage = _storage_identity(instruction, constants)
        value = _direct_store_value(instruction)
        if storage is None or value is None:
            return _UNKNOWN
        relation = _alias(storage, target)
        if relation is AliasResult.NO_ALIAS:
            return state
        if relation is AliasResult.MUST_ALIAS:
            return AvailabilityState(
                AvailabilityKind.AVAILABLE,
                value,
                (block,),
                ((block, instruction_index),),
            )
        if (
            state.kind is AvailabilityKind.AVAILABLE
            and _same_value(state.value, value)
        ):
            return AvailabilityState(
                AvailabilityKind.AVAILABLE,
                state.value,
                tuple(sorted(set(state.store_blocks) | {block})),
                tuple(
                    sorted(set(state.store_sites) | {(block, instruction_index)})
                ),
            )
        if state.kind is AvailabilityKind.UNKNOWN:
            return _UNKNOWN
        return _MAYBE
    if instruction.opcode in {
        IROpcode.CALL,
        IROpcode.REFERENCE_STORE,
        IROpcode.SLICE_STORE,
    }:
        return _UNKNOWN
    if instruction.opcode in _NON_WRITING_OPCODES:
        return state
    return _UNKNOWN


def _entry_state(
    block: str,
    entry: str,
    predecessors: dict[str, tuple[str, ...]],
    outputs: dict[str, AvailabilityState | None],
) -> AvailabilityState | None:
    incoming: list[AvailabilityState] = []
    if block == entry:
        incoming.append(_UNINITIALIZED)
    for predecessor in predecessors[block]:
        state = outputs[predecessor]
        if state is not None:
            incoming.append(state)
    if not incoming:
        return None
    return _join(tuple(incoming))


def _analyze_storage(
    function: SSAFunction,
    target: StorageIdentity,
    constants: dict[str, int],
    successors: dict[str, tuple[str, ...]],
    predecessors: dict[str, tuple[str, ...]],
) -> tuple[dict[str, AvailabilityState], dict[tuple[str, int], AvailabilityState], int]:
    if not function.blocks:
        return {}, {}, 0
    entry = function.blocks[0].name
    outputs: dict[str, AvailabilityState | None] = {
        block.name: None for block in function.blocks
    }
    queue = deque((entry,))
    queued = {entry}
    updates = 0
    inputs: dict[str, AvailabilityState] = {}

    while queue:
        name = queue.popleft()
        queued.discard(name)
        incoming = _entry_state(name, entry, predecessors, outputs)
        if incoming is None:
            continue
        inputs[name] = incoming
        state = incoming
        block = next(block for block in function.blocks if block.name == name)
        for instruction_index, instruction in enumerate(block.instructions):
            state = _apply_instruction(
                state,
                instruction,
                target,
                constants,
                name,
                instruction_index,
            )
        if outputs[name] == state:
            continue
        outputs[name] = state
        updates += 1
        for successor in successors[name]:
            if successor not in queued:
                queue.append(successor)
                queued.add(successor)

    load_states: dict[tuple[str, int], AvailabilityState] = {}
    for block in function.blocks:
        state = inputs.get(block.name)
        if state is None:
            continue
        for index, instruction in enumerate(block.instructions):
            if (
                instruction.opcode is IROpcode.LOAD
                and _storage_identity(instruction, constants) == target
            ):
                load_states[(block.name, index)] = state
            state = _apply_instruction(
                state, instruction, target, constants, block.name, index
            )
    return inputs, load_states, updates


def analyze_memory_value_availability(
    function: SSAFunction,
) -> MemoryValueAvailabilityReport:
    """Find loads whose exact stored value is available on every CFG path.

    Only direct `STORE`/`LOAD` cells participate. Direct stores use the shared
    conservative alias-cell query. Calls and indirect stores invalidate the
    fact. No transformation is performed by this analysis.
    """

    constants = _constant_indices(function)
    successors, predecessors = _cfg(function)
    load_locations: dict[tuple[str, int], StorageIdentity | None] = {}
    unique_locations: set[StorageIdentity] = set()
    for block in function.blocks:
        for index, instruction in enumerate(block.instructions):
            if instruction.opcode is IROpcode.LOAD:
                storage = _storage_identity(instruction, constants)
                load_locations[(block.name, index)] = storage
                if storage is not None:
                    unique_locations.add(storage)

    states_by_load: dict[tuple[str, int], AvailabilityState] = {}
    total_updates = 0
    for storage in sorted(unique_locations, key=StorageIdentity.sort_key):
        _inputs, load_states, updates = _analyze_storage(
            function,
            storage,
            constants,
            successors,
            predecessors,
        )
        total_updates += updates
        states_by_load.update(load_states)

    loads: list[LoadAvailability] = []
    for block in function.blocks:
        for index, instruction in enumerate(block.instructions):
            if instruction.opcode is not IROpcode.LOAD:
                continue
            key = (block.name, index)
            storage = load_locations[key]
            result = instruction.result
            if storage is None:
                state = _UNKNOWN
                reason = "LOAD_LOCATION_NOT_PROVEN"
            else:
                state = states_by_load.get(key, _UNINITIALIZED)
                if state.kind is AvailabilityKind.AVAILABLE:
                    if (
                        state.value is None
                        or result is None
                        or state.value.type is not result.type
                    ):
                        state = _UNKNOWN
                        reason = "STORED_VALUE_TYPE_OR_DEFINITION_UNPROVEN"
                    else:
                        reason = "SAME_EXACT_VALUE_ON_ALL_PATHS"
                elif state.kind is AvailabilityKind.MAYBE_AVAILABLE:
                    reason = "ALIAS_OR_CONTROL_FLOW_MERGE"
                elif state.kind is AvailabilityKind.KILLED:
                    reason = "ALL_PATHS_KILLED"
                elif state.kind is AvailabilityKind.UNINITIALIZED:
                    reason = "NO_REACHING_STORE"
                else:
                    reason = "UNKNOWN_MEMORY_EFFECT_OR_LOCATION"
            loads.append(
                LoadAvailability(
                    block.name,
                    index,
                    result,
                    storage,
                    state,
                    reason,
                )
            )
    return MemoryValueAvailabilityReport(
        function.name,
        tuple(loads),
        total_updates,
    )


def _join_load_states(states: tuple[LoadReuseState, ...]) -> LoadReuseState:
    if not states:
        return _LOAD_UNINITIALIZED
    first = states[0]
    if all(state.kind is first.kind for state in states[1:]):
        if first.kind is AvailabilityKind.AVAILABLE and all(
            _same_value(state.value, first.value) for state in states[1:]
        ):
            return LoadReuseState(
                AvailabilityKind.AVAILABLE,
                first.value,
                tuple(sorted({site for state in states for site in state.load_sites})),
            )
        if first.kind is not AvailabilityKind.AVAILABLE:
            return first
    if any(state.kind is AvailabilityKind.UNKNOWN for state in states):
        return _LOAD_UNKNOWN
    if all(
        state.kind in {AvailabilityKind.KILLED, AvailabilityKind.UNINITIALIZED}
        for state in states
    ):
        return (
            _LOAD_KILLED
            if any(state.kind is AvailabilityKind.KILLED for state in states)
            else _LOAD_UNINITIALIZED
        )
    return _LOAD_MAYBE


def _load_entry_state(
    block: str,
    entry: str,
    predecessors: dict[str, tuple[str, ...]],
    outputs: dict[str, LoadReuseState | None],
) -> LoadReuseState | None:
    incoming: list[LoadReuseState] = []
    if block == entry:
        incoming.append(_LOAD_UNINITIALIZED)
    for predecessor in predecessors[block]:
        state = outputs[predecessor]
        if state is not None:
            incoming.append(state)
    if not incoming:
        return None
    return _join_load_states(tuple(incoming))


def _apply_load_instruction(
    state: LoadReuseState,
    instruction: SSAInstruction,
    target: StorageIdentity,
    constants: dict[str, int],
    block: str,
    instruction_index: int,
) -> LoadReuseState:
    if instruction.opcode is IROpcode.LOAD:
        if _storage_identity(instruction, constants) != target:
            return state
        if instruction.result is None or instruction.result.def_block is None:
            return _LOAD_UNKNOWN
        return LoadReuseState(
            AvailabilityKind.AVAILABLE,
            instruction.result,
            ((block, instruction_index),),
        )
    if instruction.opcode is IROpcode.STORE:
        storage = _storage_identity(instruction, constants)
        if storage is None:
            return _LOAD_UNKNOWN
        relation = _alias(storage, target)
        if relation is AliasResult.NO_ALIAS:
            return state
        if relation is AliasResult.MUST_ALIAS:
            return _LOAD_KILLED
        return _LOAD_UNKNOWN
    if instruction.opcode in {
        IROpcode.CALL,
        IROpcode.REFERENCE_STORE,
        IROpcode.SLICE_STORE,
    }:
        return _LOAD_UNKNOWN
    if instruction.opcode in _NON_WRITING_OPCODES:
        return state
    return _LOAD_UNKNOWN


def _analyze_repeated_load_storage(
    function: SSAFunction,
    target: StorageIdentity,
    constants: dict[str, int],
    successors: dict[str, tuple[str, ...]],
    predecessors: dict[str, tuple[str, ...]],
) -> tuple[dict[tuple[str, int], LoadReuseState], int]:
    if not function.blocks:
        return {}, 0
    entry = function.blocks[0].name
    outputs: dict[str, LoadReuseState | None] = {
        block.name: None for block in function.blocks
    }
    inputs: dict[str, LoadReuseState] = {}
    queue = deque((entry,))
    queued = {entry}
    updates = 0
    while queue:
        name = queue.popleft()
        queued.discard(name)
        incoming = _load_entry_state(name, entry, predecessors, outputs)
        if incoming is None:
            continue
        inputs[name] = incoming
        state = incoming
        block = next(block for block in function.blocks if block.name == name)
        for index, instruction in enumerate(block.instructions):
            state = _apply_load_instruction(
                state, instruction, target, constants, name, index
            )
        if outputs[name] == state:
            continue
        outputs[name] = state
        updates += 1
        for successor in successors[name]:
            if successor not in queued:
                queue.append(successor)
                queued.add(successor)

    candidates: dict[tuple[str, int], LoadReuseState] = {}
    for block in function.blocks:
        state = inputs.get(block.name)
        if state is None:
            continue
        for index, instruction in enumerate(block.instructions):
            if (
                instruction.opcode is IROpcode.LOAD
                and _storage_identity(instruction, constants) == target
            ):
                candidates[(block.name, index)] = state
            state = _apply_load_instruction(
                state, instruction, target, constants, block.name, index
            )
    return candidates, updates


def analyze_repeated_load_availability(
    function: SSAFunction,
) -> RepeatedLoadAvailabilityReport:
    """Find exact-cell LOAD values still available across CFG edges.

    This is a diagnostic experiment, separate from store-to-load availability.
    Same-block repeats are deliberately excluded from the reported candidates.
    Stores that may alias the cell and calls/indirect writes kill the fact.
    """

    constants = _constant_indices(function)
    successors, predecessors = _cfg(function)
    load_locations: dict[tuple[str, int], StorageIdentity | None] = {}
    unique_locations: set[StorageIdentity] = set()
    for block in function.blocks:
        for index, instruction in enumerate(block.instructions):
            if instruction.opcode is IROpcode.LOAD:
                storage = _storage_identity(instruction, constants)
                load_locations[(block.name, index)] = storage
                if storage is not None:
                    unique_locations.add(storage)

    states: dict[tuple[str, int], LoadReuseState] = {}
    updates = 0
    for storage in sorted(unique_locations, key=StorageIdentity.sort_key):
        per_load, count = _analyze_repeated_load_storage(
            function, storage, constants, successors, predecessors
        )
        states.update(per_load)
        updates += count

    candidates: list[RepeatedLoadCandidate] = []
    for block in function.blocks:
        for index, instruction in enumerate(block.instructions):
            if instruction.opcode is not IROpcode.LOAD:
                continue
            key = (block.name, index)
            storage = load_locations[key]
            result = instruction.result
            state = states.get(
                key, _LOAD_UNKNOWN if storage is None else _LOAD_UNINITIALIZED
            )
            if storage is None:
                reason = "LOAD_LOCATION_NOT_PROVEN"
            elif state.kind is AvailabilityKind.AVAILABLE:
                if (
                    state.value is None
                    or result is None
                    or state.value.type is not result.type
                ):
                    state = _LOAD_UNKNOWN
                    reason = "LOAD_VALUE_TYPE_OR_DEFINITION_UNPROVEN"
                else:
                    reason = "SAME_EXACT_VALUE_AVAILABLE_ON_ALL_PATHS"
            elif state.kind is AvailabilityKind.MAYBE_AVAILABLE:
                reason = "CONTROL_FLOW_MERGE_HAS_DIFFERENT_LOAD_VALUES"
            elif state.kind is AvailabilityKind.KILLED:
                reason = "REACHING_STORE_INVALIDATED_PRIOR_LOAD"
            elif state.kind is AvailabilityKind.UNINITIALIZED:
                reason = "NO_REACHING_LOAD"
            else:
                reason = "UNKNOWN_MEMORY_EFFECT_OR_LOCATION"
            candidate = RepeatedLoadCandidate(
                block.name, index, result, storage, state, reason
            )
            candidates.append(candidate)
    return RepeatedLoadAvailabilityReport(function.name, tuple(candidates), updates)
