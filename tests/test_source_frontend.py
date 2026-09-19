from __future__ import annotations

import pytest

from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.generic_syntax import (
    FunctionPayload,
    NodeKind,
    PayloadKind,
)
from bootstrap.s3.lexer import SyntaxMode, TokenKind, tokenize
from bootstrap.s3.source_frontend import TokenArena, parse_source_to_syntax


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
