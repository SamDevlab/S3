from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
    SemanticError,
    diagnostic_from_exception,
)
from bootstrap.s3.lexer import SyntaxMode, tokenize
from bootstrap.s3.module_compilation import prepare_module_compilation
from bootstrap.s3.parser import parse_tokens
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.semantic import SemanticModel, analyze


def _semantic_model(source: str) -> SemanticModel:
    return analyze(
        parse_tokens(
            tokenize(source, mode=SyntaxMode.V0_6),
            mode=SyntaxMode.V0_6,
        )
    )


def _sources_semantic_model(sources: dict[str, str]) -> SemanticModel:
    plan = prepare_module_compilation(sources)
    return analyze(plan.program)


def _assert_sources_semantic_rejection(
    sources: dict[str, str] | tuple[tuple[str, str], ...],
    message: str,
) -> None:
    with pytest.raises(SemanticError) as captured:
        compile_sources_for_semantic_error(sources)

    diagnostic = diagnostic_from_exception(captured.value)
    assert diagnostic.phase is DiagnosticPhase.SEMANTIC
    assert diagnostic.category is DiagnosticCategory.SEMANTIC
    assert diagnostic.code is DiagnosticCode.SEMANTIC_INVALID_PROGRAM
    assert diagnostic.message == message


def compile_sources_for_semantic_error(
    sources: dict[str, str] | tuple[tuple[str, str], ...],
) -> None:
    plan = prepare_module_compilation(sources)
    analyze(plan.program)


def _assert_semantic_rejection(
    source: str,
    message: str,
    *,
    code: DiagnosticCode = DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
) -> None:
    with pytest.raises(SemanticError) as captured:
        compile_source(source)

    diagnostic = diagnostic_from_exception(captured.value)
    assert diagnostic.phase is DiagnosticPhase.SEMANTIC
    assert diagnostic.category is DiagnosticCategory.SEMANTIC
    assert diagnostic.code is code
    assert diagnostic.message == message


def test_acyclic_nested_record_layout_preserves_declared_leaf_order() -> None:
    model = _semantic_model(
        "enum Sign:\n"
        "    Negative\n"
        "    Positive\n"
        "record Inner:\n"
        "    value: tryte\n"
        "    sign: Sign\n"
        "record Outer:\n"
        "    flag: trit\n"
        "    inner: Inner\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    leaves = model.record_leaves("Outer")
    assert [leaf.path for leaf in leaves] == [
        ("flag",),
        ("inner", "value"),
        ("inner", "sign"),
    ]
    assert model.record_leaf_count("Outer") == 3


def test_deep_acyclic_nested_record_layout_is_accepted() -> None:
    model = _semantic_model(
        "record Coordinate:\n"
        "    x: tryte\n"
        "record Point:\n"
        "    coordinate: Coordinate\n"
        "record Shape:\n"
        "    point: Point\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    assert [leaf.path for leaf in model.record_leaves("Shape")] == [
        ("point", "coordinate", "x"),
    ]


def test_diamond_acyclic_record_layout_keeps_each_field_path_distinct() -> None:
    model = _semantic_model(
        "record Leaf:\n"
        "    value: tryte\n"
        "record Left:\n"
        "    leaf: Leaf\n"
        "record Right:\n"
        "    leaf: Leaf\n"
        "record Pair:\n"
        "    left: Left\n"
        "    right: Right\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )

    assert [leaf.path for leaf in model.record_leaves("Pair")] == [
        ("left", "leaf", "value"),
        ("right", "leaf", "value"),
    ]


def test_imported_record_field_participates_in_acyclic_layout() -> None:
    model = _sources_semantic_model(
        {
            "main.s3": (
                "module main\n"
                "from geometry import Point\n"
                "record Box:\n"
                "    point: Point\n"
                "fn main() -> tryte:\n"
                "    return 0\n"
            ),
            "geometry.s3": (
                "module geometry\n"
                "export record Point:\n"
                "    x: tryte\n"
                "export fn marker() -> tryte:\n"
                "    return 0\n"
            ),
        }
    )

    assert [leaf.path for leaf in model.record_leaves("Box")] == [
        ("point", "x"),
    ]


def test_acyclic_nested_record_layout_is_source_order_deterministic() -> None:
    ordered = (
        (
            "main.s3",
            "module main\n"
            "from geometry import Point\n"
            "record Box:\n"
            "    point: Point\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
        ),
        (
            "geometry.s3",
            "module geometry\n"
            "export record Point:\n"
            "    x: tryte\n"
            "export fn marker() -> tryte:\n"
            "    return 0\n",
        ),
    )

    first = _sources_semantic_model(dict(ordered))
    second = _sources_semantic_model(dict(reversed(ordered)))

    assert [leaf.path for leaf in first.record_leaves("Box")] == [
        ("point", "x"),
    ]
    assert [leaf.path for leaf in second.record_leaves("Box")] == [
        ("point", "x"),
    ]


def test_same_name_records_in_distinct_modules_keep_distinct_layout_identity() -> None:
    model = _sources_semantic_model(
        {
            "main.s3": (
                "module main\n"
                "from left import marker as left_marker\n"
                "from right import marker as right_marker\n"
                "fn main() -> tryte:\n"
                "    return left.marker() + right.marker()\n"
            ),
            "left.s3": (
                "module left\n"
                "export record Point:\n"
                "    x: tryte\n"
                "export fn marker() -> tryte:\n"
                "    return 0\n"
            ),
            "right.s3": (
                "module right\n"
                "export record Point:\n"
                "    y: tryte\n"
                "export fn marker() -> tryte:\n"
                "    return 0\n"
            ),
        }
    )

    assert [leaf.path for leaf in model.record_leaves("__s3mod_left__type_Point")] == [
        ("x",),
    ]
    assert [leaf.path for leaf in model.record_leaves("__s3mod_right__type_Point")] == [
        ("y",),
    ]


@pytest.mark.parametrize(
    ("source", "message"),
    (
        (
            "record Node:\n"
            "    next: Node\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "recursive record layout cycle: Node -> Node",
        ),
        (
            "record A:\n"
            "    b: B\n"
            "record B:\n"
            "    a: A\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "recursive record layout cycle: A -> B -> A",
        ),
        (
            "record A:\n"
            "    b: B\n"
            "record B:\n"
            "    c: C\n"
            "record C:\n"
            "    a: A\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "recursive record layout cycle: A -> B -> C -> A",
        ),
        (
            "record A:\n"
            "    b: B\n"
            "record B:\n"
            "    c: C\n"
            "record C:\n"
            "    d: D\n"
            "record D:\n"
            "    a: A\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "recursive record layout cycle: A -> B -> C -> D -> A",
        ),
    ),
)
def test_recursive_record_layouts_are_rejected_before_lowering(
    source: str,
    message: str,
) -> None:
    _assert_semantic_rejection(source, message)


def test_exported_self_reference_is_rejected_before_lowering() -> None:
    _assert_sources_semantic_rejection(
        {
            "main.s3": (
                "module main\n"
                "from graph import value\n"
                "fn main() -> tryte:\n"
                "    return value()\n"
            ),
            "graph.s3": (
                "module graph\n"
                "export record Node:\n"
                "    next: Node\n"
                "export fn value() -> tryte:\n"
                "    return 0\n"
            ),
        },
        "recursive record layout cycle: __s3mod_graph__type_Node -> "
        "__s3mod_graph__type_Node",
    )


def test_import_cycle_blocks_cross_module_layout_cycle_before_imported_type_rewrite() -> None:
    with pytest.raises(SemanticError) as captured:
        prepare_module_compilation(
            {
                "main.s3": (
                    "module main\n"
                    "from graph import B\n"
                    "export record A:\n"
                    "    b: B\n"
                    "fn main() -> tryte:\n"
                    "    return 0\n"
                ),
                "graph.s3": (
                    "module graph\n"
                    "from main import A\n"
                    "export record B:\n"
                    "    a: A\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n"
                ),
            }
        )

    assert "module import cycle" in str(captured.value)


def test_private_type_in_potential_cycle_is_rejected_by_import_resolution() -> None:
    with pytest.raises(SemanticError) as captured:
        prepare_module_compilation(
            {
                "main.s3": (
                    "module main\n"
                    "from graph import Node\n"
                    "record Box:\n"
                    "    node: Node\n"
                    "fn main() -> tryte:\n"
                    "    return 0\n"
                ),
                "graph.s3": (
                    "module graph\n"
                    "record Node:\n"
                    "    next: Node\n"
                    "export fn marker() -> tryte:\n"
                    "    return 0\n"
                ),
            }
        )

    assert "type 'Node' in module 'graph' is private" in str(captured.value)


def test_missing_record_field_type_keeps_unknown_type_diagnostic() -> None:
    _assert_semantic_rejection(
        "record Box:\n"
        "    missing: Missing\n"
        "fn main() -> tryte:\n"
        "    return 0\n",
        "unknown type 'Missing'",
    )


def test_duplicate_field_is_rejected_before_layout_cycle_analysis() -> None:
    _assert_semantic_rejection(
        "record Node:\n"
        "    next: Node\n"
        "    next: tryte\n"
        "fn main() -> tryte:\n"
        "    return 0\n",
        "duplicate field 'next' in record 'Node'",
        code=DiagnosticCode.RECORD_FIELD_DUPLICATE,
    )


def test_recursive_record_layout_does_not_enter_lowering(monkeypatch) -> None:
    def fail_lowering(*_args, **_kwargs):
        raise AssertionError("lowering should not run for recursive record layouts")

    monkeypatch.setattr("bootstrap.s3.pipeline.lower", fail_lowering)

    with pytest.raises(SemanticError) as captured:
        compile_source(
            "record A:\n"
            "    b: B\n"
            "record B:\n"
            "    a: A\n"
            "fn main() -> tryte:\n"
            "    return 0\n"
        )

    assert "recursive record layout cycle: A -> B -> A" in str(captured.value)


def test_single_leaf_nested_record_return_still_uses_existing_scalar_contract() -> None:
    model = _sources_semantic_model(
        {
            "main.s3": (
                "module main\n"
                "from geometry import Box\n"
                "from geometry import make\n"
                "fn main() -> tryte:\n"
                "    box: Box = make()\n"
                "    return box.point.x\n"
            ),
            "geometry.s3": (
                "module geometry\n"
                "export record Point:\n"
                "    x: tryte\n"
                "export record Box:\n"
                "    point: Point\n"
                "export fn make() -> Box:\n"
                "    return Box(point=Point(x=7))\n"
            ),
        }
    )

    assert model.record_leaf_count("__s3mod_geometry__type_Box") == 1
