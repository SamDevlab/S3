"""Self-checking entry point for the initial S3 mathematical prototypes."""

from __future__ import annotations

import random

from cfg import Block, CFG, Instruction
from combinatorial_checks import find_matroid_violation, find_submodularity_violation
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


def demo_combinatorial_checks() -> None:
    ground = ("a", "b", "c")

    # Uniform matroid U(2,3): every subset with at most two elements is independent.
    assert find_matroid_violation(ground, lambda subset: len(subset) <= 2) is None

    # Deliberately violate heredity to prove the counterexample finder fires.
    bad_independent = lambda subset: subset != frozenset({"a"})
    assert find_matroid_violation(ground, bad_independent) is not None

    # Concave cardinality cap is submodular.
    assert (
        find_submodularity_violation(ground, lambda subset: min(len(subset), 2))
        is None
    )

    # Pure complementarity/synergy between a and b violates submodularity.
    def synergy(subset: frozenset[str]) -> float:
        return 1.0 if {"a", "b"}.issubset(subset) else 0.0

    assert find_submodularity_violation(ground, synergy) is not None


def main() -> None:
    validate_lattice_laws()
    validate_transfer_monotonicity()
    demo_liveness()
    demo_cut_matches_oracle()
    randomized_cut_oracle_crosscheck()
    demo_combinatorial_checks()
    print("residence_lattice=PASS")
    print("liveness=PASS")
    print("mincut_vs_exact_oracle=PASS")
    print("matroid_counterexample_tool=PASS")
    print("submodularity_counterexample_tool=PASS")
    print("OK")


if __name__ == "__main__":
    main()
