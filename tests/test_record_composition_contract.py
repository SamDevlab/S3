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
from bootstrap.s3.pipeline import compile_source, compile_sources, run_source


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


@pytest.mark.parametrize(
    ("source", "message"),
    (
        (
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "nested record fields are not supported yet",
        ),
        (
            "record Node:\n"
            "    next: Node\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "nested record fields are not supported yet",
        ),
        (
            "record A:\n"
            "    b: B\n"
            "record B:\n"
            "    a: A\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "nested record fields are not supported yet",
        ),
        (
            "record Inner:\n"
            "    value: tryte\n"
            "record Outer:\n"
            "    inner: Inner\n"
            "fn main() -> tryte:\n"
            "    item: Outer = Outer(inner=Inner(value=1))\n"
            "    return 0\n",
            "nested record fields are not supported yet",
        ),
        (
            "record Box:\n"
            "    values: tryte[2]\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "record fields cannot be arrays in milestone 1.00",
        ),
        (
            "record Label:\n"
            "    text: string\n"
            "fn main() -> tryte:\n"
            "    return 0\n",
            "record fields cannot be string in milestone 1.00",
        ),
        (
            "record Box:\n"
            "    value: tryte\n"
            "fn main() -> tryte:\n"
            "    boxes: Box[1] = [Box(value=1)]\n"
            "    return 0\n",
            "arrays of nominal types are not supported",
        ),
    ),
)
def test_record_composition_rejects_unsupported_aggregate_shapes(
    source: str,
    message: str,
) -> None:
    _assert_semantic_rejection(source, message)


def test_imported_record_cannot_be_used_as_a_record_field_type() -> None:
    _assert_sources_semantic_rejection(
        {
            "main.s3": (
                "module main\n"
                "from logic import value\n"
                "record Outer:\n"
                "    inner: Inner\n"
                "fn main() -> tryte:\n"
                "    return value()\n"
            ),
            "logic.s3": (
                "module logic\n"
                "record Inner:\n"
                "    value: tryte\n"
                "export fn value() -> tryte:\n"
                "    return 1\n"
            ),
        },
        "nested record fields are not supported yet",
    )
