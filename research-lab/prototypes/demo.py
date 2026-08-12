"""Self-checking entry point for the initial S3 mathematical prototypes."""

from __future__ import annotations

import random

from cfg import Block, CFG, Instruction
from exact_oracle import solve_exact
from liveness import analyze_liveness
from materialization_cut import (
    MaterializationProblem,
    Placement,
    TransitionCost,
    UnaryCost,
    solve_min_cut,
)
from residence_lattice import validate_lattice_laws, validate_transfer_monotonicity


def demo_liveness() -> None:
    cfg = CFG.make(
        "entry",
        [
            Block.make(
                "entry",
                [Instruction.make("x = input", defs=["x"])],
                successors=["left", "right"],
            ),
            Block.make(
                "left",
                [Instruction.make("left work")],
                successors=["join"],
            ),
            Block.make(
                "right",
                [Instruction.make("right work")],
                successors=["join"],
            ),
            Block.make(
                "join",
                [Instruction.make("use x", uses=["x"])],
            ),
        ],
    )
    result = analyze_liveness(cfg)
    assert "x" in result.blocks["entry"].live_out
    assert "x" in result.blocks["left"].live_in
    assert "x" in result.blocks["right"].live_in
    assert "x" in result.blocks["join"].live_in


def demo_cut_matches_oracle() -> None:
    problem = MaterializationProblem.make(
        ["entry", "left", "right", "join"],
        unary={
            "left": UnaryCost(flexible=0, memory=1),
            "right": UnaryCost(flexible=0, memory=1),
        },
        transitions=[
            TransitionCost("entry", "left", materialize=3, recover=5),
            TransitionCost("entry", "right", materialize=2, recover=5),
            TransitionCost("left", "join", materialize=4, recover=2),
            TransitionCost("right", "join", materialize=4, recover=2),
        ],
        pinned={
            "entry": Placement.FLEXIBLE,
            "join": Placement.MEMORY,
        },
    )
    cut = solve_min_cut(problem)
    oracle = solve_exact(problem)
    assert cut.cost == oracle.solution.cost, (cut, oracle)


def randomized_cut_oracle_crosscheck(seed: int = 0x533, cases: int = 200) -> None:
    rng = random.Random(seed)
    for case in range(cases):
        node_count = rng.randint(1, 7)
        nodes = tuple(f"n{i}" for i in range(node_count))
        unary = {
            node: UnaryCost(rng.randint(0, 6), rng.randint(0, 6))
            for node in nodes
        }
        transitions: list[TransitionCost] = []
        for source in nodes:
            for target in nodes:
                if source == target or rng.random() >= 0.22:
                    continue
                transitions.append(
                    TransitionCost(
                        source,
                        target,
                        materialize=rng.randint(0, 7),
                        recover=rng.randint(0, 7),
                    )
                )
        pinned: dict[str, Placement] = {}
        for node in nodes:
            roll = rng.random()
            if roll < 0.10:
                pinned[node] = Placement.FLEXIBLE
            elif roll < 0.20:
                pinned[node] = Placement.MEMORY

        problem = MaterializationProblem.make(
            nodes,
            unary=unary,
            transitions=transitions,
            pinned=pinned,
        )
        cut = solve_min_cut(problem)
        oracle = solve_exact(problem)
        assert cut.cost == oracle.solution.cost, {
            "case": case,
            "cut": cut,
            "oracle": oracle,
            "problem": problem,
        }


def main() -> None:
    validate_lattice_laws()
    validate_transfer_monotonicity()
    demo_liveness()
    demo_cut_matches_oracle()
    randomized_cut_oracle_crosscheck()
    print("residence_lattice=PASS")
    print("liveness=PASS")
    print("mincut_vs_exact_oracle=PASS")
    print("OK")


if __name__ == "__main__":
    main()
