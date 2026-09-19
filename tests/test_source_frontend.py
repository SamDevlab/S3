from __future__ import annotations

import pytest

from bootstrap.s3.compiler_substrate import SourceBundle
from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.generic_syntax import (
    DeclarationPayload,
    FunctionPayload,
    NodeKind,
    PayloadKind,
    SymbolPayload,
)
from bootstrap.s3.lexer import SyntaxMode, TokenKind, tokenize
from bootstrap.s3.source_frontend import (
    TokenArena,
    parse_source_bundle,
    parse_source_bundle_independent,
    parse_source_to_syntax,
    parse_source_to_syntax_independent,
)


PROGRAM = """\
module demo
record Pair:
    left: i64
    right: i64
enum Choice:
    None
    Some(value: i64)
fn add(x: i64, y: i64) -> i64:
    return x + y
fn main() -> i64:
    mut value: i64 = add(1, 2)
    return value
"""


def _kinds(result) -> tuple[NodeKind, ...]:
    return tuple(node.kind for _, node in result.syntax_arena.nodes.items())


def test_token_arena_uses_direct_ids_and_round_trips_reference_tokens() -> None:
    arena = TokenArena.from_source(PROGRAM, file_id=7)
    reference = tokenize(arena.source, mode=SyntaxMode.V0_6)
    rebuilt = arena.to_reference_tokens()
    assert tuple((item.kind, item.text, item.position) for item in rebuilt) == tuple(
        (item.kind, item.text, item.position) for item in reference
    )
    assert tuple(item_id for item_id, _ in arena.tokens.items()) == tuple(range(len(arena)))
    assert all(record.span.file_id == 7 for _, record in arena.tokens.items())


def test_token_arena_normalizes_line_endings_and_uses_utf8_byte_spans() -> None:
    source = 'fn main() -> i64:\r\n    discard "é"\r\n    return 0\r\n'
    arena = TokenArena.from_source(source, file_id=3)
    assert "\r" not in arena.source
    string_token = next(
        record
        for _, record in arena.tokens.items()
        if record.kind is TokenKind.STRING_LITERAL
    )
    assert string_token.text == '"é"'
    assert string_token.span.end - string_token.span.start == len('"é"'.encode("utf-8"))
    assert TokenArena.POSITION_AUTHORITY == "normalized_utf8_bytes"


def test_real_source_projects_to_valid_generic_syntax_arena() -> None:
    first = parse_source_to_syntax(PROGRAM, file_id=2)
    second = parse_source_to_syntax(PROGRAM, file_id=2)

    first.syntax_arena.validate()
    second.syntax_arena.validate()

    root = first.syntax_arena.node(first.root_id)
    child_kinds = tuple(
        first.syntax_arena.node(child_id).kind
        for child_id in first.syntax_arena.child_ids(root.id)
    )
    assert child_kinds == (
        NodeKind.MODULE_DECLARATION,
        NodeKind.RECORD_DECLARATION,
        NodeKind.ENUM_DECLARATION,
        NodeKind.FUNCTION,
        NodeKind.FUNCTION,
    )
    assert first.structural_digest() == second.structural_digest()
    assert NodeKind.BINARY in _kinds(first)
    assert NodeKind.VARIABLE_DECLARATION in _kinds(first)
    assert NodeKind.RECORD_FIELD in _kinds(first)
    assert NodeKind.ENUM_VARIANT in _kinds(first)


def test_parser_level_function_payload_can_defer_semantic_return_type_id() -> None:
    result = parse_source_to_syntax(
        "fn main() -> i64:\n    return 0\n"
    )
    function = next(
        node
        for _, node in result.syntax_arena.nodes.items()
        if node.kind is NodeKind.FUNCTION
    )
    assert function.payload_kind is PayloadKind.FUNCTION
    payload = result.syntax_arena.payload(function)
    assert isinstance(payload, FunctionPayload)
    assert payload.return_type_id == -1
    result.syntax_arena.validate()


@pytest.mark.parametrize(
    "source, required_kinds",
    (
        (
            """\
fn main() -> i64:
    return (1 + 2) * 3
""",
            {NodeKind.BINARY, NodeKind.RETURN},
        ),
        (
            """\
fn main() -> i64:
    mut values: i64[3] = [1, 2, 3]
    return values[1]
""",
            {
                NodeKind.ARRAY_TYPE,
                NodeKind.ARRAY_LITERAL,
                NodeKind.INDEX,
                NodeKind.VARIABLE_DECLARATION,
            },
        ),
        (
            """\
record Box<T: value>:
    value: T
fn main() -> i64:
    return 0
""",
            {
                NodeKind.TYPE_PARAMETER,
                NodeKind.TYPE_PARAMETER_TYPE,
                NodeKind.RECORD_DECLARATION,
            },
        ),
    ),
)
def test_source_frontend_anti_specialization_shapes(
    source: str,
    required_kinds: set[NodeKind],
) -> None:
    result = parse_source_to_syntax(source)
    result.syntax_arena.validate()
    assert required_kinds <= set(_kinds(result))


def test_source_frontend_preserves_reference_parse_failure() -> None:
    with pytest.raises(ParseError):
        parse_source_to_syntax(
            "fn main() -> i64:\n    return\n"
        )

def test_source_bundle_uses_canonical_file_order_and_shared_symbols() -> None:
    bundle = SourceBundle(
        (
            (
                "zeta.s3",
                "module zeta\nfn value() -> i64:\n    return 2\n",
            ),
            (
                "alpha.s3",
                "module alpha\nfn value() -> i64:\n    return 1\n",
            ),
        )
    )
    first = parse_source_bundle(bundle)
    second = parse_source_bundle(bundle)

    assert tuple(unit.path for unit in first.units) == (
        "alpha.s3",
        "zeta.s3",
    )
    assert first.structural_digest() == second.structural_digest()
    assert first.symbol_names.count("value") == 1
    assert tuple(unit.file_id for unit in first.units) == (0, 1)
    for unit in first.units:
        unit.syntax_arena.validate()

def test_token_arena_rejects_negative_file_id() -> None:
    with pytest.raises(ValueError, match="file_id"):
        TokenArena.from_source("fn main() -> i64:\n    return 0\n", file_id=-1)


def test_source_bundle_rejects_invalid_utf8() -> None:
    bundle = SourceBundle((("bad.s3", b"\xff"),))
    with pytest.raises(Exception, match="valid UTF-8"):
        parse_source_bundle(bundle)

def _logical_tree(result, node_id: int):
    arena = result.syntax_arena
    node = arena.node(node_id)
    payload = arena.payload(node)
    if isinstance(payload, SymbolPayload):
        logical_payload = ("symbol", result.symbol_names[payload.symbol_id])
    elif isinstance(payload, DeclarationPayload):
        logical_payload = (
            "declaration",
            result.symbol_names[payload.symbol_id],
            payload.type_id,
            payload.flags,
        )
    elif isinstance(payload, FunctionPayload):
        logical_payload = (
            "function",
            result.symbol_names[payload.symbol_id],
            payload.return_type_id,
            payload.parameter_count,
            payload.flags,
        )
    elif payload is None:
        logical_payload = None
    else:
        logical_payload = (type(payload).__name__, tuple(vars(payload).values()) if hasattr(payload, "__dict__") else repr(payload))
    return (
        node.kind.value,
        logical_payload,
        tuple(_logical_tree(result, child) for child in arena.child_ids(node_id)),
    )


@pytest.mark.parametrize(
    "source",
    (
        PROGRAM,
        """\
record Box<T: value>:
    value: T
fn read(box: Box<i64>) -> i64:
    return box.value
fn main() -> i64:
    mut box: Box<i64> = Box<i64>(value=7)
    return read(box)
""",
        """\
fn main() -> i64:
    mut total: i64 = 0
    for index: i64 in range(0, 3):
        total += index
    while total < 10:
        total += 1
    return total
""",
        """\
enum Choice:
    None
    Some(value: i64)
fn main() -> i64:
    mut value: i64 = 1
    match value:
        -1:
            return 10
        0:
            return 20
        else:
            return 30
""",
    ),
)
def test_independent_parser_matches_reference_projection_logically(source: str) -> None:
    reference = parse_source_to_syntax(source)
    independent = parse_source_to_syntax_independent(source)

    reference.syntax_arena.validate()
    independent.syntax_arena.validate()

    assert independent.parser_backend == "independent_generic_recursive_descent"
    assert _logical_tree(reference, reference.root_id) == _logical_tree(
        independent, independent.root_id
    )


def test_independent_parser_does_not_require_reference_parser_output() -> None:
    result = parse_source_to_syntax_independent(
        "fn main() -> i64:\n    return (1 + 2) * 3\n"
    )
    assert result.parser_backend == "independent_generic_recursive_descent"
    assert NodeKind.BINARY in _kinds(result)
    result.syntax_arena.validate()


@pytest.mark.parametrize(
    "source",
    (
        "fn main() -> i64:\n    return\n",
        "record Empty:\nfn main() -> i64:\n    return 0\n",
        "fn main() -> i64:\n    mut value: i64 = 1;\n    return value\n",
    ),
)
def test_independent_parser_rejects_malformed_sources(source: str) -> None:
    with pytest.raises(ParseError):
        parse_source_to_syntax_independent(source)


def test_independent_source_bundle_uses_shared_symbol_namespace() -> None:
    bundle = SourceBundle(
        (
            ("b.s3", "module b\nfn value() -> i64:\n    return 2\n"),
            ("a.s3", "module a\nfn value() -> i64:\n    return 1\n"),
        )
    )
    result = parse_source_bundle_independent(bundle)
    assert result.parser_backend == "independent_generic_recursive_descent"
    assert tuple(unit.path for unit in result.units) == ("a.s3", "b.s3")
    assert result.symbol_names.count("value") == 1
    for unit in result.units:
        unit.syntax_arena.validate()

def test_independent_parser_never_calls_reference_parse_tokens(monkeypatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("reference parser bridge must not run")

    monkeypatch.setattr("bootstrap.s3.source_frontend.parse_tokens", forbidden)
    result = parse_source_to_syntax_independent(
        "fn main() -> i64:\n    return 7\n"
    )
    result.syntax_arena.validate()
    assert result.parser_backend == "independent_generic_recursive_descent"