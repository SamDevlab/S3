"""Tiny dependency-free CFG model for S3 research experiments.

This file deliberately does not import production S3 compiler modules.  It is a
stable mathematical playground that later adapters may populate from real S3 IR.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping


Value = str
BlockName = str


@dataclass(frozen=True, slots=True)
class Instruction:
    """Minimal use/def view of an instruction."""

    name: str
    uses: frozenset[Value] = frozenset()
    defs: frozenset[Value] = frozenset()

    @classmethod
    def make(
        cls,
        name: str,
        *,
        uses: Iterable[Value] = (),
        defs: Iterable[Value] = (),
    ) -> "Instruction":
        return cls(name=name, uses=frozenset(uses), defs=frozenset(defs))


@dataclass(frozen=True, slots=True)
class Block:
    name: BlockName
    instructions: tuple[Instruction, ...]
    successors: tuple[BlockName, ...] = ()

    @classmethod
    def make(
        cls,
        name: BlockName,
        instructions: Iterable[Instruction],
        *,
        successors: Iterable[BlockName] = (),
    ) -> "Block":
        return cls(name, tuple(instructions), tuple(successors))


@dataclass(frozen=True, slots=True)
class CFG:
    """Immutable control-flow graph with deterministic block order."""

    entry: BlockName
    blocks: Mapping[BlockName, Block]
    order: tuple[BlockName, ...]

    @classmethod
    def make(cls, entry: BlockName, blocks: Iterable[Block]) -> "CFG":
        ordered = tuple(blocks)
        mapping = {block.name: block for block in ordered}
        if len(mapping) != len(ordered):
            raise ValueError("duplicate block name")
        if entry not in mapping:
            raise ValueError(f"unknown entry block: {entry}")
        for block in ordered:
            for successor in block.successors:
                if successor not in mapping:
                    raise ValueError(
                        f"block {block.name!r} references unknown successor {successor!r}"
                    )
        return cls(entry=entry, blocks=mapping, order=tuple(b.name for b in ordered))

    def predecessors(self) -> dict[BlockName, tuple[BlockName, ...]]:
        result: dict[BlockName, list[BlockName]] = {name: [] for name in self.order}
        for name in self.order:
            for successor in self.blocks[name].successors:
                result[successor].append(name)
        return {name: tuple(preds) for name, preds in result.items()}

    def values(self) -> frozenset[Value]:
        values: set[Value] = set()
        for name in self.order:
            for instruction in self.blocks[name].instructions:
                values.update(instruction.uses)
                values.update(instruction.defs)
        return frozenset(values)

    def reachable(self) -> frozenset[BlockName]:
        seen: set[BlockName] = set()
        stack = [self.entry]
        while stack:
            name = stack.pop()
            if name in seen:
                continue
            seen.add(name)
            # Reverse so traversal remains deterministic in declared successor order.
            stack.extend(reversed(self.blocks[name].successors))
        return frozenset(seen)
