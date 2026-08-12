"""Exhaustive oracle for tiny binary materialization-placement problems."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from materialization_cut import (
    MaterializationProblem,
    Placement,
    PlacementSolution,
    assignment_cost,
)


@dataclass(frozen=True, slots=True)
class OracleResult:
    solution: PlacementSolution
    assignments_examined: int


def solve_exact(
    problem: MaterializationProblem,
    *,
    max_free_nodes: int = 22,
) -> OracleResult:
    """Enumerate every feasible binary assignment.

    This is intentionally exponential and is meant only as a research oracle.
    """

    free_nodes = tuple(node for node in problem.nodes if node not in problem.pinned)
    if len(free_nodes) > max_free_nodes:
        raise ValueError(
            f"oracle refuses {len(free_nodes)} free nodes; limit is {max_free_nodes}"
        )

    base = dict(problem.pinned)
    best_cost: int | None = None
    best_assignment: dict[str, Placement] | None = None
    examined = 0

    for choices in product((Placement.FLEXIBLE, Placement.MEMORY), repeat=len(free_nodes)):
        assignment = dict(base)
        assignment.update(zip(free_nodes, choices, strict=True))
        examined += 1
        cost = assignment_cost(problem, assignment)
        # Deterministic tie-breaking follows the declared free-node order and the
        # enumeration order FLEXIBLE before MEMORY.
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_assignment = assignment

    assert best_cost is not None
    assert best_assignment is not None
    ordered_assignment = {node: best_assignment[node] for node in problem.nodes}
    return OracleResult(
        solution=PlacementSolution(best_cost, ordered_assignment),
        assignments_examined=examined,
    )
