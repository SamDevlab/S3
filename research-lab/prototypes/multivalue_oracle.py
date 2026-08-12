"""Exact tiny oracle for multiple value-placement problems with shared capacity."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from lagrangian_capacity import MultiValueProblem
from materialization_cut import Placement, assignment_cost


@dataclass(frozen=True, slots=True)
class MultiValueExactResult:
    cost: int
    assignments: dict[str, dict[str, Placement]]
    assignments_examined: int
    feasible_assignments: int


def solve_exact_multivalue(
    problem: MultiValueProblem,
    *,
    max_free_bits: int = 24,
) -> MultiValueExactResult:
    """Enumerate all tiny shared-capacity placement assignments exactly."""

    decisions: list[tuple[str, str]] = []
    base: dict[str, dict[str, Placement]] = {}
    for value_name, value_problem in problem.values.items():
        assignment = dict(value_problem.pinned)
        base[value_name] = assignment
        for node in problem.nodes:
            if node not in value_problem.pinned:
                decisions.append((value_name, node))

    if len(decisions) > max_free_bits:
        raise ValueError(
            f"oracle refuses {len(decisions)} free bits; limit is {max_free_bits}"
        )

    best_cost: int | None = None
    best_assignments: dict[str, dict[str, Placement]] | None = None
    examined = 0
    feasible_count = 0

    for choices in product((Placement.FLEXIBLE, Placement.MEMORY), repeat=len(decisions)):
        assignments = {value: dict(assignment) for value, assignment in base.items()}
        for (value_name, node), placement in zip(decisions, choices, strict=True):
            assignments[value_name][node] = placement
        examined += 1

        occupancy = {node: 0 for node in problem.nodes}
        for assignment in assignments.values():
            for node, placement in assignment.items():
                if placement is Placement.FLEXIBLE:
                    occupancy[node] += 1
        if any(occupancy[node] > problem.capacities[node] for node in problem.nodes):
            continue

        feasible_count += 1
        cost = sum(
            assignment_cost(problem.values[value_name], assignments[value_name])
            for value_name in problem.values
        )
        if best_cost is None or cost < best_cost:
            best_cost = cost
            best_assignments = {
                value: dict(assignment) for value, assignment in assignments.items()
            }

    if best_cost is None or best_assignments is None:
        raise ValueError("no feasible assignment")

    return MultiValueExactResult(
        cost=best_cost,
        assignments=best_assignments,
        assignments_examined=examined,
        feasible_assignments=feasible_count,
    )
