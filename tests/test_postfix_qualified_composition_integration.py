from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    SemanticError,
    diagnostic_from_exception,
)
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source, compile_sources
from tests.support.differential import (
    DifferentialCase,
    DifferentialExpectation,
    assert_hosted_equivalence,
)


def _run_sources(
    sources: dict[str, str] | tuple[tuple[str, str], ...],
    optimization: OptimizationLevel | str,
) -> int:
    compilation = compile_sources(sources, optimization)
    return execute_assembly(compilation.assembly)


def _assert_sources_equivalent(
    sources: dict[str, str] | tuple[tuple[str, str], ...],
    expected: int,
) -> None:
    observed = tuple(
        _run_sources(sources, optimization)
        for optimization in (OptimizationLevel.O0, OptimizationLevel.O1)
    )
    assert observed == (expected, expected)


def _assert_sources_semantic_rejection(
    sources: dict[str, str],
    message: str,
    code: DiagnosticCode,
) -> None:
    with pytest.raises(SemanticError) as captured:
        compile_sources(sources)

    diagnostic = diagnostic_from_exception(captured.value)
    assert diagnostic.category is DiagnosticCategory.SEMANTIC
    assert diagnostic.code is code
    assert diagnostic.message == message


def test_single_file_postfix_composition_uses_hosted_differential_harness() -> None:
    assert_hosted_equivalence(
        DifferentialCase(
            name="single-file-record-member-branch-loop",
            source=(
                "enum Sign:\n"
                "    Negative\n"
                "    Zero\n"
                "    Positive\n"
                "record Tagged:\n"
                "    flag: trit\n"
                "    sign: Sign\n"
                "    value: tryte\n"
                "fn score(item: Tagged) -> tryte:\n"
                "    while item.flag:\n"
                "        return -9\n"
                "    match item.sign:\n"
                "        Sign.Negative:\n"
                "            return -1\n"
                "        Sign.Zero:\n"
                "            return 0\n"
                "        Sign.Positive:\n"
                "            return item.value\n"
                "fn main() -> tryte:\n"
                "    item: Tagged = Tagged(flag=0, sign=Sign.Positive, value=12)\n"
                "    return score(item)\n"
            ),
            expectation=DifferentialExpectation(return_value=12),
            tags=("postfix", "record", "enum", "loop"),
        )
    )


def test_multimodule_postfix_and_qualified_composition_o0_o1_equivalent() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from math import inc\n"
            "from math import is_positive\n"
            "from math import one\n"
            "from signlib import classify\n"
            "from signlib import positive\n"
            "from maker import make\n"
            "enum Local:\n"
            "    No\n"
            "    Yes\n"
            "record Item:\n"
            "    flag: trit\n"
            "    value: tryte\n"
            "    local: Local\n"
            "fn keep(value: tryte) -> tryte:\n"
            "    return value\n"
            "fn local_score(item: Item) -> tryte:\n"
            "    while item.flag:\n"
            "        return -99\n"
            "    match item.local:\n"
            "        Local.No:\n"
            "            return -1\n"
            "        Local.Yes:\n"
            "            return keep(item.value)\n"
            "fn main() -> tryte:\n"
            "    item: Item = Item(flag=0, value=3, local=Local.Yes)\n"
            "    mut counter: tryte = math.one()\n"
            "    while math.is_positive(counter):\n"
            "        counter = counter - 1\n"
            "    return math.inc(math.one()) + local_score(item) + "
            "signlib.classify(signlib.Sign.Positive) + maker.make().value + "
            "counter\n"
        ),
        "math.s3": (
            "module math\n"
            "export fn one() -> tryte:\n"
            "    return 1\n"
            "export fn inc(value: tryte) -> tryte:\n"
            "    return value + 1\n"
            "export fn is_positive(value: tryte) -> trit:\n"
            "    return value > 0\n"
        ),
        "signlib.s3": (
            "module signlib\n"
            "enum Sign:\n"
            "    Negative\n"
            "    Zero\n"
            "    Positive\n"
            "export fn positive() -> Sign:\n"
            "    return Sign.Positive\n"
            "export fn classify(value: Sign) -> tryte:\n"
            "    match value:\n"
            "        Sign.Negative:\n"
            "            return -5\n"
            "        Sign.Zero:\n"
            "            return 0\n"
            "        Sign.Positive:\n"
            "            return 5\n"
        ),
        "maker.s3": (
            "module maker\n"
            "record Box:\n"
            "    value: tryte\n"
            "export fn make() -> Box:\n"
            "    return Box(value=7)\n"
        ),
    }

    _assert_sources_equivalent(sources, 17)


def test_multimodule_qualified_composition_is_source_order_deterministic() -> None:
    sources = (
        (
            "main.s3",
            "module main\n"
            "from left import value\n"
            "from right import value as right_value\n"
            "fn main() -> tryte:\n"
            "    return left.value() + right.value()\n",
        ),
        (
            "left.s3",
            "module left\n"
            "export fn value() -> tryte:\n"
            "    return 2\n",
        ),
        (
            "right.s3",
            "module right\n"
            "export fn value() -> tryte:\n"
            "    return 3\n",
        ),
    )

    forward = compile_sources(sources).assembly.render()
    backward = compile_sources(tuple(reversed(sources))).assembly.render()

    assert forward == backward
    _assert_sources_equivalent(sources, 5)


@pytest.mark.parametrize(
    ("main_source", "library_source", "message", "code"),
    (
        (
            "module main\n"
            "from math import visible\n"
            "fn main() -> tryte:\n"
            "    return math.hidden()\n",
            "module math\n"
            "export fn visible() -> tryte:\n"
            "    return 1\n"
            "fn hidden() -> tryte:\n"
            "    return 2\n",
            "function 'hidden' in module 'math' is private",
            DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
        ),
        (
            "module main\n"
            "from math import visible\n"
            "fn main() -> tryte:\n"
            "    return math.missing()\n",
            "module math\n"
            "export fn visible() -> tryte:\n"
            "    return 1\n",
            "module 'math' has no member 'missing'",
            DiagnosticCode.IMPORT_UNKNOWN_SYMBOL,
        ),
        (
            "module main\n"
            "from math import visible\n"
            "fn main() -> tryte:\n"
            "    return math\n",
            "module math\n"
            "export fn visible() -> tryte:\n"
            "    return 1\n",
            "module 'math' cannot be used as a value",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "module main\n"
            "from math import visible\n"
            "fn main() -> tryte:\n"
            "    return math.Sign\n",
            "module math\n"
            "enum Sign:\n"
            "    Positive\n"
            "export fn visible() -> tryte:\n"
            "    return 1\n",
            "type 'math.Sign' cannot be used as a value",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "module main\n"
            "from math import visible\n"
            "fn main() -> tryte:\n"
            "    return math.visible()()\n",
            "module math\n"
            "export fn visible() -> tryte:\n"
            "    return 1\n",
            "call target must be an unqualified function name",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
    ),
)
def test_multimodule_postfix_composition_rejects_invalid_public_shapes(
    main_source: str,
    library_source: str,
    message: str,
    code: DiagnosticCode,
) -> None:
    _assert_sources_semantic_rejection(
        {
            "main.s3": main_source,
            "math.s3": library_source,
        },
        message,
        code,
    )


def test_unsupported_aggregate_shapes_remain_rejected_in_differential_path() -> None:
    for source, message in (
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
            "record Box:\n"
            "    value: tryte\n"
            "fn main() -> tryte:\n"
            "    boxes: Box[1] = [Box(value=1)]\n"
            "    return 0\n",
            "arrays of nominal types are not supported",
        ),
    ):
        with pytest.raises(SemanticError) as captured:
            compile_source(source)

        assert diagnostic_from_exception(captured.value).message == message


def test_imported_record_field_remains_rejected_in_multimodule_path() -> None:
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
        DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
    )
