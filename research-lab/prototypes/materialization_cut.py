"""Binary materialization-placement experiment solved by s-t min cut.

The model is intentionally restricted to one logical value (or independent
values) with two states at each program point:

    FLEXIBLE  - value need not be canonical in memory
    MEMORY    - canonical memory representation is required/selected

Directed CFG transitions may charge different costs for FLEXIBLE->MEMORY
(materialize/store) and MEMORY->FLEXIBLE (recover/load).  This pairwise binary
energy is representable by directed cut arcs.

Shared register-capacity coupling between multiple values is OUTSIDE this model.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from collections import deque
from typing import Iterable, Mapping


class Placement(Enum):
    FLEXIBLE = 0
    MEMORY = 1


@dataclass(frozen=True, slots=True)
class UnaryCost:
    flexible: int = 0
    memory: int = 0

    def __post_init__(self) -> None:
        if self.flexible < 0 or self.memory < 0:
            raise ValueError("cut prototype requires non-negative unary costs")


@dataclass(frozen=True, slots=True)
class TransitionCost:
    source: str
    target: str
    materialize: int
    recover: int

    def __post_init__(self) -> None:
        if self.materialize < 0 or self.recover < 0:
            raise ValueError("cut prototype requires non-negative transition costs")


@dataclass(frozen=True, slots=True)
class MaterializationProblem:
    nodes: tuple[str, ...]
    unary: Mapping[str, UnaryCost]
    transitions: tuple[TransitionCost, ...]
    pinned: Mapping[str, Placement]

    @classmethod
    def make(
        cls,
        nodes: Iterable[str],
        *,
        unary: Mapping[str, UnaryCost] | None = None,
        transitions: Iterable[TransitionCost] = (),
        pinned: Mapping[str, Placement] | None = None,
    ) -> "MaterializationProblem":
        ordered = tuple(nodes)
        if len(set(ordered)) != len(ordered):
            raise ValueError("duplicate problem node")
        known = set(ordered)
        unary_map = dict(unary or {})
        pinned_map = dict(pinned or {})
        transition_tuple = tuple(transitions)

        unknown_unary = set(unary_map) - known
        unknown_pins = set(pinned_map) - known
        if unknown_unary or unknown_pins:
            raise ValueError(f"unknown nodes in unary/pins: {unknown_unary | unknown_pins}")
        for edge in transition_tuple:
            if edge.source not in known or edge.target not in known:
                raise ValueError(f"transition references unknown node: {edge}")

        return cls(
            nodes=ordered,
            unary={name: unary_map.get(name, UnaryCost()) for name in ordered},
            transitions=transition_tuple,
            pinned=pinned_map,
        )


@dataclass(frozen=True, slots=True)
class PlacementSolution:
    cost: int
    assignment: dict[str, Placement]


@dataclass(slots=True)
class _Edge:
    to: int
    rev: int
    capacity: int


class _Dinic:
    def __init__(self, n: int) -> None:
        self.graph: list[list[_Edge]] = [[] for _ in range(n)]

    def add_edge(self, source: int, target: int, capacity: int) -> None:
        if capacity < 0:
            raise ValueError("negative capacity")
        forward = _Edge(target, len(self.graph[target]), capacity)
        reverse = _Edge(source, len(self.graph[source]), 0)
        self.graph[source].append(forward)
        self.graph[target].append(reverse)

    def max_flow(self, source: int, sink: int) -> int:
        total = 0
        n = len(self.graph)
        while True:
            level = [-1] * n
            level[source] = 0
            queue: deque[int] = deque([source])
            while queue:
                node = queue.popleft()
                for edge in self.graph[node]:
                    if edge.capacity > 0 and level[edge.to] < 0:
                        level[edge.to] = level[node] + 1
                        queue.append(edge.to)
            if level[sink] < 0:
                return total

            it = [0] * n

            def send(node: int, pushed: int) -> int:
                if node == sink:
                    return pushed
                while it[node] < len(self.graph[node]):
                    edge_index = it[node]
                    edge = self.graph[node][edge_index]
                    if edge.capacity > 0 and level[node] + 1 == level[edge.to]:
                        amount = send(edge.to, min(pushed, edge.capacity))
                        if amount:
                            edge.capacity -= amount
                            self.graph[edge.to][edge.rev].capacity += amount
                            return amount
                    it[node] += 1
                return 0

            infinity = 1 << 60
            while True:
                pushed = send(source, infinity)
                if not pushed:
                    break
                total += pushed

    def reachable_from(self, source: int) -> frozenset[int]:
        seen = {source}
        stack = [source]
        while stack:
            node = stack.pop()
            for edge in self.graph[node]:
                if edge.capacity > 0 and edge.to not in seen:
                    seen.add(edge.to)
                    stack.append(edge.to)
        return frozenset(seen)


def assignment_cost(
    problem: MaterializationProblem,
    assignment: Mapping[str, Placement],
) -> int:
    """Evaluate an assignment under exactly the same energy as the cut model."""

    if set(assignment) != set(problem.nodes):
        missing = set(problem.nodes) - set(assignment)
        extra = set(assignment) - set(problem.nodes)
        raise ValueError(f"assignment mismatch; missing={missing}, extra={extra}")

    for node, placement in problem.pinned.items():
        if assignment[node] is not placement:
            raise ValueError(f"assignment violates pin {node}={placement.name}")

    cost = 0
    for node in problem.nodes:
        unary = problem.unary[node]
        cost += unary.flexible if assignment[node] is Placement.FLEXIBLE else unary.memory

    for edge in problem.transitions:
        left = assignment[edge.source]
        right = assignment[edge.target]
        if left is Placement.FLEXIBLE and right is Placement.MEMORY:
            cost += edge.materialize
        elif left is Placement.MEMORY and right is Placement.FLEXIBLE:
            cost += edge.recover
    return cost


def solve_min_cut(problem: MaterializationProblem) -> PlacementSolution:
    """Solve the restricted binary placement problem exactly by s-t min cut."""

    index = {name: position for position, name in enumerate(problem.nodes)}
    source = len(problem.nodes)
    sink = source + 1
    flow = _Dinic(sink + 1)

    finite_total = 0
    for unary in problem.unary.values():
        finite_total += unary.flexible + unary.memory
    for edge in problem.transitions:
        finite_total += edge.materialize + edge.recover
    # Any cut using a forbidden pin must cost more than every finite assignment.
    pin_infinity = finite_total + 1

    for node in problem.nodes:
        i = index[node]
        unary = problem.unary[node]
        flexible_cost = unary.flexible
        memory_cost = unary.memory

        # Source side means FLEXIBLE; sink side means MEMORY.
        # node->sink crosses iff node is FLEXIBLE, therefore charges flexible_cost.
        # source->node crosses iff node is MEMORY, therefore charges memory_cost.
        if problem.pinned.get(node) is Placement.MEMORY:
            flexible_cost += pin_infinity
        elif problem.pinned.get(node) is Placement.FLEXIBLE:
            memory_cost += pin_infinity

        flow.add_edge(i, sink, flexible_cost)
        flow.add_edge(source, i, memory_cost)

    for edge in problem.transitions:
        u = index[edge.source]
        v = index[edge.target]
        # u FLEXIBLE, v MEMORY => u is source-side and v sink-side: u->v crosses.
        flow.add_edge(u, v, edge.materialize)
        # u MEMORY, v FLEXIBLE => v source-side and u sink-side: v->u crosses.
        flow.add_edge(v, u, edge.recover)

    _ = flow.max_flow(source, sink)
    source_side = flow.reachable_from(source)
    assignment = {
        name: (Placement.FLEXIBLE if index[name] in source_side else Placement.MEMORY)
        for name in problem.nodes
    }
    # Re-evaluate rather than trusting max-flow total so pins and model semantics
    # are independently checked.
    cost = assignment_cost(problem, assignment)
    return PlacementSolution(cost=cost, assignment=assignment)
