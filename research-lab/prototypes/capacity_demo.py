"""Self-check for the shared-capacity Lagrangian research prototype."""

from __future__ import annotations

from lagrangian_capacity import MultiValueProblem, solve_lagrangian
from materialization_cut import MaterializationProblem, UnaryCost
from multivalue_oracle import solve_exact_multivalue


def symmetric_two_value_case() -> None:
    # Two values both prefer FLEXIBLE at one point, but only one flexible slot is
    # available.  The exact optimum is therefore one FLEXIBLE + one MEMORY.
    one_value = MaterializationProblem.make(
        ["p"],
        unary={"p": UnaryCost(flexible=0, memory=5)},
    )
    problem = MultiValueProblem.make(
        {"a": one_value, "b": one_value},
        {"p": 1},
    )

    exact = solve_exact_multivalue(problem)
    relaxed = solve_lagrangian(
        problem,
        iterations=12,
        initial_step=1,
        decay_every=100,
    )

    assert exact.cost == 5
    # Weak duality: Lagrangian dual bound may never exceed the constrained
    # primal optimum.
    assert relaxed.best_dual_bound <= exact.cost
    # In this symmetric case lambda=5 reaches the exact dual bound even though
    # independent tie-breaking may produce a suboptimal feasible primal point.
    assert relaxed.best_dual_bound == exact.cost
    assert relaxed.best_feasible_cost is None or relaxed.best_feasible_cost >= exact.cost


def main() -> None:
    symmetric_two_value_case()
    print("multi_value_exact_oracle=PASS")
    print("lagrangian_weak_duality=PASS")
    print("lagrangian_exact_dual_bound_on_symmetric_case=PASS")
    print("OK")


if __name__ == "__main__":
    main()
