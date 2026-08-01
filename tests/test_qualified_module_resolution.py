from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_sources


def _run_sources(
    sources: dict[str, str] | tuple[tuple[str, str], ...],
    *,
    optimization: OptimizationLevel = OptimizationLevel.O0,
) -> int:
    return execute_assembly(
        compile_sources(sources, optimization=optimization).assembly,
    )


def _semantic_code(error: pytest.ExceptionInfo[SemanticError]) -> DiagnosticCode:
    return error.value.diagnostic_code


def test_qualified_module_call_runs_for_tryte_and_trit_returns() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from math import inc\n"
            "from math import is_positive\n"
            "fn main() -> tryte:\n"
            "    if_value: trit = math.is_positive(1)\n"
            "    return math.inc(6)\n"
        ),
        "math.s3": (
            "module math\n"
            "export fn inc(value: tryte) -> tryte:\n"
            "    return value + 1\n"
            "export fn is_positive(value: tryte) -> trit:\n"
            "    return value > 0\n"
        ),
    }

    assert _run_sources(sources, optimization=OptimizationLevel.O0) == 7
    assert _run_sources(sources, optimization=OptimizationLevel.O1) == 7


def test_qualified_module_call_composes_in_expressions_arguments_branches_and_loops() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from math import inc\n"
            "from math import is_positive\n"
            "fn twice(value: tryte) -> tryte:\n"
            "    return math.inc(value) + math.inc(0)\n"
            "fn main() -> tryte:\n"
            "    mut total: tryte = twice(math.inc(1))\n"
            "    while math.is_positive(total):\n"
            "        total = total - math.inc(0)\n"
            "    return total\n"
        ),
        "math.s3": (
            "module math\n"
            "export fn inc(value: tryte) -> tryte:\n"
            "    return value + 1\n"
            "export fn is_positive(value: tryte) -> trit:\n"
            "    return value > 0\n"
        ),
    }

    assert _run_sources(sources) == 0


def test_qualified_module_resolution_is_deterministic_for_source_order() -> None:
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
            "right.s3",
            "module right\n"
            "export fn value() -> tryte:\n"
            "    return 3\n",
        ),
        (
            "left.s3",
            "module left\n"
            "export fn value() -> tryte:\n"
            "    return 2\n",
        ),
    )

    forward = compile_sources(sources).assembly.render()
    backward = compile_sources(tuple(reversed(sources))).assembly.render()

    assert forward == backward
    assert _run_sources(sources) == 5


def test_qualified_module_enum_variant_flows_through_values_arguments_and_match() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from signlib import classify\n"
            "from signlib import positive\n"
            "fn main() -> tryte:\n"
            "    if_equal: trit = signlib.Sign.Positive == signlib.Sign.Positive\n"
            "    match positive():\n"
            "        signlib.Sign.Negative:\n"
            "            return -1\n"
            "        signlib.Sign.Zero:\n"
            "            return 0\n"
            "        signlib.Sign.Positive:\n"
            "            return classify(signlib.Sign.Positive)\n"
        ),
        "signlib.s3": (
            "module signlib\n"
            "export enum Sign:\n"
            "    Negative\n"
            "    Zero\n"
            "    Positive\n"
            "export fn positive() -> Sign:\n"
            "    return Sign.Positive\n"
            "export fn classify(value: Sign) -> tryte:\n"
            "    match value:\n"
            "        Sign.Negative:\n"
            "            return -1\n"
            "        Sign.Zero:\n"
            "            return 0\n"
            "        Sign.Positive:\n"
            "            return 1\n"
        ),
    }

    assert _run_sources(sources, optimization=OptimizationLevel.O0) == 1
    assert _run_sources(sources, optimization=OptimizationLevel.O1) == 1


@pytest.mark.parametrize(
    ("main_source", "message", "code"),
    [
        (
            "module main\n"
            "fn main() -> tryte:\n"
            "    return missing.inc()\n",
            "module 'missing' was not found",
            DiagnosticCode.MODULE_NOT_FOUND,
        ),
        (
            "module main\n"
            "fn main() -> tryte:\n"
            "    return math.inc()\n",
            "module 'math' is not imported",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "module main\n"
            "from math import inc\n"
            "fn main() -> tryte:\n"
            "    return math.missing()\n",
            "module 'math' has no member 'missing'",
            DiagnosticCode.IMPORT_UNKNOWN_SYMBOL,
        ),
        (
            "module main\n"
            "from math import inc\n"
            "fn main() -> tryte:\n"
            "    return math.hidden()\n",
            "function 'hidden' in module 'math' is private",
            DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
        ),
        (
            "module main\n"
            "from math import inc\n"
            "fn main() -> tryte:\n"
            "    return math\n",
            "module 'math' cannot be used as a value",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "module main\n"
            "from math import inc\n"
            "fn main() -> tryte:\n"
            "    return math()\n",
            "module 'math' cannot be called",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "module main\n"
            "from math import inc\n"
            "fn main() -> tryte:\n"
            "    return math[0]\n",
            "module 'math' cannot be indexed",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "module main\n"
            "from math import inc\n"
            "fn main() -> tryte:\n"
            "    return math.Sign\n",
            "type 'math.Sign' cannot be used as a value",
            DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        ),
        (
            "module main\n"
            "from math import inc\n"
            "fn main() -> tryte:\n"
            "    return math.Sign.Positive.value\n",
            "field access requires a record value",
            DiagnosticCode.RECORD_FIELD_UNKNOWN,
        ),
    ],
)
def test_qualified_module_resolution_rejects_invalid_member_uses(
    main_source: str,
    message: str,
    code: DiagnosticCode,
) -> None:
    with pytest.raises(SemanticError) as error:
        compile_sources(
            {
                "main.s3": main_source,
                "math.s3": (
                    "module math\n"
                    "export enum Sign:\n"
                    "    Negative\n"
                    "    Positive\n"
                    "export fn inc() -> tryte:\n"
                    "    return 1\n"
                    "fn hidden() -> tryte:\n"
                    "    return 2\n"
                ),
            }
        )

    assert message in str(error.value)
    assert _semantic_code(error) is code


def test_local_runtime_binding_wins_over_module_root() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from math import inc\n"
            "fn main() -> tryte:\n"
            "    math: tryte = 1\n"
            "    return math.inc\n"
        ),
        "math.s3": (
            "module math\n"
            "export fn inc() -> tryte:\n"
            "    return 2\n"
        ),
    }

    with pytest.raises(SemanticError) as error:
        compile_sources(sources)

    assert "field access requires a record value" in str(error.value)
    assert _semantic_code(error) is DiagnosticCode.RECORD_FIELD_UNKNOWN


def test_expression_callees_remain_rejected_without_attribute_error() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "fn factory() -> tryte:\n"
            "    return 1\n"
            "fn main() -> tryte:\n"
            "    return factory()()\n"
        ),
    }

    with pytest.raises(SemanticError) as error:
        compile_sources(sources)

    assert "call target must be an unqualified function name" in str(error.value)
