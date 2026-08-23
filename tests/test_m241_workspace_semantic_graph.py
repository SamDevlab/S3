from __future__ import annotations

import pytest

from bootstrap.s3.workspace_semantic import (
    SymbolKind,
    WorkspaceSemanticError,
    WorkspaceSemanticGraph,
    WorkspaceSemanticIndex,
)


LIB = (
    "module lib\n"
    "export record Point:\n"
    "    x: tryte\n"
    "export fn make() -> Point:\n"
    "    return Point(x=1)\n"
)
MAIN = (
    "module main\n"
    "from lib import Point\n"
    "from lib import make\n"
    "fn main() -> tryte:\n"
    "    point: Point = make()\n"
    "    return point.x\n"
)


def test_workspace_semantic_graph_is_open_order_independent() -> None:
    first = WorkspaceSemanticGraph.from_sources({"main.s3": MAIN, "lib.s3": LIB})
    second = WorkspaceSemanticGraph.from_sources({"lib.s3": LIB, "main.s3": MAIN})

    assert first.resolution_digest == second.resolution_digest
    assert tuple(str(item) for item in first.ordered_modules) == ("lib", "main")
    assert first.resolve("main", "make").identity.canonical == "lib::value::make"
    assert first.type_identity("main", "Point").canonical == "lib::type::Point"
    assert first.symbol("lib", "Point").kind is SymbolKind.TYPE


def test_workspace_semantic_graph_rejects_duplicate_and_conflicting_symbols() -> None:
    with pytest.raises(WorkspaceSemanticError, match="duplicate function"):
        WorkspaceSemanticGraph.from_sources(
            {
                "main.s3": "module main\nfn same() -> tryte:\n    return 0\nfn same() -> tryte:\n    return 1\n",
            }
        )
    with pytest.raises(WorkspaceSemanticError, match="ambiguous"):
        WorkspaceSemanticGraph.from_sources(
            {
                "main.s3": "module main\nfn same() -> tryte:\n    return 0\nrecord same:\n    value: tryte\n",
            }
        )


def test_private_and_unknown_imports_fail_closed() -> None:
    with pytest.raises(WorkspaceSemanticError, match="private"):
        WorkspaceSemanticGraph.from_sources(
            {
                "main.s3": "module main\nfrom lib import hidden\nfn main() -> tryte:\n    return hidden()\n",
                "lib.s3": "module lib\nfn hidden() -> tryte:\n    return 0\n",
            }
        )
    with pytest.raises(WorkspaceSemanticError, match="does not define"):
        WorkspaceSemanticGraph.from_sources(
            {
                "main.s3": "module main\nfrom lib import missing\nfn main() -> tryte:\n    return 0\n",
                "lib.s3": "module lib\nexport fn present() -> tryte:\n    return 0\n",
            }
        )


def test_incremental_index_allows_open_order_and_invalidates_dependents() -> None:
    index = WorkspaceSemanticIndex()
    first = index.open_document("main.s3", MAIN)
    assert first.graph.complete is False
    assert first.graph.unresolved_imports
    second = index.open_document("lib.s3", LIB)
    assert second.graph.complete is True
    assert tuple(str(item) for item in second.invalidated_modules) == ("lib", "main")

    changed_lib = LIB.replace("x: tryte", "x: i64")
    update = index.open_document("lib.s3", changed_lib)
    assert tuple(str(item) for item in update.changed_modules) == ("lib",)
    assert tuple(str(item) for item in update.invalidated_modules) == ("lib", "main")
    assert index.graph.resolution_digest != second.graph.resolution_digest


def test_incremental_index_rejects_last_close_and_normalizes_paths() -> None:
    index = WorkspaceSemanticIndex()
    with pytest.raises(WorkspaceSemanticError, match="must not contain"):
        index.open_document("src/../main.s3", MAIN)
    index.open_document("main.s3", MAIN)
    with pytest.raises(WorkspaceSemanticError, match="last document"):
        index.close_document("main.s3")
