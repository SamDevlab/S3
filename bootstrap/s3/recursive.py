"""Bounded recursive/nested compiler-data substrate for hosted components.

Nodes use stable integer identities and insertion-ordered edges. Traversal is
iterative and cycle-aware, so recursive graphs are representable without
depending on Python's call stack or allowing an unbounded walk.
"""

from __future__ import annotations

from dataclasses import dataclass


class RecursiveStructureError(RuntimeError):
    """Raised for invalid node identities or duplicate graph edges."""


class RecursiveCapacityError(RecursiveStructureError):
    """Raised when a node or edge bound would be exceeded."""


class RecursiveDepthError(RecursiveStructureError):
    """Raised when traversal exceeds the configured path-depth bound."""


@dataclass(frozen=True, slots=True)
class RecursiveNode:
    """Immutable snapshot of one node and its current child identities."""

    node_id: int
    value: object
    children: tuple[int, ...]


class RecursiveNodeStore:
    """A bounded deterministic graph store suitable for compiler structures."""

    def __init__(self, *, max_nodes: int, max_edges: int, max_depth: int = 1024) -> None:
        for name, value in (
            ("max_nodes", max_nodes),
            ("max_edges", max_edges),
            ("max_depth", max_depth),
        ):
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError(f"{name} must be an integer")
            if value <= 0:
                raise ValueError(f"{name} must be positive")
        self.max_nodes = max_nodes
        self.max_edges = max_edges
        self.max_depth = max_depth
        self._values: dict[int, object] = {}
        self._children: dict[int, list[int]] = {}
        self._next_id = 0
        self._edge_count = 0

    @property
    def node_count(self) -> int:
        return len(self._values)

    @property
    def edge_count(self) -> int:
        return self._edge_count

    def create(self, value: object) -> int:
        if self.node_count >= self.max_nodes:
            raise RecursiveCapacityError("recursive node capacity reached")
        node_id = self._next_id
        self._next_id += 1
        self._values[node_id] = value
        self._children[node_id] = []
        return node_id

    def node(self, node_id: int) -> RecursiveNode:
        self._require_node(node_id)
        return RecursiveNode(
            node_id,
            self._values[node_id],
            tuple(self._children[node_id]),
        )

    def add_edge(self, parent: int, child: int) -> None:
        self._require_node(parent)
        self._require_node(child)
        if child in self._children[parent]:
            raise RecursiveStructureError("recursive edge already exists")
        if self.edge_count >= self.max_edges:
            raise RecursiveCapacityError("recursive edge capacity reached")
        self._children[parent].append(child)
        self._edge_count += 1

    def walk(self, root: int) -> tuple[int, ...]:
        """Return insertion-ordered depth-first reachability without recursion."""

        self._require_node(root)
        visited: set[int] = set()
        pending: list[tuple[int, int]] = [(root, 0)]
        ordered: list[int] = []
        while pending:
            node_id, depth = pending.pop()
            if node_id in visited:
                continue
            if depth > self.max_depth:
                raise RecursiveDepthError("recursive traversal depth limit reached")
            visited.add(node_id)
            ordered.append(node_id)
            for child in reversed(self._children[node_id]):
                pending.append((child, depth + 1))
        return tuple(ordered)

    def _require_node(self, node_id: int) -> None:
        if isinstance(node_id, bool) or not isinstance(node_id, int):
            raise RecursiveStructureError("node identity must be an integer")
        if node_id not in self._values:
            raise RecursiveStructureError(f"unknown recursive node {node_id}")
