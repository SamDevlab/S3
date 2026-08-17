from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
    SemanticError,
    diagnostic_from_exception,
)
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.lexer import SyntaxMode, tokenize
from bootstrap.s3.parser import parse_tokens
from bootstrap.s3.pipeline import compile_source, compile_sources, run_source
from bootstrap.s3.semantic import analyze


def _assert_semantic_rejection(source: str, message: str) -> None:
    with pytest.raises(SemanticError) as captured:
        compile_source(source)

    diagnostic = diagnostic_from_exception(captured.value)
    assert diagnostic.phase is DiagnosticPhase.SEMANTIC
    assert diagnostic.category is DiagnosticCategory.SEMANTIC
    assert diagnostic.code is DiagnosticCode.SEMANTIC_INVALID_PROGRAM
    assert diagnostic.message == message


def _assert_sources_semantic_rejection(
    sources: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(SemanticError) as captured:
        compile_sources(sources)

    diagnostic = diagnostic_from_exception(captured.value)
    assert diagnostic.phase is DiagnosticPhase.SEMANTIC
    assert diagnostic.category is DiagnosticCategory.SEMANTIC
    assert diagnostic.code is DiagnosticCode.SEMANTIC_INVALID_PROGRAM
    assert diagnostic.message == message


def _semantic_model(source: str):
    return analyze(
        parse_tokens(
            tokenize(source, mode=SyntaxMode.V0_6),
            mode=SyntaxMode.V0_6,
        )
    )


def test_record_composition_accepts_current_scalar_and_enum_fields() -> None:
    source = (
        "enum Sign:\n"
        "    Negative\n"
        "    Zero\n"
        "    Positive\n"
        "record Tagged:\n"
        "    flag: trit\n"
        "    value: tryte\n"
        "    sign: Sign\n"
        "fn score(item: Tagged) -> tryte:\n"
        "    match item.sign:\n"
        "        Sign.Negative:\n"
        "            return -1\n"
        "        Sign.Zero:\n"
        "            return 0\n"
        "        Sign.Positive:\n"
        "            return item.value\n"
        "fn main() -> tryte:\n"
        "    item: Tagged = Tagged(flag=-1, value=11, sign=Sign.Positive)\n"
        "    return score(item)\n"
    )

    assert run_source(source, optimization="O0") == 11
    assert run_source(source, optimization="O1") == 11


def test_single_field_record_return_remains_the_only_record_return_contract() -> None:
    source = (
        "record Box:\n"
        "    value: tryte\n"
        "fn make() -> Box:\n"
        "    return Box(value=8)\n"
        "fn main() -> tryte:\n"
        "    box: Box = make()\n"
        "    return box.value\n"
    )

    assert run_source(source, optimization="O0") == 8
    assert run_source(source, optimization="O1") == 8


def test_module_record_composition_stays_module_local_without_nesting() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from logic import classify\n"
            "fn main() -> tryte:\n"
            "    return classify(2)\n"
        ),
        "logic.s3": (
            "module logic\n"
            "enum Kind:\n"
            "    Small\n"
            "    Large\n"
            "record Classified:\n"
            "    kind: Kind\n"
            "    value: tryte\n"
            "export fn classify(value: tryte) -> tryte:\n"
            "    item: Classified = Classified(kind=Kind.Large, value=value)\n"
            "    match item.kind:\n"
            "        Kind.Small:\n"
            "            return -1\n"
            "        Kind.Large:\n"
            "            return item.value\n"
        ),
    }

    for optimization in ("O0", "O1"):
        compilation = compile_sources(sources, optimization)
        assert execute_assembly(compilation.assembly) == 2


def test_record_composition_accepts_arrays_of_records() -> None:
    source = (
        "record Box:\n"
        "    value: tryte\n"
        "fn main() -> tryte:\n"
        "    boxes: Box[1] = [Box(value=1)]\n"
        "    return boxes[0].value\n"
    )

    assert run_source(source, optimization="O0") == 1
    assert run_source(source, optimization="O1") == 1


def test_record_composition_accepts_static_text_field() -> None:
    source = (
        "record Label:\n"
        "    text: string\n"
        "fn main() -> tryte:\n"
        "    label: Label = Label(text=\"hello\")\n"
        "    selected: string = label.text\n"
        "    return len(\"hello\")\n"
    )

    for optimization in ("O0", "O1"):
        compilation = compile_source(source, optimization)
        assert execute_assembly(compilation.assembly) == 5


def test_acyclic_nested_record_fields_are_accepted_semantically() -> None:
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

    assert model.record_leaf_count("Outer") == 3
    assert [leaf.path for leaf in model.record_leaves("Outer")] == [
        ("flag",),
        ("inner", "value"),
        ("inner", "sign"),
    ]


def test_imported_record_can_be_used_as_a_record_field_type() -> None:
    compilation = compile_sources(
        {
            "main.s3": (
                "module main\n"
                "from logic import Inner\n"
                "from logic import value\n"
                "record Outer:\n"
                "    inner: Inner\n"
                "fn main() -> tryte:\n"
                "    return value()\n"
            ),
            "logic.s3": (
                "module logic\n"
                "export record Inner:\n"
                "    value: tryte\n"
                "export fn value() -> tryte:\n"
                "    return 1\n"
            ),
        },
    )

    assert compilation.semantic_model.record_leaf_count("Outer") == 1
