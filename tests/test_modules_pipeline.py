from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_source, compile_sources


def _run_sources(
    sources: dict[str, str] | tuple[tuple[str, str], ...],
    *,
    optimization: OptimizationLevel = OptimizationLevel.O0,
    entry_module: str = "main",
) -> int:
    compilation = compile_sources(
        sources,
        optimization,
        entry_module=entry_module,
    )
    return execute_assembly(compilation.assembly)


def _semantic_code(error: pytest.ExceptionInfo[SemanticError]) -> DiagnosticCode:
    return error.value.diagnostic_code


def test_compile_source_single_file_compatibility_is_preserved() -> None:
    source = "fn main() -> tryte:\n    return 7\n"

    assert compile_source(source, mode=SyntaxMode.V0_6).ir.functions[0].name == "main"
    assert _run_sources({"main.s3": source}) == 7


def test_compile_sources_imports_exported_function() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from math import inc\n"
            "fn main() -> tryte:\n"
            "    return inc(6)\n"
        ),
        "math.s3": (
            "module math\n"
            "export fn inc(value: tryte) -> tryte:\n"
            "    return value + 1\n"
        ),
    }

    assert _run_sources(sources, optimization=OptimizationLevel.O0) == 7
    assert _run_sources(sources, optimization=OptimizationLevel.O1) == 7


def test_compile_sources_imports_transitively() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from app.logic import compute\n"
            "fn main() -> tryte:\n"
            "    return compute(3)\n"
        ),
        "app/logic.s3": (
            "module app.logic\n"
            "from math import inc\n"
            "export fn compute(value: tryte) -> tryte:\n"
            "    return inc(value) + inc(1)\n"
        ),
        "math.s3": (
            "module math\n"
            "export fn inc(value: tryte) -> tryte:\n"
            "    return value + 1\n"
        ),
    }

    assert _run_sources(sources) == 6


def test_compile_sources_accepts_import_alias() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from math import inc as add_one\n"
            "fn main() -> tryte:\n"
            "    return add_one(8)\n"
        ),
        "math.s3": (
            "module math\n"
            "export fn inc(value: tryte) -> tryte:\n"
            "    return value + 1\n"
        ),
    }

    assert _run_sources(sources) == 9


def test_compile_sources_is_deterministic_for_input_order() -> None:
    sources = (
        (
            "main.s3",
            "module main\n"
            "from math import inc\n"
            "fn main() -> tryte:\n"
            "    return inc(6)\n",
        ),
        (
            "math.s3",
            "module math\n"
            "export fn inc(value: tryte) -> tryte:\n"
            "    return value + 1\n",
        ),
    )

    forward = compile_sources(sources).assembly.render()
    backward = compile_sources(tuple(reversed(sources))).assembly.render()

    assert forward == backward


def test_compile_sources_preserves_entry_module_composite_types() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "enum Sign:\n"
            "    Negative\n"
            "    Zero\n"
            "    Positive\n"
            "record Tagged:\n"
            "    sign: Sign\n"
            "    value: tryte\n"
            "fn main() -> tryte:\n"
            "    item: Tagged = Tagged(sign=Sign.Positive, value=11)\n"
            "    match item.sign:\n"
            "        Sign.Negative:\n"
            "            return -1\n"
            "        Sign.Zero:\n"
            "            return 0\n"
            "        Sign.Positive:\n"
            "            return item.value\n"
        ),
        "math.s3": (
            "module math\n"
            "export fn inc(value: tryte) -> tryte:\n"
            "    return value + 1\n"
        ),
    }

    assert _run_sources(sources, optimization=OptimizationLevel.O0) == 11
    assert _run_sources(sources, optimization=OptimizationLevel.O1) == 11


def test_compile_sources_rewrites_imported_module_composite_types() -> None:
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

    assert _run_sources(sources, optimization=OptimizationLevel.O0) == 2
    assert _run_sources(sources, optimization=OptimizationLevel.O1) == 2


def test_compile_sources_type_names_are_module_local() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from left import left_value\n"
            "from right import right_value\n"
            "record Box:\n"
            "    value: tryte\n"
            "fn main() -> tryte:\n"
            "    box: Box = Box(value=1)\n"
            "    return box.value + left_value() + right_value()\n"
        ),
        "left.s3": (
            "module left\n"
            "record Box:\n"
            "    value: tryte\n"
            "export fn left_value() -> tryte:\n"
            "    box: Box = Box(value=2)\n"
            "    return box.value\n"
        ),
        "right.s3": (
            "module right\n"
            "record Box:\n"
            "    value: tryte\n"
            "export fn right_value() -> tryte:\n"
            "    box: Box = Box(value=3)\n"
            "    return box.value\n"
        ),
    }

    assert _run_sources(sources, optimization=OptimizationLevel.O0) == 6
    assert _run_sources(sources, optimization=OptimizationLevel.O1) == 6


def test_compile_sources_rejects_private_import() -> None:
    with pytest.raises(SemanticError) as error:
        compile_sources(
            {
                "main.s3": (
                    "module main\n"
                    "from math import inc\n"
                    "fn main() -> tryte:\n"
                    "    return inc(6)\n"
                ),
                "math.s3": (
                    "module math\n"
                    "fn inc(value: tryte) -> tryte:\n"
                    "    return value + 1\n"
                ),
            }
        )

    assert _semantic_code(error) is DiagnosticCode.IMPORT_PRIVATE_SYMBOL


def test_compile_sources_rejects_unknown_imported_symbol() -> None:
    with pytest.raises(SemanticError) as error:
        compile_sources(
            {
                "main.s3": (
                    "module main\n"
                    "from math import missing\n"
                    "fn main() -> tryte:\n"
                    "    return missing(6)\n"
                ),
                "math.s3": (
                    "module math\n"
                    "export fn inc(value: tryte) -> tryte:\n"
                    "    return value + 1\n"
                ),
            }
        )

    assert _semantic_code(error) is DiagnosticCode.IMPORT_UNKNOWN_SYMBOL


def test_compile_sources_rejects_import_conflicting_with_local_function() -> None:
    with pytest.raises(SemanticError) as error:
        compile_sources(
            {
                "main.s3": (
                    "module main\n"
                    "from math import inc\n"
                    "fn inc(value: tryte) -> tryte:\n"
                    "    return value\n"
                    "fn main() -> tryte:\n"
                    "    return inc(6)\n"
                ),
                "math.s3": (
                    "module math\n"
                    "export fn inc(value: tryte) -> tryte:\n"
                    "    return value + 1\n"
                ),
            }
        )

    assert _semantic_code(error) is DiagnosticCode.IMPORT_CONFLICT


def test_compile_sources_rejects_missing_module_and_cycle() -> None:
    with pytest.raises(SemanticError) as missing:
        compile_sources(
            {
                "main.s3": (
                    "module main\n"
                    "from missing import value\n"
                    "fn main() -> tryte:\n"
                    "    return value()\n"
                ),
            }
        )

    assert _semantic_code(missing) is DiagnosticCode.MODULE_NOT_FOUND

    with pytest.raises(SemanticError) as cycle:
        compile_sources(
            {
                "main.s3": (
                    "module main\n"
                    "from lib import value\n"
                    "fn main() -> tryte:\n"
                    "    return value()\n"
                ),
                "lib.s3": (
                    "module lib\n"
                    "from main import main\n"
                    "export fn value() -> tryte:\n"
                    "    return 1\n"
                ),
            }
        )

    assert _semantic_code(cycle) is DiagnosticCode.MODULE_CYCLE


def test_compile_sources_requires_entry_main_in_entry_module() -> None:
    with pytest.raises(SemanticError) as error:
        compile_sources(
            {
                "app.s3": (
                    "module app\n"
                    "export fn value() -> tryte:\n"
                    "    return 1\n"
                ),
            },
            entry_module="app",
        )

    assert _semantic_code(error) is DiagnosticCode.MODULE_ENTRY_INVALID
