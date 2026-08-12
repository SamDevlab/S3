"""Backward liveness analysis over the generic research CFG."""

from __future__ import annotations

from dataclasses import dataclass

from cfg import BlockName, CFG, Value


@dataclass(frozen=True, slots=True)
class BlockLiveness:
    use: frozenset[Value]
    defs: frozenset[Value]
    live_in: frozenset[Value]
    live_out: frozenset[Value]


@dataclass(frozen=True, slots=True)
class LivenessResult:
    blocks: dict[BlockName, BlockLiveness]
    iterations: int


def _block_use_def(cfg: CFG) -> tuple[dict[BlockName, set[Value]], dict[BlockName, set[Value]]]:
    uses: dict[BlockName, set[Value]] = {}
    defs: dict[BlockName, set[Value]] = {}

    for name in cfg.order:
        block_use: set[Value] = set()
        block_def: set[Value] = set()
        for instruction in cfg.blocks[name].instructions:
            # A value contributes to USE only when it is read before being defined
            # in this block.
            block_use.update(value for value in instruction.uses if value not in block_def)
            block_def.update(instruction.defs)
        uses[name] = block_use
        defs[name] = block_def

    return uses, defs


def analyze_liveness(cfg: CFG) -> LivenessResult:
    """Compute the least fixed point of standard backward live-variable equations.

    Equations:

        OUT[B] = union(IN[S]) for successors S
        IN[B]  = USE[B] union (OUT[B] - DEF[B])

    The finite powerset domain guarantees termination.  Reverse declared block
    order is only a work-order heuristic; the fixed point must not depend on it.
    """

    uses, defs = _block_use_def(cfg)
    live_in: dict[BlockName, set[Value]] = {name: set() for name in cfg.order}
    live_out: dict[BlockName, set[Value]] = {name: set() for name in cfg.order}

    iterations = 0
    while True:
        iterations += 1
        changed = False
        for name in reversed(cfg.order):
            block = cfg.blocks[name]
            new_out: set[Value] = set()
            for successor in block.successors:
                new_out.update(live_in[successor])
            new_in = uses[name] | (new_out - defs[name])

            if new_out != live_out[name] or new_in != live_in[name]:
                live_out[name] = new_out
                live_in[name] = new_in
                changed = True

        if not changed:
            break

    result = {
        name: BlockLiveness(
            use=frozenset(uses[name]),
            defs=frozenset(defs[name]),
            live_in=frozenset(live_in[name]),
            live_out=frozenset(live_out[name]),
        )
        for name in cfg.order
    }
    return LivenessResult(blocks=result, iterations=iterations)
