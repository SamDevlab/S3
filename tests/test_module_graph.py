from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.module_graph import (
    ImportEdge,
    ModuleGraph,
    ModuleId,
    SourceUnit,
    normalize_logical_path,
)


def _unit(path: str, module: str | None = None) -> SourceUnit:
    declared = None if module is None else ModuleId.parse(module)
    return SourceUnit(path, "fn main() -> tryte:\n    return 0\n", declared)


def _semantic_code(error: pytest.ExceptionInfo[SemanticError]) -> DiagnosticCode:
    return error.value.diagnostic_code


def test_module_id_can_be_derived_from_normalized_relative_path() -> None:
    assert normalize_logical_path(r"lib\math.s3") == "lib/math.s3"
    assert str(ModuleId.from_logical_path(r"lib\math.s3")) == "lib.math"
    assert str(ModuleId.from_logical_path("main.s3")) == "main"


def test_module_graph_orders_dependencies_deterministically() -> None:
    main = _unit("src/main.s3", "main")
    math = _unit("src/math.s3", "math")
    util = _unit("src/util.s3", "util")
    imports = (
        ImportEdge(ModuleId.parse("main"), ModuleId.parse("util"), "helper"),
        ImportEdge(ModuleId.parse("util"), ModuleId.parse("math"), "inc"),
    )

    graph = ModuleGraph.build((main, util, math), imports)
    reversed_graph = ModuleGraph.build((math, util, main), imports)

    assert tuple(str(module) for module in graph.ordered_modules) == (
        "math",
        "util",
        "main",
    )
    assert graph.ordered_modules == reversed_graph.ordered_modules
    assert tuple(unit.module_id for unit in graph.units) == graph.ordered_modules


def test_module_graph_rejects_duplicate_modules() -> None:
    with pytest.raises(SemanticError) as error:
        ModuleGraph.build(
            (
                _unit("a.s3", "main"),
                _unit("b.s3", "main"),
            )
        )

    assert _semantic_code(error) is DiagnosticCode.MODULE_DUPLICATE


def test_module_graph_rejects_missing_entry_module() -> None:
    with pytest.raises(SemanticError) as error:
        ModuleGraph.build((_unit("lib.s3", "lib"),), entry_module="main")

    assert _semantic_code(error) is DiagnosticCode.MODULE_ENTRY_INVALID


def test_module_graph_rejects_missing_imported_module() -> None:
    with pytest.raises(SemanticError) as error:
        ModuleGraph.build(
            (_unit("main.s3", "main"),),
            (
                ImportEdge(
                    ModuleId.parse("main"),
                    ModuleId.parse("missing"),
                    "value",
                ),
            ),
        )

    assert _semantic_code(error) is DiagnosticCode.MODULE_NOT_FOUND


def test_module_graph_rejects_duplicate_import() -> None:
    edge = ImportEdge(ModuleId.parse("main"), ModuleId.parse("math"), "inc")

    with pytest.raises(SemanticError) as error:
        ModuleGraph.build(
            (_unit("main.s3", "main"), _unit("math.s3", "math")),
            (edge, edge),
        )

    assert _semantic_code(error) is DiagnosticCode.IMPORT_DUPLICATE


def test_module_graph_rejects_import_local_name_conflict() -> None:
    with pytest.raises(SemanticError) as error:
        ModuleGraph.build(
            (
                _unit("main.s3", "main"),
                _unit("math.s3", "math"),
                _unit("util.s3", "util"),
            ),
            (
                ImportEdge(ModuleId.parse("main"), ModuleId.parse("math"), "inc"),
                ImportEdge(
                    ModuleId.parse("main"),
                    ModuleId.parse("util"),
                    "helper",
                    alias="inc",
                ),
            ),
        )

    assert _semantic_code(error) is DiagnosticCode.IMPORT_CONFLICT


def test_module_graph_rejects_direct_cycle() -> None:
    with pytest.raises(SemanticError) as error:
        ModuleGraph.build(
            (_unit("main.s3", "main"), _unit("math.s3", "math")),
            (
                ImportEdge(ModuleId.parse("main"), ModuleId.parse("math"), "inc"),
                ImportEdge(ModuleId.parse("math"), ModuleId.parse("main"), "main"),
            ),
        )

    assert _semantic_code(error) is DiagnosticCode.MODULE_CYCLE


def test_module_graph_rejects_indirect_cycle() -> None:
    with pytest.raises(SemanticError) as error:
        ModuleGraph.build(
            (
                _unit("main.s3", "main"),
                _unit("a.s3", "a"),
                _unit("b.s3", "b"),
            ),
            (
                ImportEdge(ModuleId.parse("main"), ModuleId.parse("a"), "a"),
                ImportEdge(ModuleId.parse("a"), ModuleId.parse("b"), "b"),
                ImportEdge(ModuleId.parse("b"), ModuleId.parse("main"), "main"),
            ),
        )

    assert _semantic_code(error) is DiagnosticCode.MODULE_CYCLE
