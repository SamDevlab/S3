from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from bootstrap.s3.initialization import (
    InitializationState,
    _constant_index,
    _constant_values,
    _initial_state,
    _join_maps,
    _predecessors,
    _reachable,
    _successors,
    _transfer,
)
from bootstrap.s3.ir import IROpcode
from bootstrap.s3.pipeline import compile_source


def _state_for_access(function, state, instruction, constants):
    assert instruction.memory is not None
    memory = next(item for item in function.memory_objects if item.index == instruction.memory)
    index = _constant_index(instruction, constants)
    if index is not None and 0 <= index < memory.length:
        return state[(memory.index, index)]
    cells = [state[(memory.index, offset)] for offset in range(memory.length)]
    if cells and all(item is InitializationState.INITIALIZED for item in cells):
        return InitializationState.INITIALIZED
    if cells and all(item is InitializationState.UNINITIALIZED for item in cells):
        return InitializationState.UNINITIALIZED
    return InitializationState.MAYBE_INITIALIZED


def analyze(source_path: Path, output_path: Path) -> None:
    source = source_path.read_text(encoding="utf-8")
    compilation = compile_source(source, "O1")
    all_accesses = []
    function_summaries = []
    for function in compilation.ir.functions:
        if function.external:
            continue
        successors = _successors(function)
        predecessors = _predecessors(function, successors)
        reachable = _reachable(successors)
        constants = _constant_values(function)
        memory_lengths = {memory.index: memory.length for memory in function.memory_objects}
        initial = _initial_state(function)
        entries = {}
        exits = {}
        changed = True
        while changed:
            changed = False
            for block in function.blocks:
                if block.name not in reachable:
                    continue
                incoming = [
                    exits[pred]
                    for pred in sorted(predecessors[block.name])
                    if pred in exits
                ]
                if block.name == "entry":
                    incoming.insert(0, initial)
                if not incoming:
                    continue
                entry = _join_maps(incoming)
                exit_state = _transfer(entry, block.instructions, constants, memory_lengths)
                if entries.get(block.name) != entry:
                    entries[block.name] = entry
                    changed = True
                if exits.get(block.name) != exit_state:
                    exits[block.name] = exit_state
                    changed = True
        summary = Counter()
        state = Counter()
        for block in function.blocks:
            if block.name not in entries:
                continue
            current = dict(entries[block.name])
            for position, instruction in enumerate(block.instructions):
                if instruction.opcode in {IROpcode.LOAD, IROpcode.STORE}:
                    memory = next(item for item in function.memory_objects if item.index == instruction.memory)
                    access_state = _state_for_access(function, current, instruction, constants)
                    if instruction.opcode is IROpcode.LOAD or not memory.mutable:
                        kind = "LOAD" if instruction.opcode is IROpcode.LOAD else "IMMUTABLE_STORE"
                        key = f"{kind}:{access_state.value}"
                        summary[key] += 1
                        state[access_state.value] += 1
                        all_accesses.append(
                            {
                                "function": function.name,
                                "block": block.name,
                                "position": position,
                                "kind": kind,
                                "state": access_state.value,
                                "memory": instruction.memory,
                            }
                        )
                current = _transfer(current, (instruction,), constants, memory_lengths)
        function_summaries.append(
            {
                "function": function.name,
                "access_summary": dict(sorted(summary.items())),
                "state_summary": dict(sorted(state.items())),
            }
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {
                "source": str(source_path),
                "optimization": "O1",
                "functions": function_summaries,
                "accesses": all_accesses,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: p5_initialization_semantics.py SOURCE OUTPUT")
    analyze(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve())
