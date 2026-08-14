"""Conservative native proof for redundant register initialization checks.

The proof is recomputed from validated Assembly and is intentionally not part
of the public Assembly representation.  An absent, malformed, or unsupported
case returns no safe sites, leaving the native checked path unchanged.
"""

from __future__ import annotations

from ...assembly import AssemblyFunction, AssemblyOpcode
from .liveness import instruction_use_def


RegisterReadSite = tuple[str, int, int]


def _successors(function: AssemblyFunction) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for block in function.blocks:
        if not block.instructions:
            result[block.label] = ()
            continue
        terminator = block.instructions[-1]
        if terminator.opcode in {AssemblyOpcode.TJMP, AssemblyOpcode.TBR3}:
            result[block.label] = tuple(terminator.labels)
        else:
            result[block.label] = ()
    return result


def _reachable(function: AssemblyFunction, successors: dict[str, tuple[str, ...]]) -> set[str]:
    if not function.blocks:
        return set()
    result: set[str] = set()
    pending = [function.blocks[0].label]
    while pending:
        label = pending.pop()
        if label in result:
            continue
        result.add(label)
        pending.extend(successors.get(label, ()))
    return result


def _predecessors(
    successors: dict[str, tuple[str, ...]],
    reachable: set[str],
) -> dict[str, set[str]]:
    result = {label: set() for label in reachable}
    for source, targets in successors.items():
        if source not in reachable:
            continue
        for target in targets:
            if target in reachable:
                result[target].add(source)
    return result


def _address_taken_registers(function: AssemblyFunction) -> set[int]:
    result: set[int] = set()
    for block in function.blocks:
        for instruction in block.instructions:
            if instruction.opcode is AssemblyOpcode.TADDR and instruction.memory is None:
                result.update(instruction.registers[1:])
    return result


def _definite_register_states(
    function: AssemblyFunction,
    successors: dict[str, tuple[str, ...]],
    reachable: set[str],
) -> tuple[dict[str, set[int]], dict[str, set[int]]]:
    """Compute registers initialized on every reachable path into each block."""

    if not function.blocks or not reachable:
        return {}, {}
    predecessors = _predecessors(successors, reachable)
    entry = function.blocks[0].label
    register_in: dict[str, set[int]] = {}
    register_out: dict[str, set[int]] = {}
    pending = [entry]
    queued = {entry}
    iterations = 0

    while pending:
        label = pending.pop(0)
        queued.discard(label)
        iterations += 1
        if iterations > max(1000, len(reachable) * len(reachable) * 8):
            raise ValueError("register initialization fixed point did not converge")
        block = next(block for block in function.blocks if block.label == label)
        if label == entry:
            current = {parameter.register for parameter in function.parameters}
        else:
            incoming = [
                register_out[pred]
                for pred in predecessors[label]
                if pred in register_out
            ]
            # A predecessor that has not been visited yet is absent only
            # during the fixed-point walk.  Later predecessor updates are
            # intersected and requeue successors before the result is used.
            if incoming:
                current = set.intersection(*(set(values) for values in incoming))
            else:
                current = set()
        output = set(current)
        for instruction in block.instructions:
            _, writes = instruction_use_def(instruction)
            output.update(writes)
        changed = register_in.get(label) != current or register_out.get(label) != output
        register_in[label] = current
        register_out[label] = output
        if changed:
            for target in successors.get(label, ()):
                if target in reachable and target not in queued:
                    pending.append(target)
                    queued.add(target)
    return register_in, register_out


def proven_initialized_register_reads(
    function: AssemblyFunction,
) -> frozenset[RegisterReadSite]:
    """Return only reads whose initialized-marker failure is unreachable.

    The predicate is deliberately narrower than general register liveness:
    references, slices, calls, address-taken registers, unknown opcodes, and
    incomplete CFG states produce no proof.
    """

    if function.external or not function.blocks:
        return frozenset()
    try:
        successors = _successors(function)
        reachable = _reachable(function, successors)
        if not reachable:
            return frozenset()
        if function.reference_targets or function.slice_registers:
            return frozenset()
        if any(
            instruction.opcode is AssemblyOpcode.TCALL
            for block in function.blocks
            for instruction in block.instructions
        ):
            return frozenset()
        register_in, _ = _definite_register_states(function, successors, reachable)
        address_taken = _address_taken_registers(function)
        result: set[RegisterReadSite] = set()
        for block in function.blocks:
            if block.label not in reachable:
                continue
            state = set(register_in.get(block.label, ()))
            for index, instruction in enumerate(block.instructions):
                reads, writes = instruction_use_def(instruction)
                for register in reads:
                    if register in state and register not in address_taken:
                        result.add((block.label, index, register))
                state.update(writes)
        return frozenset(result)
    except (KeyError, StopIteration, TypeError, ValueError):
        # The native optimization must never become a new failure mode.
        return frozenset()
