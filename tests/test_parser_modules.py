from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.lexer import SyntaxMode, TokenKind, tokenize
from bootstrap.s3.module_graph import (
    ModuleGraph,
    ModuleId,
    import_edges_from_program,
    source_unit_from_program,
)
from bootstrap.s3.parser import parse


def test_lexer_recognizes_module_import_keywords_in_v0_6() -> None:
    tokens = tokenize(
        "module app\nfrom lib.math import inc as add_one\n",
        mode=SyntaxMode.V0_6,
    )

    kinds = [token.kind for token in tokens]

    assert TokenKind.MODULE in kinds
    assert TokenKind.FROM in kinds
    assert TokenKind.IMPORT in kinds
    assert TokenKind.AS in kinds
    assert TokenKind.DOT in kinds


def test_parser_accepts_module_imports_and_exported_function() -> None:
    program = parse(
        "module app.main\n"
        "from lib.math import inc\n"
        "from lib.sign import sign as classify\n"
        "\n"
        "export fn helper(value: tryte) -> tryte:\n"
        "    return inc(value)\n"
        "\n"
        "fn main() -> tryte:\n"
        "    return helper(1)\n",
        mode=SyntaxMode.V0_6,
    )

    assert program.module is not None
    assert program.module.name == "app.main"
    assert [import_.module_name for import_ in program.imports] == [
        "lib.math",
        "lib.sign",
    ]
    assert program.imports[0].symbol_name == "inc"
    assert program.imports[0].alias is None
    assert program.imports[1].symbol_name == "sign"
    assert program.imports[1].alias == "classify"
    assert program.functions[0].exported is True
    assert program.functions[1].exported is False


def test_parser_module_helpers_feed_module_graph() -> None:
    program = parse(
        "module app\n"
        "from lib.math import inc\n"
        "fn main() -> tryte:\n"
        "    return inc(1)\n",
        mode=SyntaxMode.V0_6,
    )
    lib = parse(
        "module lib.math\n"
        "export fn inc(value: tryte) -> tryte:\n"
        "    return value + 1\n",
        mode=SyntaxMode.V0_6,
    )
    app_unit = source_unit_from_program("src/app.s3", "", program)
    lib_unit = source_unit_from_program("src/lib/math.s3", "", lib)
    imports = import_edges_from_program(app_unit.module_id, program)

    graph = ModuleGraph.build(
        (app_unit, lib_unit),
        imports,
        entry_module=ModuleId.parse("app"),
    )

    assert tuple(str(module) for module in graph.ordered_modules) == (
        "lib.math",
        "app",
    )


def test_parser_rejects_module_syntax_in_v0_5() -> None:
    with pytest.raises(ParseError):
        parse(
            "module app\nfn main() -> tryte:\n    return 0\n",
            mode=SyntaxMode.V0_5,
        )
