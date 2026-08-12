"""Research prototype: Lagrangian relaxation of shared FLEXIBLE capacity.

This explores Zettel S3-ZK-0015.  It is NOT a register allocator.

Each logical value has its own binary materialization problem.  Values are
coupled only by a simplified per-program-point capacity:

    number of values assigned FLEXIBLE at point p <= capacity[p]

Non-negative integer prices are added to FLEXIBLE unary costs.  For fixed
prices the problem decomposes into independent min-cut solves.  A subgradient-
style update raises prices where occupancy exceeds capacity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from materialization_cut import (
    MaterializationProblem,
    Placement,
    PlacementSolution,
    UnaryCost,
    assignment_cost,
    solve_min_cut,
)


@dataclass(frozen=True, slots=True)
class MultiValueProblem:
    values: Mapping[str, MaterializationProblem]
    capacities: Mapping[str, int]
    nodes: tuple[str, ...]

    @classmethod
    def make(
        cls,
        values: Mapping[str, MaterializationProblem],
        capacities: Mapping[str, int],
    ) -> "MultiValueProblem":
        if not values:
            raise ValueError("multi-value problem requires at least one value")
        ordered_values = dict(values)
        first = next(iter(ordered_values.values()))
        nodes = first.nodes
        for name, problem in ordered_values.items():
            if problem.nodes != nodes:
                raise ValueError(f"value {name!r} uses a different node order")
        capacity_map = {node: int(capacities.get(node, len(ordered_values))) for node in nodes}
        for node, capacity in capacity_map.items():
            if capacity < 0:
                raise ValueError(f"negative capacity at {node!r}")
            forced_flexible = sum(
                value_problem.pinned.get(node) is Placement.FLEXIBLE
                for value_problem in ordered_values.values()
            )
            if forced_flexible > capacity:
                raise ValueError(
                    f"infeasible hard pins at {node!r}: {forced_flexible} > {capacity}"
                )
        return cls(ordered_values, capacity_map, nodes)


@dataclass(frozen=True, slots=True)
class LagrangianIteration:
    iteration: int
    step: int
    prices: dict[str, int]
    occupancy: dict[str, int]
    dual_bound: int
    original_cost: int
    feasible: bool


@dataclass(frozen=True, slots=True)
class LagrangianResult:
    best_dual_bound: int
    best_feasible_cost: int | None
    best_feasible_assignments: dict[str, dict[str, Placement]] | None
    final_prices: dict[str, int]
    history: tuple[LagrangianIteration, ...]


def _adjusted_problem(
    problem: MaterializationProblem,
    prices: Mapping[str, int],
) -> MaterializationProblem:
    unary = {
        node: UnaryCost(
            flexible=problem.unary[node].flexible + prices[node],
            memory=problem.unary[node].memory,
        )
        for node in problem.nodes
    }
    return MaterializationProblem.make(
        problem.nodes,
        unary=unary,
        transitions=problem.transitions,
        pinned=problem.pinned,
    )


def solve_lagrangian(
    problem: MultiValueProblem,
    *,
    iterations: int = 100,
    initial_step: int = 4,
    decay_every: int = 20,
) -> LagrangianResult:
    """Run a deterministic integer-price subgradient experiment.

    This is intentionally simple.  It exists to measure whether decomposition
    is useful before investing in a sophisticated dual optimizer.
    """

    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if initial_step <= 0 or decay_every <= 0:
        raise ValueError("step parameters must be positive")

    prices = {node: 0 for node in problem.nodes}
    best_dual: int | None = None
    best_feasible_cost: int | None = None
    best_feasible_assignments: dict[str, dict[str, Placement]] | None = None
    history: list[LagrangianIteration] = []

    for iteration in range(iterations):
        occupancy = {node: 0 for node in problem.nodes}
        assignments: dict[str, dict[str, Placement]] = {}
        adjusted_total = 0
        original_total = 0

        for value_name, value_problem in problem.values.items():
            adjusted = _adjusted_problem(value_problem, prices)
            solution: PlacementSolution = solve_min_cut(adjusted)
            assignments[value_name] = dict(solution.assignment)
            adjusted_total += solution.cost
            original_total += assignment_cost(value_problem, solution.assignment)
            for node, placement in solution.assignment.items():
                if placement is Placement.FLEXIBLE:
                    occupancy[node] += 1

        dual_bound = adjusted_total - sum(
            prices[node] * problem.capacities[node] for node in problem.nodes
        )
        if best_dual is None or dual_bound > best_dual:
            best_dual = dual_bound

        feasible = all(
            occupancy[node] <= problem.capacities[node] for node in problem.nodes
        )
        if feasible and (
            best_feasible_cost is None or original_total < best_feasible_cost
        ):
            best_feasible_cost = original_total
            best_feasible_assignments = {
                value: dict(assignment) for value, assignment in assignments.items()
            }

        step = max(1, initial_step // (1 + iteration // decay_every))
        history.append(
            LagrangianIteration(
                iteration=iteration,
                step=step,
                prices=dict(prices),
                occupancy=dict(occupancy),
                dual_bound=dual_bound,
                original_cost=original_total,
                feasible=feasible,
            )
        )

        for node in problem.nodes:
            violation = occupancy[node] - problem.capacities[node]
            prices[node] = max(0, prices[node] + step * violation)

    assert best_dual is not None
    return LagrangianResult(
        best_dual_bound=best_dual,
        best_feasible_cost=best_feasible_cost,
        best_feasible_assignments=best_feasible_assignments,
        final_prices=dict(prices),
        history=tuple(history),
    )
