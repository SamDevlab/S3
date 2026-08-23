"""M2.54 bounded recursive and nested compiler-data contracts."""

from __future__ import annotations

import pytest

from bootstrap.s3.recursive import (
    RecursiveCapacityError,
    RecursiveDepthError,
    RecursiveNodeStore,
    RecursiveStructureError,
)


def test_recursive_store_preserves_deterministic_nested_order() -> None:
    store = RecursiveNodeStore(max_nodes=5, max_edges=6)
    root = store.create("root")
    left = store.create("left")
    right = store.create("right")
    leaf = store.create("leaf")
    store.add_edge(root, left)
    store.add_edge(root, right)
    store.add_edge(left, leaf)
    assert store.walk(root) == (root, left, leaf, right)
    assert store.node(root).children == (left, right)


def test_recursive_store_terminates_on_cycles_with_one_visit_per_node() -> None:
    store = RecursiveNodeStore(max_nodes=3, max_edges=3)
    first = store.create("first")
    second = store.create("second")
    third = store.create("third")
    store.add_edge(first, second)
    store.add_edge(second, third)
    store.add_edge(third, first)
    assert store.walk(first) == (first, second, third)


def test_recursive_store_fails_closed_on_node_and_edge_capacity() -> None:
    store = RecursiveNodeStore(max_nodes=2, max_edges=1)
    first = store.create("first")
    second = store.create("second")
    with pytest.raises(RecursiveCapacityError):
        store.create("third")
    store.add_edge(first, second)
    with pytest.raises(RecursiveCapacityError):
        store.add_edge(second, first)


def test_recursive_store_bounds_depth_without_python_recursion() -> None:
    store = RecursiveNodeStore(max_nodes=4, max_edges=3, max_depth=2)
    nodes = [store.create(index) for index in range(4)]
    for parent, child in zip(nodes, nodes[1:]):
        store.add_edge(parent, child)
    with pytest.raises(RecursiveDepthError):
        store.walk(nodes[0])


def test_recursive_store_rejects_unknown_and_duplicate_edges() -> None:
    store = RecursiveNodeStore(max_nodes=2, max_edges=2)
    first = store.create("first")
    second = store.create("second")
    store.add_edge(first, second)
    with pytest.raises(RecursiveStructureError):
        store.add_edge(first, second)
    with pytest.raises(RecursiveStructureError):
        store.add_edge(first, 99)
