"""Conservative, diagnostic-only reference provenance and lifetime analysis.

This analysis deliberately does not authorize optimizer transformations. Any
uncertain origin, call, or unsupported reference use is represented as unknown.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .alias_analysis import AliasResult
from .builtin_effects import BuiltinEffect, builtin_effect
from .ir import IRFunction, IRInstruction, IRModule, IROpcode, IRType


class EscapeStatus(str, Enum):
    NO_ESCAPE = "NO_ESCAPE"
    ESCAPES = "ESCAPES"
    UNKNOWN = "UNKNOWN"


class ReferenceEffect(str, Enum):
    NONE = "none"
    READ = "read"
    WRITE = "write"
    READ_WRITE = "read_write"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ReferenceRegion:
    """Logical storage identity; never a runtime or machine address."""

    storage_class: str
    root: int | str
    projection: tuple[object, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "storage_class": self.storage_class,
            "root": self.root,
            "projection": list(self.projection),
        }


@dataclass(frozen=True, slots=True)
class ReferenceFact:
    register: int
    origins: tuple[ReferenceRegion, ...]
    origin_unknown: bool
    mutable: bool
    escape: EscapeStatus
    live_blocks: tuple[str, ...]
    read_uses: int
    write_uses: int
    unknown_uses: int

    def to_dict(self) -> dict[str, object]:
        return {
            "register": self.register,
            "origins": [origin.to_dict() for origin in self.origins],
            "origin_unknown": self.origin_unknown,
            "mutable": self.mutable,
            "escape": self.escape.value,
            "live_blocks": list(self.live_blocks),
            "read_uses": self.read_uses,
            "write_uses": self.write_uses,
            "unknown_uses": self.unknown_uses,
        }


@dataclass(frozen=True, slots=True)
class ReferenceAnalysisReport:
    function: str
    complete: bool
    incomplete_reasons: tuple[str, ...]
    references: tuple[ReferenceFact, ...]
    effects: tuple[tuple[str, int], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "function": self.function,
            "complete": self.complete,
            "incomplete_reasons": list(self.incomplete_reasons),
            "references": [fact.to_dict() for fact in self.references],
            "effects": dict(self.effects),
        }


def alias_regions(left: ReferenceRegion, right: ReferenceRegion) -> AliasResult:
    """Compare logical regions without treating distinct dynamic indices as disjoint."""

    local_classes = {"frame-memory", "frame-register", "aggregate-temporary"}
    if left.storage_class in local_classes and right.storage_class in local_classes:
        if left.storage_class != right.storage_class or left.root != right.root:
            return AliasResult.NO_ALIAS
    elif left.storage_class == "external" and right.storage_class in local_classes:
        return AliasResult.NO_ALIAS
    elif right.storage_class == "external" and left.storage_class in local_classes:
        return AliasResult.NO_ALIAS
    elif left.storage_class != right.storage_class or left.root != right.root:
        return AliasResult.MAY_ALIAS

    if left.projection == right.projection:
        return AliasResult.MUST_ALIAS
    if (
        len(left.projection) == len(right.projection) == 2
        and left.projection[0] == right.projection[0] == "element"
        and isinstance(left.projection[1], int)
        and not isinstance(left.projection[1], bool)
        and isinstance(right.projection[1], int)
        and not isinstance(right.projection[1], bool)
    ):
        return AliasResult.NO_ALIAS
    return AliasResult.MAY_ALIAS


def analyze_references(function: IRFunction) -> ReferenceAnalysisReport:
    """Summarize reference origins, CFG liveness, effects, and escapes.

    Completeness is scoped to the reference facts modeled here. This first
    version understands local address formation, aggregate field projection,
    moves, loads/stores, returns, and closed-world builtin effects. Unknown
    calls and unsupported reference producers fail closed.
    """

    registers = {register.index: register for register in function.registers}
    parameter_registers = {parameter.register for parameter in function.parameters}
    reference_registers = {
        index for index, register in registers.items()
        if register.type is IRType.REFERENCE
    } | {
        parameter.register for parameter in function.parameters
        if parameter.type is IRType.REFERENCE
    }
    origins: dict[int, set[ReferenceRegion]] = {index: set() for index in reference_registers}
    origin_unknown: set[int] = set()
    pending_moves: dict[int, int] = {}
    reasons: set[str] = set()
    escape_events: set[int] = set()
    unknown_escape: set[int] = set()
    read_uses: dict[int, int] = {index: 0 for index in reference_registers}
    write_uses: dict[int, int] = {index: 0 for index in reference_registers}
    unknown_uses: dict[int, int] = {index: 0 for index in reference_registers}
    effect_counts = {effect.value: 0 for effect in ReferenceEffect}
    if function.external:
        reasons.add("external function body is unavailable")

    # All formal reference parameters can alias one another or external state.
    for parameter in function.parameters:
        if parameter.type is IRType.REFERENCE:
            origins[parameter.register].add(
                ReferenceRegion("external", "parameter-space", ("parameter", parameter.register))
            )

    memory_ids = {memory.index for memory in function.memory_objects}
    constant_registers = {
        instruction.result: instruction.immediate
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CONST
        and instruction.result is not None
        and isinstance(instruction.immediate, int)
        and not isinstance(instruction.immediate, bool)
    }

    def mark_unknown(register: int, reason: str) -> None:
        if register in reference_registers:
            origin_unknown.add(register)
            reasons.add(reason)

    for block in function.blocks:
        for instruction in block.instructions:
            for result in instruction.results:
                if result not in reference_registers or result in parameter_registers:
                    continue
                if instruction.opcode is IROpcode.ADDRESS_OF:
                    if instruction.memory is not None:
                        if instruction.memory not in memory_ids:
                            mark_unknown(result, "address_of references an unknown memory object")
                            continue
                        projection: tuple[object, ...] = ()
                        if instruction.operands:
                            index_register = instruction.operands[0]
                            constant = constant_registers.get(index_register)
                            projection = ("element", constant if constant is not None else ("ssa", index_register))
                        origins[result].add(ReferenceRegion("frame-memory", instruction.memory, projection))
                    elif instruction.operands:
                        origins[result].add(ReferenceRegion("frame-register", instruction.operands[0]))
                    else:
                        mark_unknown(result, "address_of has no modeled storage root")
                elif instruction.opcode is IROpcode.AGGREGATE_ADDRESS_OF:
                    origins[result].add(ReferenceRegion("aggregate-temporary", result))
                elif instruction.opcode is IROpcode.AGGREGATE_FIELD_ADDRESS:
                    if instruction.operands:
                        pending_moves[result] = instruction.operands[0]
                    else:
                        mark_unknown(result, "aggregate field address has no base reference")
                elif instruction.opcode is IROpcode.MOVE and instruction.operands:
                    pending_moves[result] = instruction.operands[0]
                else:
                    mark_unknown(result, f"unsupported reference producer: {instruction.opcode.value}")

    # Propagate origin sets through SSA moves and aggregate field projections.
    for _ in range(len(pending_moves) + 1):
        changed = False
        for result, source in pending_moves.items():
            if source not in reference_registers:
                mark_unknown(result, "reference move source is not a reference")
                continue
            before = len(origins[result])
            if result in origins and source in origins:
                for region in origins[source]:
                    if any(
                        instruction.opcode is IROpcode.AGGREGATE_FIELD_ADDRESS
                        and result in instruction.results
                        for instruction in function.instructions
                    ):
                        path = next(
                            (
                                instruction.aggregate_field_path
                                for instruction in function.instructions
                                if result in instruction.results
                                and instruction.opcode is IROpcode.AGGREGATE_FIELD_ADDRESS
                            ),
                            (),
                        )
                        origins[result].add(
                            ReferenceRegion(region.storage_class, region.root, (*region.projection, "field", *path))
                        )
                    else:
                        origins[result].add(region)
                if source in origin_unknown:
                    origin_unknown.add(result)
            changed |= len(origins[result]) != before
        if not changed:
            break
    for result, source in pending_moves.items():
        if not origins[result] and result not in origin_unknown:
            mark_unknown(result, "reference origin could not be resolved through the CFG")
        if source in origin_unknown:
            origin_unknown.add(result)

    # Any reference value whose provenance is incomplete poisons downstream copies.
    changed = True
    while changed:
        changed = False
        for result, source in pending_moves.items():
            if source in origin_unknown and result not in origin_unknown:
                origin_unknown.add(result)
                changed = True

    cfg_successors: dict[str, set[str]] = {block.name: set() for block in function.blocks}
    known_blocks = set(cfg_successors)
    block_use: dict[str, set[int]] = {block.name: set() for block in function.blocks}
    block_def: dict[str, set[int]] = {block.name: set() for block in function.blocks}
    for block in function.blocks:
        # Parameters are defined at function entry, outside the basic blocks.
        # Keeping the local def set empty records their uses for CFG propagation.
        defined: set[int] = set()
        for instruction in block.instructions:
            for operand in instruction.operands:
                if operand in reference_registers and operand not in defined:
                    block_use[block.name].add(operand)
            for result in instruction.results:
                if result in reference_registers:
                    block_def[block.name].add(result)
                    defined.add(result)
            if instruction.opcode in {IROpcode.JUMP, IROpcode.BRANCH3}:
                for target in instruction.targets:
                    if target in known_blocks:
                        cfg_successors[block.name].add(target)
                    else:
                        reasons.add(f"CFG target {target!r} is not present in the function")

    live_in = {block: set() for block in known_blocks}
    live_out = {block: set() for block in known_blocks}
    changed = True
    while changed:
        changed = False
        for block in reversed(function.blocks):
            outgoing = set().union(*(live_in[target] for target in cfg_successors[block.name])) if cfg_successors[block.name] else set()
            incoming = block_use[block.name] | (outgoing - block_def[block.name])
            if outgoing != live_out[block.name] or incoming != live_in[block.name]:
                live_out[block.name] = outgoing
                live_in[block.name] = incoming
                changed = True

    live_blocks: dict[int, set[str]] = {index: set() for index in reference_registers}
    for block in function.blocks:
        for register in live_in[block.name] | live_out[block.name] | block_use[block.name] | block_def[block.name]:
            live_blocks[register].add(block.name)

    for block in function.blocks:
        for instruction in block.instructions:
            refs = [operand for operand in instruction.operands if operand in reference_registers]
            effect = ReferenceEffect.NONE
            if instruction.opcode in {IROpcode.REFERENCE_LOAD, IROpcode.SLICE_LOAD, IROpcode.AGGREGATE_FIELD_LOAD, IROpcode.SLICE_LENGTH}:
                effect = ReferenceEffect.READ
            elif instruction.opcode in {IROpcode.REFERENCE_STORE, IROpcode.SLICE_STORE}:
                effect = ReferenceEffect.WRITE
            elif instruction.opcode is IROpcode.CALL and refs:
                builtin = builtin_effect(instruction.callee)
                if builtin is BuiltinEffect.PURE:
                    effect = ReferenceEffect.NONE
                elif builtin is BuiltinEffect.READ_ONLY:
                    effect = ReferenceEffect.READ
                elif builtin is BuiltinEffect.MUTATES:
                    effect = ReferenceEffect.READ_WRITE
                else:
                    effect = ReferenceEffect.UNKNOWN
                # Effect class alone does not prove that a callee does not retain
                # a reference. Parameter-level no-escape summaries are not present.
                unknown_escape.update(refs)
                reasons.add("reference passed to a call without a parameter-level no-escape summary")
            elif refs and instruction.opcode in {IROpcode.MOVE, IROpcode.RETURN, IROpcode.AGGREGATE_FIELD_ADDRESS, IROpcode.ADDRESS_OF}:
                effect = ReferenceEffect.NONE
            elif refs:
                effect = ReferenceEffect.UNKNOWN
            effect_counts[effect.value] += int(bool(refs) or effect is not ReferenceEffect.NONE)

            for register in refs:
                if effect in {ReferenceEffect.READ, ReferenceEffect.READ_WRITE}:
                    read_uses[register] += 1
                if effect in {ReferenceEffect.WRITE, ReferenceEffect.READ_WRITE}:
                    write_uses[register] += 1
                if effect is ReferenceEffect.UNKNOWN:
                    unknown_uses[register] += 1
                if instruction.opcode is IROpcode.RETURN:
                    escape_events.add(register)
                elif instruction.opcode is IROpcode.CALL:
                    unknown_escape.add(register)
                elif instruction.opcode is IROpcode.STORE:
                    # A reference stored in memory is not followed by this local analysis.
                    if register in instruction.operands:
                        unknown_escape.add(register)
                        reasons.add("reference stored in memory without a storage-content summary")
                elif instruction.opcode is IROpcode.REFERENCE_STORE:
                    # The first operand is the destination reference; a reference value
                    # in a later operand is an unsupported reference-containing store.
                    if instruction.operands.index(register) > 0:
                        unknown_escape.add(register)
                        reasons.add("reference value stored through a reference without a content summary")

    # Returning/passing a copy also affects the reference from which it was derived.
    changed = True
    while changed:
        changed = False
        for result, source in pending_moves.items():
            if result in escape_events and source not in escape_events:
                escape_events.add(source)
                changed = True
            if result in unknown_escape and source not in unknown_escape:
                unknown_escape.add(source)
                changed = True

    facts: list[ReferenceFact] = []
    for index in sorted(reference_registers):
        reg_info = registers.get(index)
        if reg_info is not None and reg_info.reference_mutable:
            mutable = True
        else:
            mutable = next(
                (parameter.reference_mutable for parameter in function.parameters if parameter.register == index),
                False,
            )
        if index in escape_events:
            escape = EscapeStatus.ESCAPES
        elif index in unknown_escape or index in origin_unknown or function.external:
            escape = EscapeStatus.UNKNOWN
        else:
            escape = EscapeStatus.NO_ESCAPE
        facts.append(
            ReferenceFact(
                index,
                tuple(sorted(origins[index], key=lambda region: (region.storage_class, str(region.root), repr(region.projection)))),
                index in origin_unknown,
                mutable,
                escape,
                tuple(sorted(live_blocks[index])),
                read_uses[index],
                write_uses[index],
                unknown_uses[index],
            )
        )
    return ReferenceAnalysisReport(
        function.name,
        not reasons,
        tuple(sorted(reasons)),
        tuple(facts),
        tuple(sorted(effect_counts.items())),
    )


def analyze_module_references(module: IRModule) -> tuple[ReferenceAnalysisReport, ...]:
    """Analyze each function independently; calls remain unknown interprocedurally."""

    return tuple(analyze_references(function) for function in module.functions)
