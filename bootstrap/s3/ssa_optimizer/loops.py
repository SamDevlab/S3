"""SSA loop and strength-reduction passes."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from typing import Dict, List, Set, Tuple

from ..alias_analysis import AliasAnalysis
from ..builtin_effects import BuiltinEffect, builtin_effect
from ..cfg import ControlFlowGraph
from ..dominance import DominatorTree
from ..ir import IRBasicBlock, IRFunction, IRInstruction, IROpcode, IRType
from ..ssa import SSABlock, SSAFunction, SSAInstruction, SSAPhiNode, SSAValue
from ..ternary import (
    TernaryRangeError,
    add,
    compare,
    invert,
    tritwise_max,
    tritwise_min,
)
from .common import _FOLDABLE_OPCODES, _PURE_REMOVABLE_OPCODES, _width
from .lowering import _cfg_from_ssa


@dataclass(frozen=True, slots=True)
class LoopInfo:
    """Natural-loop structure derived from CFG backedges and dominance."""

    header: str
    blocks: frozenset[str]
    backedges: tuple[str, ...]
    preheaders: tuple[str, ...]
    exits: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InductionInfo:
    """A scalar memory recurrence with constant initialization and stride."""

    memory: int
    initial_value: int
    step: int
    update_block: str
    update_index: int


@dataclass(frozen=True, slots=True)
class LoopCarriedRecurrenceInfo:
    """A scalar recurrence proven to update once on every reachable backedge."""

    loop_header: str
    memory: int
    condition_memory: int
    condition_relation: str
    element_type: IRType
    kind: str
    operation: str
    initial_value: int | float
    step: int | None
    update_sites: tuple[tuple[str, int], ...]
    backedge_updates: tuple[tuple[str, int], ...]
    ordered: bool


@dataclass(frozen=True, slots=True)
class RangeFact:
    """An access-point fact established by a monotonic counted-loop test."""

    induction_memory: int
    lower_bound: int
    step: int
    upper_bound_vector: int
    upper_bound_exclusive: bool
    access_block: str
    access_index: int


@dataclass(frozen=True, slots=True)
class VectorBoundsProof:
    """A conservative proof for one vector access in a canonical counted loop."""

    loop: LoopInfo
    induction: InductionInfo
    range_fact: RangeFact
    element_type: IRType
    vector_register: int
    access_block: str
    access_index: int

    @property
    def header(self) -> str:
        return self.loop.header

    @property
    def body(self) -> str:
        return self.induction.update_block

    @property
    def latch(self) -> str:
        return self.induction.update_block


@dataclass(frozen=True, slots=True)
class ReductionInfo:
    """An ordered scalar recurrence; recognition never permits reassociation."""

    loop_header: str
    accumulator_memory: int
    element_type: IRType
    operation: str
    initial_register: int
    initial_constant: int | float | None
    recurrence_register: int
    update_block: str
    update_index: int
    ordered: bool = True


@dataclass(frozen=True, slots=True)
class LoopAnalysisMetrics:
    loops_seen: int
    inductions_recognized: int
    range_facts_derived: int
    bounds_checks_seen: int
    bounds_checks_proven_safe: int
    bounds_checks_eliminated: int
    bounds_checks_retained: int


@dataclass(frozen=True, slots=True)
class ReductionAnalysisMetrics:
    loops_seen: int
    reductions_recognized: int
    add_reductions: int
    multiply_reductions: int
    min_reductions: int
    max_reductions: int
    unsupported_reductions: int | None


@dataclass(frozen=True, slots=True)
class LoopAnalysisResult:
    loops: tuple[LoopInfo, ...]
    inductions: tuple[InductionInfo, ...]
    recurrences: tuple[LoopCarriedRecurrenceInfo, ...]
    range_facts: tuple[RangeFact, ...]
    proofs: tuple[VectorBoundsProof, ...]
    metrics: LoopAnalysisMetrics
    reductions: tuple[ReductionInfo, ...]
    reduction_metrics: ReductionAnalysisMetrics


_VECTOR_ELEMENT_TYPES = {
    "tryte": IRType.TRYTE,
    "i64": IRType.I64,
    "f64": IRType.F64,
}


def _constant_register(
    register: int,
    definitions: dict[int, IRInstruction],
    seen: set[int] | None = None,
) -> int | float | None:
    visited = set() if seen is None else seen
    if register in visited:
        return None
    visited.add(register)
    instruction = definitions.get(register)
    if instruction is None:
        return None
    if instruction.opcode is IROpcode.CONST:
        return instruction.immediate
    if instruction.opcode is IROpcode.MOVE and len(instruction.operands) == 1:
        return _constant_register(instruction.operands[0], definitions, visited)
    return None


def _copy_source(register: int, definitions: dict[int, IRInstruction]) -> int:
    seen: set[int] = set()
    current = register
    while current not in seen:
        seen.add(current)
        instruction = definitions.get(current)
        if (
            instruction is None
            or instruction.opcode is not IROpcode.MOVE
            or len(instruction.operands) != 1
        ):
            break
        current = instruction.operands[0]
    return current


def _natural_loop_blocks(
    cfg: ControlFlowGraph,
    dominators: DominatorTree,
    header: str,
    tail: str,
) -> set[str]:
    blocks = {header, tail}
    pending = [tail]
    while pending:
        current = pending.pop()
        for predecessor in sorted(cfg.nodes[current].predecessors, reverse=True):
            if predecessor not in blocks and dominators.dominates(header, predecessor):
                blocks.add(predecessor)
                pending.append(predecessor)
    return blocks


def discover_loop_info(function: IRFunction) -> tuple[LoopInfo, ...]:
    """Discover natural loops and their external CFG boundaries."""

    cfg = ControlFlowGraph.build(function)
    dominators = DominatorTree.build(cfg)
    backedges: dict[str, list[str]] = {}
    for tail, node in cfg.nodes.items():
        for header in node.successors:
            if dominators.dominates(header, tail):
                backedges.setdefault(header, []).append(tail)

    loops: list[LoopInfo] = []
    for header in sorted(backedges):
        tails = tuple(sorted(backedges[header]))
        blocks = {header}
        for tail in tails:
            blocks.update(_natural_loop_blocks(cfg, dominators, header, tail))
        preheaders = tuple(sorted(cfg.nodes[header].predecessors - blocks))
        exits = tuple(
            sorted(
                {
                    successor
                    for name in blocks
                    for successor in cfg.nodes[name].successors
                    if successor not in blocks
                }
            )
        )
        loops.append(
            LoopInfo(
                header=header,
                blocks=frozenset(blocks),
                backedges=tails,
                preheaders=preheaders,
                exits=exits,
            )
        )
    return tuple(loops)


@dataclass(frozen=True, slots=True)
class _LoopCondition:
    body: str
    join: str
    condition_memory: int
    relation_arms: tuple[str, ...]


def _condition_body_for_less_than(
    function: IRFunction,
    header: str,
    definitions: dict[int, IRInstruction],
) -> _LoopCondition | None:
    blocks = {block.name: block for block in function.blocks}
    block = blocks[header]
    if not block.instructions or block.instructions[-1].opcode is not IROpcode.BRANCH3:
        return None
    branch = block.instructions[-1]
    if len(branch.operands) != 1 or len(branch.targets) != 3:
        return None
    compare_instruction = definitions.get(branch.operands[0])
    if (
        compare_instruction is None
        or compare_instruction.opcode is not IROpcode.COMPARE
        or len(compare_instruction.operands) != 2
    ):
        return None

    relation_arms = [blocks.get(name) for name in branch.targets]
    if any(arm is None or not arm.instructions for arm in relation_arms):
        return None
    joins: set[str] = set()
    condition_memory: int | None = None
    values: list[int | float | None] = []
    for arm in relation_arms:
        assert arm is not None
        terminator = arm.instructions[-1]
        stores = [
            instruction
            for instruction in arm.instructions
            if instruction.opcode is IROpcode.STORE
        ]
        if (
            terminator.opcode is not IROpcode.JUMP
            or len(terminator.targets) != 1
            or len(stores) != 1
            or len(stores[0].operands) != 2
            or stores[0].memory is None
        ):
            return None
        joins.add(terminator.targets[0])
        memory = stores[0].memory
        if condition_memory is None:
            condition_memory = memory
        elif condition_memory != memory:
            return None
        values.append(_constant_register(stores[0].operands[1], definitions))
    if len(joins) != 1 or condition_memory is None or values != [-1, 0, 0]:
        return None

    join = blocks.get(next(iter(joins)))
    if join is None or not join.instructions:
        return None
    join_branch = join.instructions[-1]
    if (
        join_branch.opcode is not IROpcode.BRANCH3
        or len(join_branch.operands) != 1
        or len(join_branch.targets) != 3
    ):
        return None
    condition_load = definitions.get(join_branch.operands[0])
    if (
        condition_load is None
        or condition_load.opcode is not IROpcode.LOAD
        or condition_load.memory != condition_memory
    ):
        return None
    return _LoopCondition(
        body=join_branch.targets[0],
        join=join.name,
        condition_memory=condition_memory,
        relation_arms=tuple(branch.targets),
    )


def _recognize_induction(
    function: IRFunction,
    loop: LoopInfo,
    body: str,
    definitions: dict[int, IRInstruction],
    blocks: dict[str, IRBasicBlock],
) -> InductionInfo | None:
    if (
        len(loop.backedges) != 1
        or loop.backedges[0] != body
        or len(loop.preheaders) != 1
        or not loop.exits
    ):
        return None
    preheader = loop.preheaders[0]
    preheader_block = blocks[preheader]
    body_block = blocks[body]
    if (
        not preheader_block.instructions
        or preheader_block.instructions[-1].opcode is not IROpcode.JUMP
        or preheader_block.instructions[-1].targets != (loop.header,)
        or not body_block.instructions
        or body_block.instructions[-1].opcode is not IROpcode.JUMP
        or body_block.instructions[-1].targets != (loop.header,)
        or any(
            instruction.opcode
            in {IROpcode.JUMP, IROpcode.BRANCH3, IROpcode.RETURN}
            for instruction in body_block.instructions[:-1]
        )
    ):
        return None

    header_block = blocks[loop.header]
    if (
        not header_block.instructions
        or header_block.instructions[-1].opcode is not IROpcode.BRANCH3
    ):
        return None
    branch = header_block.instructions[-1]
    comparison = definitions.get(branch.operands[0]) if branch.operands else None
    if (
        comparison is None
        or comparison.opcode is not IROpcode.COMPARE
        or len(comparison.operands) != 2
    ):
        return None
    index_load = definitions.get(_copy_source(comparison.operands[0], definitions))
    if index_load is None or index_load.opcode is not IROpcode.LOAD:
        return None
    induction_memory = index_load.memory
    if induction_memory is None:
        return None
    if any(
        instruction.opcode is IROpcode.ADDRESS_OF
        and instruction.memory == induction_memory
        for block in function.blocks
        for instruction in block.instructions
    ):
        return None

    initializers = [
        instruction
        for instruction in preheader_block.instructions
        if instruction.opcode is IROpcode.STORE
        and instruction.memory == induction_memory
    ]
    all_stores = [
        instruction
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode is IROpcode.STORE
        and instruction.memory == induction_memory
    ]
    if (
        len(initializers) != 1
        or len(initializers[0].operands) != 2
        or len(all_stores) != 2
    ):
        return None
    initial = _constant_register(initializers[0].operands[1], definitions)
    if isinstance(initial, bool) or not isinstance(initial, int) or initial < 0:
        return None
    updates: list[tuple[int, IRInstruction, int]] = []
    for instruction_index, instruction in enumerate(body_block.instructions[:-1]):
        if instruction.opcode is not IROpcode.ADD or len(instruction.operands) != 2:
            continue
        for load_register, step_register in (
            (instruction.operands[0], instruction.operands[1]),
            (instruction.operands[1], instruction.operands[0]),
        ):
            load = definitions.get(_copy_source(load_register, definitions))
            step = _constant_register(step_register, definitions)
            if (
                load is not None
                and load.opcode is IROpcode.LOAD
                and load.memory == induction_memory
                and isinstance(step, int)
                and not isinstance(step, bool)
                and step > 0
            ):
                updates.append((instruction_index, instruction, step))
                break
    induction_stores = [
        (index, instruction)
        for index, instruction in enumerate(body_block.instructions)
        if instruction.opcode is IROpcode.STORE
        and instruction.memory == induction_memory
    ]
    if len(updates) != 1 or len(induction_stores) != 1:
        return None
    update_index, update, step = updates[0]
    store_index, induction_store = induction_stores[0]
    if (
        store_index <= update_index
        or len(induction_store.operands) != 2
        or induction_store.operands[1] not in update.results
    ):
        return None
    return InductionInfo(
        memory=induction_memory,
        initial_value=initial,
        step=step,
        update_block=body,
        update_index=store_index,
    )


def _register_types(function: IRFunction) -> dict[int, IRType]:
    return {item.index: item.type for item in function.registers} | {
        item.register: item.type for item in function.parameters
    }


def _induction_condition_memory(
    function: IRFunction,
    loop: LoopInfo,
    definitions: dict[int, IRInstruction],
    definition_sites: dict[int, tuple[str, int, IRInstruction]],
) -> int | None:
    header = next((item for item in function.blocks if item.name == loop.header), None)
    if header is None or not header.instructions:
        return None
    terminator = header.instructions[-1]
    if terminator.opcode is not IROpcode.BRANCH3 or len(terminator.operands) != 1:
        return None
    comparison = definitions.get(terminator.operands[0])
    comparison_site = definition_sites.get(terminator.operands[0])
    if comparison is None or comparison.opcode is not IROpcode.COMPARE or len(comparison.operands) != 2:
        return None
    if comparison_site is None or comparison_site[0] != loop.header:
        return None
    load_register = _copy_source(comparison.operands[0], definitions)
    load = definitions.get(load_register)
    site = definition_sites.get(load_register)
    if (
        load is None
        or load.opcode is not IROpcode.LOAD
        or load.memory is None
        or site is None
        or site[0] != loop.header
    ):
        return None
    return load.memory


def _recurrence_update(
    memory: int,
    block_name: str,
    store_index: int,
    store: IRInstruction,
    definitions: dict[int, IRInstruction],
    definition_sites: dict[int, tuple[str, int, IRInstruction]],
    register_types: dict[int, IRType],
    element_type: IRType,
) -> tuple[str, str, int | None] | None:
    if store.opcode is not IROpcode.STORE or store.memory != memory or len(store.operands) != 2:
        return None
    value_register = _copy_source(store.operands[1], definitions)
    operation = definitions.get(value_register)
    operation_site = definition_sites.get(value_register)
    if (
        operation is None
        or operation.opcode not in {IROpcode.ADD, IROpcode.MULTIPLY}
        or len(operation.operands) != 2
        or operation_site is None
        or operation_site[0] != block_name
        or operation_site[1] >= store_index
        or register_types.get(value_register) is not element_type
    ):
        return None

    accumulator_load: IRInstruction | None = None
    other_register: int | None = None
    for accumulator_register, candidate_register in (
        (operation.operands[0], operation.operands[1]),
        (operation.operands[1], operation.operands[0]),
    ):
        source_register = _copy_source(accumulator_register, definitions)
        source = definitions.get(source_register)
        source_site = definition_sites.get(source_register)
        if (
            source is not None
            and source.opcode is IROpcode.LOAD
            and source.memory == memory
            and register_types.get(source_register) is element_type
            and source_site is not None
            and source_site[0] == block_name
            and source_site[1] < operation_site[1]
        ):
            accumulator_load = source
            other_register = candidate_register
            break
    if accumulator_load is None or other_register is None:
        return None

    constant = _constant_register(other_register, definitions)
    if register_types.get(other_register) is not element_type:
        return None
    operation_name = "add" if operation.opcode is IROpcode.ADD else "multiply"
    if (
        element_type is IRType.I64
        and operation.opcode is IROpcode.ADD
        and isinstance(constant, int)
        and not isinstance(constant, bool)
        and constant > 0
    ):
        return "INDUCTION", operation_name, constant
    if constant is None:
        return "REDUCTION", operation_name, None
    return None


def _prove_loop_carried_recurrences(
    function: IRFunction,
    loop: LoopInfo,
    condition_body: str,
    condition_memory: int,
    definitions: dict[int, IRInstruction],
    definition_sites: dict[int, tuple[str, int, IRInstruction]],
    blocks: dict[str, IRBasicBlock],
) -> tuple[LoopCarriedRecurrenceInfo, ...]:
    if len(loop.preheaders) != 1 or not loop.backedges:
        return ()
    preheader = loop.preheaders[0]
    preheader_block = blocks[preheader]
    if (
        not preheader_block.instructions
        or preheader_block.instructions[-1].opcode is not IROpcode.JUMP
        or preheader_block.instructions[-1].targets != (loop.header,)
    ):
        return ()

    register_types = _register_types(function)
    escaped_memories = {
        instruction.memory
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode
        in {
            IROpcode.ADDRESS_OF,
            IROpcode.AGGREGATE_ADDRESS_OF,
            IROpcode.AGGREGATE_FIELD_ADDRESS,
        }
        and instruction.memory is not None
    }
    proven: list[LoopCarriedRecurrenceInfo] = []

    for memory_object in function.memory_objects:
        memory = memory_object.index
        if (
            memory_object.length != 1
            or not memory_object.mutable
            or memory_object.element_type not in {IRType.I64, IRType.F64, IRType.TRYTE}
            or memory in escaped_memories
        ):
            continue
        initializers = [
            instruction
            for instruction in preheader_block.instructions
            if instruction.opcode is IROpcode.STORE and instruction.memory == memory
        ]
        if len(initializers) != 1 or len(initializers[0].operands) != 2:
            continue
        initial_value = _constant_register(initializers[0].operands[1], definitions)
        initial_register = _copy_source(initializers[0].operands[1], definitions)
        if (
            isinstance(initial_value, bool)
            or not isinstance(initial_value, (int, float))
            or register_types.get(initial_register) is not memory_object.element_type
            or memory_object.element_type is IRType.I64 and not isinstance(initial_value, int)
        ):
            continue

        events: dict[str, list[tuple[int, str, str, int | None]]] = {}
        rejected = False
        expected_kind: str | None = None
        expected_operation: str | None = None
        expected_step: int | None = None
        for block_name in loop.blocks:
            block = blocks[block_name]
            for index, instruction in enumerate(block.instructions):
                if instruction.opcode is not IROpcode.STORE or instruction.memory != memory:
                    continue
                update = _recurrence_update(
                    memory,
                    block_name,
                    index,
                    instruction,
                    definitions,
                    definition_sites,
                    register_types,
                    memory_object.element_type,
                )
                if update is None:
                    rejected = True
                    break
                kind, operation, step = update
                if expected_kind is None:
                    expected_kind, expected_operation, expected_step = kind, operation, step
                elif kind != expected_kind or operation != expected_operation or step != expected_step:
                    rejected = True
                    break
                events.setdefault(block_name, []).append((index, kind, operation, step))
            if rejected:
                break
        if rejected or not events:
            continue

        # The induction cell used by the counted-loop condition is the only
        # state classified as an induction variable. Other proven recurrences
        # are scalar reductions; their legality is handled separately below.
        if memory == condition_memory:
            if expected_kind != "INDUCTION":
                continue
        elif expected_kind != "REDUCTION":
            continue

        pending = deque([(condition_body, 0)])
        visited: set[tuple[str, int]] = set()
        backedge_states: set[tuple[str, int]] = set()
        opaque_path = False
        while pending:
            block_name, update_count = pending.popleft()
            state = (block_name, min(update_count, 2))
            if state in visited:
                continue
            visited.add(state)
            block = blocks[block_name]
            for index, _kind, _operation, _step in events.get(block_name, ()):
                if index < len(block.instructions) - 1:
                    update_count = min(2, update_count + 1)
            if not block.instructions:
                opaque_path = True
                continue
            terminator = block.instructions[-1]
            if terminator.opcode is IROpcode.RETURN:
                continue
            if terminator.opcode not in {IROpcode.JUMP, IROpcode.BRANCH3} or not terminator.targets:
                opaque_path = True
                continue
            for target in terminator.targets:
                if target == loop.header:
                    backedge_states.add((block_name, update_count))
                elif target in loop.blocks:
                    pending.append((target, update_count))

        if (
            opaque_path
            or not backedge_states
            or any(count != 1 for _tail, count in backedge_states)
        ):
            continue

        update_sites = tuple(
            sorted(
                (block_name, index)
                for block_name, items in events.items()
                for index, _kind, _operation, _step in items
            )
        )
        proven.append(
            LoopCarriedRecurrenceInfo(
                loop_header=loop.header,
                memory=memory,
                condition_memory=condition_memory,
                condition_relation="LESS_THAN",
                element_type=memory_object.element_type,
                kind=expected_kind or "UNKNOWN",
                operation=expected_operation or "unknown",
                initial_value=initial_value,
                step=expected_step,
                update_sites=update_sites,
                backedge_updates=tuple(sorted(backedge_states)),
                ordered=expected_kind == "REDUCTION",
            )
        )
    return tuple(proven)


def _recognize_ordered_reduction(
    function: IRFunction,
    loop: LoopInfo,
    body: str,
    definitions: dict[int, IRInstruction],
    definition_sites: dict[int, tuple[str, int, IRInstruction]],
    blocks: dict[str, IRBasicBlock],
) -> tuple[ReductionInfo, ...]:
    if len(loop.preheaders) != 1 or len(loop.backedges) != 1 or loop.backedges[0] != body:
        return ()
    preheader = loop.preheaders[0]
    preheader_block = blocks[preheader]
    body_block = blocks[body]
    if (
        not preheader_block.instructions
        or preheader_block.instructions[-1].opcode is not IROpcode.JUMP
        or preheader_block.instructions[-1].targets != (loop.header,)
        or not body_block.instructions
        or body_block.instructions[-1].opcode is not IROpcode.JUMP
        or body_block.instructions[-1].targets != (loop.header,)
    ):
        return ()
    loop_instructions = [
        instruction
        for name in loop.blocks
        for instruction in blocks[name].instructions
    ]
    if any(
        instruction.opcode in {IROpcode.REFERENCE_STORE, IROpcode.SLICE_STORE}
        or (
            instruction.opcode is IROpcode.CALL
            and builtin_effect(instruction.callee)
            not in {BuiltinEffect.PURE, BuiltinEffect.READ_ONLY}
        )
        for instruction in loop_instructions
    ):
        return ()

    result: list[ReductionInfo] = []
    for memory in function.memory_objects:
        if memory.element_type not in {IRType.TRYTE, IRType.I64, IRType.F64} or memory.length != 1:
            continue
        memory_index = memory.index
        initializers = [
            instruction
            for instruction in preheader_block.instructions
            if instruction.opcode is IROpcode.STORE and instruction.memory == memory_index
        ]
        stores = [
            (block.name, index, instruction)
            for block in function.blocks
            for index, instruction in enumerate(block.instructions)
            if instruction.opcode is IROpcode.STORE and instruction.memory == memory_index
        ]
        loads = [
            (block.name, index, instruction)
            for block in function.blocks
            if block.name in loop.blocks
            for index, instruction in enumerate(block.instructions)
            if instruction.opcode is IROpcode.LOAD and instruction.memory == memory_index
        ]
        updates = [item for item in stores if item[0] == body]
        if len(initializers) != 1 or len(stores) != 2 or len(updates) != 1 or len(loads) != 1:
            continue
        initializer = initializers[0]
        update_block, store_index, store = updates[0]
        if len(initializer.operands) != 2 or len(store.operands) != 2:
            continue
        update_register = _copy_source(store.operands[1], definitions)
        update = definitions.get(update_register)
        update_site = definition_sites.get(update_register)
        if (
            update is None
            or update.opcode
            not in {
                IROpcode.ADD,
                IROpcode.MULTIPLY,
                IROpcode.MINIMUM,
                IROpcode.MAXIMUM,
            }
            or len(update.operands) != 2
            or (
                update.opcode in {IROpcode.MINIMUM, IROpcode.MAXIMUM}
                and memory.element_type is not IRType.TRYTE
            )
            or update_site is None
            or update_site[0] != update_block
            or update_site[1] >= store_index
        ):
            continue
        accumulator_operands: list[tuple[int, IRInstruction, tuple[str, int, IRInstruction]]] = []
        recurrence_operands: list[int] = []
        for operand in update.operands:
            source = _copy_source(operand, definitions)
            definition = definitions.get(source)
            site = definition_sites.get(source)
            if definition is not None and definition.opcode is IROpcode.LOAD and definition.memory == memory_index:
                if site is not None:
                    accumulator_operands.append((source, definition, site))
            else:
                recurrence_operands.append(operand)
        if len(accumulator_operands) != 1 or len(recurrence_operands) != 1:
            continue
        load_register, _, load_site = accumulator_operands[0]
        if load_site[0] != update_block or load_site[1] >= update_site[1]:
            continue
        initial_register = initializer.operands[1]
        operation = {
            IROpcode.ADD: "add",
            IROpcode.MULTIPLY: "multiply",
            IROpcode.MINIMUM: "tritwise_minimum",
            IROpcode.MAXIMUM: "tritwise_maximum",
        }[update.opcode]
        result.append(
            ReductionInfo(
                loop_header=loop.header,
                accumulator_memory=memory_index,
                element_type=memory.element_type,
                operation=operation,
                initial_register=initial_register,
                initial_constant=_constant_register(initial_register, definitions),
                recurrence_register=recurrence_operands[0],
                update_block=update_block,
                update_index=store_index,
            )
        )
    return tuple(result)


def analyze_loop_facts(
    function: IRFunction,
) -> LoopAnalysisResult:
    """Derive conservative CFG recurrence facts and narrower vector-range proofs.

    Recurrences require a constant preheader initializer, non-escaping scalar
    storage, typed updates, and exactly one update on every reachable backedge.
    Bounds proofs retain the stricter canonical single-body and immutable-vector
    requirements; recurrence recognition alone never marks an access safe.
    """

    blocks = {block.name: block for block in function.blocks}
    definitions = {
        result: instruction
        for block in function.blocks
        for instruction in block.instructions
        for result in instruction.results
    }
    memory_by_index = {memory.index: memory for memory in function.memory_objects}
    parameters = {parameter.register: parameter for parameter in function.parameters}
    definition_sites = {
        result: (block.name, index, instruction)
        for block in function.blocks
        for index, instruction in enumerate(block.instructions)
        for result in instruction.results
    }
    loops = discover_loop_info(function)
    proofs: list[VectorBoundsProof] = []
    inductions: list[InductionInfo] = []
    recurrences: list[LoopCarriedRecurrenceInfo] = []
    range_facts: list[RangeFact] = []
    reductions: list[ReductionInfo] = []

    for loop in loops:
        condition = _condition_body_for_less_than(
            function, loop.header, definitions
        )
        if (
            condition is None
            or condition.body not in loop.blocks
            or condition.join not in loop.blocks
            or any(arm not in loop.blocks for arm in condition.relation_arms)
        ):
            continue
        condition_memory = _induction_condition_memory(
            function, loop, definitions, definition_sites
        )
        if condition_memory is None:
            continue
        recurrences.extend(
            _prove_loop_carried_recurrences(
                function,
                loop,
                condition.body,
                condition_memory,
                definitions,
                definition_sites,
                blocks,
            )
        )
        induction = _recognize_induction(
            function, loop, condition.body, definitions, blocks
        )
        if induction is None:
            continue
        reductions.extend(
            _recognize_ordered_reduction(
                function,
                loop,
                condition.body,
                definitions,
                definition_sites,
                blocks,
            )
        )

        branch = blocks[loop.header].instructions[-1]
        comparison = definitions.get(branch.operands[0])
        assert comparison is not None
        compare_block, _, _ = definition_sites.get(
            comparison.results[0], (None, None, None)
        ) if comparison.results else (None, None, None)
        if compare_block != loop.header:
            continue
        index_register = _copy_source(comparison.operands[0], definitions)
        index_load = definitions.get(index_register)
        memory = memory_by_index.get(induction.memory)
        if (
            index_load is None
            or index_load.opcode is not IROpcode.LOAD
            or index_load.memory != induction.memory
            or memory is None
            or memory.element_type is not IRType.I64
            or memory.length != 1
        ):
            continue
        index_site = definition_sites.get(index_register)
        if index_site is None or index_site[0] != loop.header:
            continue

        length_register = _copy_source(comparison.operands[1], definitions)
        length_call = definitions.get(length_register)
        if (
            length_call is None
            or length_call.opcode is not IROpcode.CALL
            or length_call.callee not in {f"{kind}_vector_len" for kind in _VECTOR_ELEMENT_TYPES}
            or len(length_call.operands) != 1
        ):
            continue
        vector_register = _copy_source(length_call.operands[0], definitions)
        length_site = definition_sites.get(length_register)
        if (
            length_site is None
            or length_site[0] not in {*loop.preheaders, loop.header}
        ):
            continue
        vector_parameter = parameters.get(vector_register)
        if (
            vector_parameter is None
            or vector_parameter.type is not IRType.REFERENCE
            or vector_parameter.reference_target is not IRType.VECTOR
            or vector_parameter.reference_mutable
        ):
            continue
        element_name = length_call.callee.removesuffix("_vector_len")
        element_type = _VECTOR_ELEMENT_TYPES[element_name]

        condition_stores = [
            (block.name, index)
            for block in function.blocks
            for index, instruction in enumerate(block.instructions)
            if instruction.opcode is IROpcode.STORE
            and instruction.memory == condition.condition_memory
        ]
        expected_condition_stores = [
            (arm, index)
            for arm in condition.relation_arms
            for index, instruction in enumerate(blocks[arm].instructions)
            if instruction.opcode is IROpcode.STORE
            and instruction.memory == condition.condition_memory
        ]
        if len(condition_stores) != 3 or sorted(condition_stores) != sorted(expected_condition_stores):
            continue

        loop_instructions = [
            instruction
            for name in loop.blocks
            for instruction in blocks[name].instructions
        ]
        if any(
            instruction.opcode in {IROpcode.REFERENCE_STORE, IROpcode.SLICE_STORE}
            for instruction in loop_instructions
        ):
            continue
        if any(
            instruction.opcode is IROpcode.CALL
            and builtin_effect(instruction.callee)
            not in {BuiltinEffect.PURE, BuiltinEffect.READ_ONLY}
            for instruction in loop_instructions
        ):
            continue

        vector_get = f"{element_name}_vector_get"
        body_block = blocks[condition.body]
        induction_stores = [
            index
            for index, instruction in enumerate(body_block.instructions)
            if instruction.opcode is IROpcode.STORE
            and instruction.memory == induction.memory
        ]
        if len(induction_stores) != 1:
            continue
        inductions.append(induction)
        for access_index, instruction in enumerate(body_block.instructions):
            if (
                instruction.opcode is not IROpcode.CALL
                or instruction.callee != vector_get
                or len(instruction.operands) != 2
                or _copy_source(instruction.operands[0], definitions) != vector_register
            ):
                continue
            access_index_register = _copy_source(instruction.operands[1], definitions)
            access_index_load = definitions.get(access_index_register)
            access_load_site = definition_sites.get(access_index_register)
            if (
                access_index_load is None
                or access_index_load.opcode is not IROpcode.LOAD
                or access_index_load.memory != induction.memory
                or access_load_site is None
                or access_load_site[0] != condition.body
                or access_load_site[1] >= access_index
                or access_index >= induction_stores[0]
            ):
                continue
            fact = RangeFact(
                induction_memory=induction.memory,
                lower_bound=induction.initial_value,
                step=induction.step,
                upper_bound_vector=vector_register,
                upper_bound_exclusive=True,
                access_block=condition.body,
                access_index=access_index,
            )
            range_facts.append(fact)
            proofs.append(
                VectorBoundsProof(
                    loop=loop,
                    induction=induction,
                    range_fact=fact,
                    element_type=element_type,
                    vector_register=vector_register,
                    access_block=condition.body,
                    access_index=access_index,
                )
            )

    checks_seen = sum(
        1
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode is IROpcode.CALL
        and instruction.callee is not None
        and instruction.callee.endswith("_vector_get")
    )
    proven_sites = {(proof.access_block, proof.access_index) for proof in proofs}
    proven_count = len(proven_sites)
    eliminated_count = sum(
        1
        for block in function.blocks
        for instruction in block.instructions
        if instruction.opcode is IROpcode.CALL
        and instruction.callee is not None
        and instruction.callee.endswith("_vector_get")
        and instruction.bounds_proven
    )
    metrics = LoopAnalysisMetrics(
        loops_seen=len(loops),
        inductions_recognized=len({item.memory for item in inductions}),
        range_facts_derived=proven_count,
        bounds_checks_seen=checks_seen,
        bounds_checks_proven_safe=proven_count,
        bounds_checks_eliminated=eliminated_count,
        bounds_checks_retained=checks_seen - eliminated_count,
    )
    reduction_metrics = ReductionAnalysisMetrics(
        loops_seen=len(loops),
        reductions_recognized=len(reductions),
        add_reductions=sum(item.operation == "add" for item in reductions),
        multiply_reductions=sum(item.operation == "multiply" for item in reductions),
        min_reductions=sum(item.operation == "tritwise_minimum" for item in reductions),
        max_reductions=sum(item.operation == "tritwise_maximum" for item in reductions),
        unsupported_reductions=None,
    )
    return LoopAnalysisResult(
        loops=loops,
        inductions=tuple(inductions),
        recurrences=tuple(recurrences),
        range_facts=tuple(range_facts),
        proofs=tuple(proofs),
        metrics=metrics,
        reductions=tuple(reductions),
        reduction_metrics=reduction_metrics,
    )


def analyze_canonical_vector_get_ranges(
    function: IRFunction,
) -> tuple[VectorBoundsProof, ...]:
    """Return only accesses with a complete loop-derived safety proof."""

    return analyze_loop_facts(function).proofs


def mark_proven_vector_bounds_checks(function: IRFunction) -> IRFunction:
    """Attach compiler-only proof facts to accepted canonical vector gets."""

    proofs = analyze_canonical_vector_get_ranges(function)
    if not proofs:
        return function
    proven = {(proof.access_block, proof.access_index) for proof in proofs}
    return replace(
        function,
        blocks=tuple(
            replace(
                block,
                instructions=tuple(
                    replace(instruction, bounds_proven=True)
                    if (block.name, index) in proven
                    else instruction
                    for index, instruction in enumerate(block.instructions)
                ),
            )
            for block in function.blocks
        ),
    )


def hoist_readonly_vector_length_queries(function: IRFunction) -> tuple[IRFunction, int]:
    """Hoist immutable parameter length queries from canonical loop headers."""
    cfg = ControlFlowGraph.build(function)
    dom_tree = DominatorTree.build(cfg)
    blocks_by_name = {block.name: block for block in function.blocks}
    parameters_by_register = {
        parameter.register: parameter for parameter in function.parameters
    }
    back_edges = [
        (tail, head)
        for tail in sorted(cfg.nodes)
        for head in sorted(cfg.nodes[tail].successors)
        if dom_tree.dominates(head, tail)
    ]
    if not back_edges:
        return function, 0

    moves: dict[tuple[str, int], str] = {}
    moved_calls: set[IRInstruction] = set()
    vector_length_builtins = {
        "tryte_vector_len",
        "i64_vector_len",
        "f64_vector_len",
    }

    for tail, header in back_edges:
        loop_blocks = {header, tail}
        worklist = [tail]
        while worklist:
            current = worklist.pop()
            for predecessor in sorted(cfg.nodes[current].predecessors, reverse=True):
                if (
                    predecessor not in loop_blocks
                    and dom_tree.dominates(header, predecessor)
                ):
                    loop_blocks.add(predecessor)
                    worklist.append(predecessor)

        loop_calls = [
            instruction
            for name in loop_blocks
            for instruction in blocks_by_name[name].instructions
            if instruction.opcode is IROpcode.CALL
        ]
        if any(
            builtin_effect(instruction.callee)
            not in {BuiltinEffect.PURE, BuiltinEffect.READ_ONLY}
            for instruction in loop_calls
        ):
            continue
        if any(
            instruction.opcode in {IROpcode.REFERENCE_STORE, IROpcode.SLICE_STORE}
            for name in loop_blocks
            for instruction in blocks_by_name[name].instructions
        ):
            continue

        outside_predecessors = sorted(
            predecessor
            for predecessor in cfg.nodes[header].predecessors
            if predecessor not in loop_blocks
        )
        if len(outside_predecessors) != 1:
            continue
        preheader = outside_predecessors[0]
        if not dom_tree.dominates(preheader, header):
            continue
        preheader_instructions = blocks_by_name[preheader].instructions
        if (
            not preheader_instructions
            or preheader_instructions[-1].opcode is not IROpcode.JUMP
            or preheader_instructions[-1].targets != (header,)
        ):
            continue

        header_block = blocks_by_name[header]
        for index, instruction in enumerate(header_block.instructions):
            if (
                instruction in moved_calls
                or instruction.opcode is not IROpcode.CALL
                or instruction.callee not in vector_length_builtins
                or len(instruction.operands) != 1
                or len(instruction.results) != 1
            ):
                continue
            parameter = parameters_by_register.get(instruction.operands[0])
            if (
                parameter is None
                or parameter.type is not IRType.REFERENCE
                or parameter.reference_mutable
            ):
                continue
            moves[(header, index)] = preheader
            moved_calls.add(instruction)

    if not moves:
        return function, 0

    removed: dict[str, set[int]] = {}
    insertions: dict[str, list[IRInstruction]] = {}
    for (source, index), destination in moves.items():
        removed.setdefault(source, set()).add(index)
        insertions.setdefault(destination, []).append(
            blocks_by_name[source].instructions[index]
        )

    updated_blocks: list[IRBasicBlock] = []
    for block in function.blocks:
        retained = [
            instruction
            for index, instruction in enumerate(block.instructions)
            if index not in removed.get(block.name, set())
        ]
        hoisted = insertions.get(block.name)
        if hoisted:
            terminator = retained.pop()
            retained.extend(hoisted)
            retained.append(terminator)
        updated_blocks.append(replace(block, instructions=tuple(retained)))

    return replace(function, blocks=tuple(updated_blocks)), len(moves)

# -----------------------------------------------------------------------------
# Milestone 0.87: Loop Invariant Code Motion (LICM)
# -----------------------------------------------------------------------------

def run_ssa_licm(
    ssa_fn: SSAFunction,
    *,
    hoist_pure_instructions: bool = True,
) -> Tuple[SSAFunction, int]:
    """Hoist safe invariants through a proven natural-loop preheader."""
    cfg = _cfg_from_ssa(ssa_fn)
    dom_tree = DominatorTree.build(cfg)

    back_edges: List[Tuple[str, str]] = []
    for node_name in sorted(cfg.nodes):
        node = cfg.nodes[node_name]
        for succ in sorted(node.successors):
            if dom_tree.dominates(succ, node_name):
                back_edges.append((node_name, succ))

    if not back_edges:
        return ssa_fn, 0

    hoisted_count = 0
    ssa_block_dict = {b.name: b for b in ssa_fn.blocks}
    parameter_values = {parameter.value.name for parameter in ssa_fn.parameters}

    for tail_name, head_name in back_edges:
        loop_blocks: Set[str] = {head_name, tail_name}
        worklist = [tail_name]
        while worklist:
            curr = worklist.pop()
            if curr in cfg.nodes:
                for pred in sorted(cfg.nodes[curr].predecessors, reverse=True):
                    if pred not in loop_blocks and dom_tree.dominates(head_name, pred):
                        loop_blocks.add(pred)
                        worklist.append(pred)

        loop_instructions = [
            inst
            for block_name in loop_blocks
            if block_name in ssa_block_dict
            for inst in ssa_block_dict[block_name].instructions
        ]
        calls_are_read_only = all(
            inst.opcode is not IROpcode.CALL
            or builtin_effect(
                str(inst.immediate) if inst.immediate is not None else None
            )
            in {BuiltinEffect.PURE, BuiltinEffect.READ_ONLY}
            for inst in loop_instructions
        )
        loop_has_store = any(
            inst.opcode
            in {
                IROpcode.REFERENCE_STORE,
                IROpcode.SLICE_STORE,
            }
            for inst in loop_instructions
        )

        defined_in_loop = {
            inst.result.name
            for b_name in loop_blocks
            if b_name in ssa_block_dict
            for inst in ssa_block_dict[b_name].instructions
            if inst.result is not None
        } | {
            phi.target.name
            for b_name in loop_blocks
            if b_name in ssa_block_dict
            for phi in ssa_block_dict[b_name].phis
        }

        invariant_defs: Set[str] = set()
        hoistable_insts: List[Tuple[str, SSAInstruction]] = []

        changed = True
        while changed:
            changed = False
            for b_name in sorted(loop_blocks):
                block = ssa_block_dict[b_name]
                for inst in block.instructions:
                    is_safe_call = (
                        inst.opcode is IROpcode.CALL
                        and calls_are_read_only
                        and not loop_has_store
                        and builtin_effect(
                            str(inst.immediate) if inst.immediate is not None else None
                        ) is BuiltinEffect.READ_ONLY
                        and inst.immediate
                        in {
                            "tryte_vector_len",
                            "i64_vector_len",
                            "f64_vector_len",
                        }
                        and len(inst.operands) == 1
                        and inst.operands[0].type is IRType.REFERENCE
                        and not inst.operands[0].reference_mutable
                        and inst.operands[0].name in parameter_values
                    )
                    is_safe_pure_op = (
                        hoist_pure_instructions
                        and
                        inst.opcode in _PURE_REMOVABLE_OPCODES
                        and inst.opcode
                        not in {
                            IROpcode.JUMP,
                            IROpcode.BRANCH3,
                            IROpcode.CALL,
                            IROpcode.STORE,
                            IROpcode.LOAD,
                        }
                    )
                    if (
                        inst.result is not None
                        and inst.result.name not in invariant_defs
                        and (is_safe_call or is_safe_pure_op)
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

        pre_header_candidates = sorted(
            p
            for p in cfg.nodes[head_name].predecessors
            if p not in loop_blocks
        ) if head_name in cfg.nodes else []
        if len(pre_header_candidates) != 1:
            continue
        target_pre_header = pre_header_candidates[0]
        if not dom_tree.dominates(target_pre_header, head_name):
            continue

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
            result_types=ssa_fn.result_types,
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
        result_types=ssa_fn.result_types,
    ), reductions_count
