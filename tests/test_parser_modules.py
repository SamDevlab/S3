from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.generic_lexer import tokenize_to_arena
from bootstrap.s3.generic_parser import GenericParser
from bootstrap.s3.generic_syntax import NodeKind, SymbolPayload
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


def test_parsers_expand_comma_separated_imports_and_preserve_aliases() -> None:
    source = (
        "module app.main\n"
        "from lib.types import First as LocalFirst, Second, Third as LocalThird\n"
        "fn main() -> tryte:\n"
        "    return 0\n"
    )
    expected = [
        ("First", "LocalFirst"),
        ("Second", None),
        ("Third", "LocalThird"),
    ]

    program = parse(source, mode=SyntaxMode.V0_6)
    assert [(item.symbol_name, item.alias) for item in program.imports] == expected

    parsed = GenericParser(tokenize_to_arena(source, mode=SyntaxMode.V0_6)).parse_program()
    arena = parsed.syntax_arena
    imports = [
        arena.node(node_id)
        for node_id in arena.child_ids(parsed.root_id)
        if arena.node(node_id).kind is NodeKind.IMPORT_DECLARATION
    ]
    assert len(imports) == 3
    imported_names: list[tuple[str, str, str | None]] = []
    for node in imports:
        module_id, symbol_id, *alias_ids = arena.child_ids(node.id)
        module_symbol = arena.payload(arena.node(module_id))
        imported_symbol = arena.payload(arena.node(symbol_id))
        assert isinstance(module_symbol, SymbolPayload)
        assert isinstance(imported_symbol, SymbolPayload)
        alias_name = None
        if alias_ids:
            alias_symbol = arena.payload(arena.node(alias_ids[0]))
            assert isinstance(alias_symbol, SymbolPayload)
            alias_name = parsed.symbol_names[alias_symbol.symbol_id]
        imported_names.append(
            (
                parsed.symbol_names[module_symbol.symbol_id],
                parsed.symbol_names[imported_symbol.symbol_id],
                alias_name,
            )
        )
    assert imported_names == [
        ("lib.types", symbol, alias) for symbol, alias in expected
    ]


@pytest.mark.parametrize(
    "source",
    (
        "module app\nfrom lib.types import First,\nfn main() -> tryte:\n    return 0\n",
        "module app\nfrom lib.types import First as, Second\nfn main() -> tryte:\n    return 0\n",
    ),
)
def test_parser_rejects_incomplete_comma_separated_imports(source: str) -> None:
    with pytest.raises(ParseError):
        parse(source, mode=SyntaxMode.V0_6)

    with pytest.raises(Exception):
        GenericParser(tokenize_to_arena(source, mode=SyntaxMode.V0_6)).parse_program()


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
