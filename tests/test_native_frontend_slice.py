from __future__ import annotations

import platform
from pathlib import Path

import pytest

from bootstrap.s3 import compile_source, run_source
from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativeToolchain,
    generate_native_assembly,
)
from bootstrap.s3.generic_syntax import (
    IntegerPayload,
    NodeKind,
    OperatorPayload,
    SymbolPayload,
)
from bootstrap.s3.frontend_token_arena import TokenArena
from bootstrap.s3.lexer import SyntaxMode, TokenKind
from bootstrap.s3.source_frontend import parse_source_to_syntax_independent


_ORDINARY_SOURCES = {
    0: "fn main\nreturn 0\n",
    1: "fn main()\nreturn 0\n",
    2: "fn entry()\nreturn 42\n",
    3: "fn worker()\nreturn 7\n",
}
_KIND_CODES = {
    TokenKind.FN: 2,
    TokenKind.IDENTIFIER: 1,
    TokenKind.RETURN: 3,
    TokenKind.INTEGER: 5,
    TokenKind.NEWLINE: 6,
    TokenKind.EOF: 0,
    TokenKind.LEFT_PAREN: 7,
    TokenKind.RIGHT_PAREN: 8,
}
_PARSER_SOURCES = {
    0: "fn entry() -> i64:\n    return 42\n",
    1: "fn worker() -> i64:\n    return 7\n",
}
_BINARY_PARSER_SOURCES = {
    0: "fn calc() -> i64:\n    return 1 + 2\n",
    1: "fn compute() -> i64:\n    return 40 + 2\n",
    4: "fn calc() -> i64:\n    return 1 + 2 * 3\n",
    5: "fn calc() -> i64:\n    return 8 * 3 + 2\n",
    6: "fn calc() -> i64:\n    return 10 + 20 + 30\n",
    7: "fn calc() -> i64:\n    return (1 + 2) * 3\n",
    8: "fn calc() -> i64:\n    return 8 * (3 + 2)\n",
    9: "fn calc() -> i64:\n    return ((1 + 2) * 3)\n",
    14: "fn calc() -> i64:\n    return 1 * 2 * 3\n",
}
_IDENTIFIER_PARSER_SOURCES = {
    0: "fn identity() -> i64:\n    return value\n",
    1: "fn identity() -> i64:\n    return counter\n",
    2: "fn identity() -> i64:\n    return value + 2\n",
    3: "fn identity() -> i64:\n    return 2 + value\n",
    4: "fn identity() -> i64:\n    return left + right\n",
    5: "fn identity() -> i64:\n    return left + right * 3\n",
    6: "fn identity() -> i64:\n    return 3 * value + 2\n",
    7: "fn identity() -> i64:\n    return (left + 2) * right\n",
    8: "fn identity() -> i64:\n    return value other\n",
    9: "fn identity() -> i64:\n    return value +\n",
    10: "fn identity() -> i64:\n    return unknown\n",
}
_SEQUENCE_PARSER_SOURCES = {
    0: "fn sequence() -> i64:\n    return 1\n",
    1: "fn sequence() -> i64:\n    return 1\n    return 2\n",
    2: "fn sequence() -> i64:\n    return 1\n    return 2\n    return 3\n",
    3: "fn sequence() -> i64:\n    return 2\n    return 1\n",
    4: "fn sequence() -> i64:\n    return 1\n    return\n",
    5: "fn sequence() -> i64:\n    return 1\n    garbage\n    return 2\n",
    6: "fn sequence() -> i64:\n    return 1\ntrailing\n",
}
_PROGRAM_PARSER_SOURCES = {
    0: "fn main() -> i64:\n    value: i64 = 40\n    return value\n",
    1: "fn calculate() -> i64:\n    base: i64 = 40\n    answer: i64 = base + 2\n    return answer\n",
    2: "fn grouped() -> i64:\n    value: i64 = (1 + 2) * 3\n    return value\n",
    3: "fn grouped() -> i64:\n    mut value: i64 = 1\n    value = value + 1\n    return value\n",
    4: "fn add(a: i64, b: i64) -> i64:\n    result: i64 = a + b\n    return result\n",
    5: "fn add(a: i64, b: i64) -> i64:\n    result: i64 = a + b\n    return result\n\nfn main() -> i64:\n    value: i64 = 40\n    return value\n",
    6: "fn bad() -> i64:\n    : i64 = 1\n",
    7: "fn bad() -> i64:\n    value: i64\n",
    8: "fn main() -> i64:\n    value: i64 = 40\ntrailing\n",
    9: "fn add(a: i64, b: i64) -> i64:\n    result: i64 = a + b\n    return result\n\nfn main() -> i64:\n    value: i64 = add(40, 2)\n    return value\n",
}
_PROGRAM_CALL_SOURCES = {
    0: "fn add() -> i64:\n    return 40\n\nfn main() -> i64:\n    value: i64 = add()\n    return value\n",
    1: "fn add(a: i64, b: i64) -> i64:\n    result: i64 = a + b\n    return result\n\nfn main() -> i64:\n    value: i64 = add(40)\n    return value\n",
    2: "fn add(a: i64, b: i64) -> i64:\n    result: i64 = a + b\n    return result\n\nfn main() -> i64:\n    value: i64 = add(40, 2)\n    return value\n",
    3: "fn add(a: i64, b: i64) -> i64:\n    result: i64 = a + b\n    return result\n\nfn main() -> i64:\n    value: i64 = add(40 + 1, 2 * 3)\n    return value\n",
}
_WHILE_PROGRAM_SOURCE = (
    "fn main() -> i64:\n"
    "    while 1:\n"
    "        return 1\n"
    "    return 2\n"
)
_COMPARISON_PROGRAM_SOURCE = (
    "fn main() -> i64:\n"
    "    mut a: i64 = 1\n"
    "    b: i64 = 2\n"
    "    while a < b:\n"
    "        a = a + 1\n"
    "    return a\n"
)


def _candidate_source(case_id: int) -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    return (
        substrate
        + f"\nfn main() -> i64:\n    return generic_lexer_native_case({case_id})\n"
    )


def _candidate_parser_source(case_id: int) -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    return (
        substrate
        + f"\nfn main() -> i64:\n    return generic_native_parser_case({case_id})\n"
    )


def _candidate_binary_parser_source(case_id: int) -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    return (
        substrate
        + f"\nfn main() -> i64:\n    return generic_native_parser_binary_case({case_id})\n"
    )


def _candidate_identifier_parser_source(case_id: int) -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    return (
        substrate
        + f"\nfn main() -> i64:\n    return generic_native_parser_identifier_case({case_id})\n"
    )


def _candidate_sequence_parser_source(case_id: int) -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    return (
        substrate
        + f"\nfn main() -> i64:\n    return generic_native_parser_sequence_case({case_id})\n"
    )


def _candidate_program_parser_source(case_id: int) -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    return (
        substrate
        + f"\nfn main() -> i64:\n    return generic_native_parser_program_case_v2({case_id})\n"
    )


def _candidate_call_program_parser_source(case_id: int) -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    return (
        substrate
        + f"\nfn main() -> i64:\n    return generic_native_parser_program_call_case({case_id})\n"
    )


def _candidate_while_program_parser_source() -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    return (
        substrate
        + "\nfn main() -> i64:\n    return generic_native_parser_program_while_case()\n"
    )


def _candidate_comparison_program_parser_source() -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    return (
        substrate
        + "\nfn main() -> i64:\n    return generic_native_parser_program_comparison_case()\n"
    )


def _candidate_generic_call_parser_source(expression: str) -> str:
    repository = Path(__file__).parents[1]
    substrate = (
        repository / "selfhost/substrate/generic_lexer_state.s3"
    ).read_text(encoding="utf-8")
    encoded = expression.encode("ascii")
    lines = [
        "fn main() -> i64:",
        f"    mut source: vector<i64> = vector_new<i64>({len(encoded)})",
    ]
    lines.extend(
        f"    discard vector_push<i64>(&mut source, {byte})"
        for byte in encoded
    )
    lines.extend(
        (
            "    mut tokens: vector<i64> = generic_lexer_scan(&source)",
            "    mut tree: vector<i64> = generic_native_parser_parse_expression(&source, &tokens, 0, 0)",
            "    mut packed: i64 = generic_expression_packed_result(&tree)",
            "    match packed >= 0:",
            "        -1:",
            "            mut node: i64 = generic_native_parser_packed_node(packed)",
            "            return generic_expression_node_kind(&tree, node) * 100 + generic_expression_node_value(&tree, node)",
            "        0:",
            "            return -1",
            "        1:",
            "            return -1",
        )
    )
    return substrate + "\n" + "\n".join(lines) + "\n"


def _independent_digest(source: str) -> int:
    arena = TokenArena.from_source_independent(
        source,
        mode=SyntaxMode.V0_6,
    )
    digest = 0
    for token_id in range(len(arena)):
        record = arena.token(token_id)
        digest += token_id * 3
        digest += _KIND_CODES[record.kind] * 5
        digest += record.span.start * 7
        digest += record.span.end * 11
    return digest


def _independent_parser_digest(source: str) -> int:
    parsed = parse_source_to_syntax_independent(source)
    arena = parsed.syntax_arena
    function = next(
        node for _, node in arena.nodes.items() if node.kind is NodeKind.FUNCTION
    )
    return_node = next(
        node for _, node in arena.nodes.items() if node.kind is NodeKind.RETURN
    )
    integer = next(
        node
        for _, node in arena.nodes.items()
        if node.kind is NodeKind.INTEGER_LITERAL
    )
    integer_payload = arena.payload(integer)
    assert isinstance(integer_payload, IntegerPayload)
    tokens = TokenArena.from_source_independent(source, mode=SyntaxMode.V0_6)
    name_token = next(
        token
        for _, token in tokens.tokens.items()
        if token.kind is TokenKind.IDENTIFIER and token.text != "i64"
    )
    name_digest = 0
    for unit in source[name_token.span.start:name_token.span.end].encode("utf-8"):
        name_digest = name_digest * 31 + unit
    native_token_count = len(tokens) - sum(
        token.kind in {TokenKind.INDENT, TokenKind.DEDENT}
        for _, token in tokens.tokens.items()
    ) + 1
    digest = name_digest * 11
    digest += name_token.span.start * 13
    digest += name_token.span.end * 17
    digest += return_node.span.start * 19
    digest += integer.span.start * 23
    digest += integer.span.end * 29
    digest += integer_payload.value * 31
    digest += native_token_count * 37
    assert function.span.start == 0
    return digest


def _independent_binary_parser_digest(source: str) -> int:
    parsed = parse_source_to_syntax_independent(source)
    arena = parsed.syntax_arena
    function = next(
        node for _, node in arena.nodes.items() if node.kind is NodeKind.FUNCTION
    )
    return_node = next(
        node for _, node in arena.nodes.items() if node.kind is NodeKind.RETURN
    )
    def tree_digest(node_id: int) -> int:
        node = arena.node(node_id)
        payload = arena.payload(node)
        operator = payload.operator_id + 1 if isinstance(payload, OperatorPayload) else 0
        digest = (
            (2 if node.kind is NodeKind.BINARY else 1) * 97
            + operator * 101
            + node.span.start * 103
            + node.span.end * 107
        )
        if node.kind is NodeKind.INTEGER_LITERAL:
            assert isinstance(payload, IntegerPayload)
            return digest + payload.value * 109
        assert node.kind is NodeKind.BINARY
        children = arena.child_ids(node.id)
        assert len(children) == 2
        return digest + tree_digest(children[0]) * 113 + tree_digest(children[1]) * 127

    expression = next(
        child
        for child_id in arena.child_ids(return_node.id)
        for child in (arena.node(child_id),)
        if child.kind in {NodeKind.BINARY, NodeKind.INTEGER_LITERAL}
    )
    tokens = TokenArena.from_source_independent(source, mode=SyntaxMode.V0_6)
    name_token = next(
        token
        for _, token in tokens.tokens.items()
        if token.kind is TokenKind.IDENTIFIER and token.text != "i64"
    )
    name_digest = 0
    for unit in source[name_token.span.start:name_token.span.end].encode("utf-8"):
        name_digest = name_digest * 31 + unit
    native_token_count = len(tokens) - sum(
        token.kind in {TokenKind.INDENT, TokenKind.DEDENT}
        for _, token in tokens.tokens.items()
    ) + 1
    digest = tree_digest(expression.id)
    digest += name_digest * 11
    digest += name_token.span.start * 13
    digest += name_token.span.end * 17
    digest += return_node.span.start * 19
    digest += native_token_count * 37
    assert function.span.start == 0
    return digest


def _independent_identifier_parser_digest(source: str) -> int:
    parsed = parse_source_to_syntax_independent(source)
    arena = parsed.syntax_arena
    function = next(
        node for _, node in arena.nodes.items() if node.kind is NodeKind.FUNCTION
    )
    return_node = next(
        node for _, node in arena.nodes.items() if node.kind is NodeKind.RETURN
    )

    def tree_digest(node_id: int) -> int:
        node = arena.node(node_id)
        payload = arena.payload(node)
        operator = payload.operator_id + 1 if isinstance(payload, OperatorPayload) else 0
        digest = (
            (2 if node.kind is NodeKind.BINARY else 3 if node.kind is NodeKind.IDENTIFIER else 1 if node.kind is NodeKind.INTEGER_LITERAL else 0) * 97
            + operator * 101
            + node.span.start * 103
            + node.span.end * 107
        )
        if node.kind is NodeKind.INTEGER_LITERAL:
            assert isinstance(payload, IntegerPayload)
            return digest + payload.value * 109
        if node.kind is NodeKind.IDENTIFIER:
            name_digest = 0
            for unit in source[node.span.start:node.span.end].encode("utf-8"):
                name_digest = name_digest * 31 + unit
            return digest + name_digest * 109
        assert node.kind is NodeKind.BINARY
        children = arena.child_ids(node.id)
        assert len(children) == 2
        return digest + tree_digest(children[0]) * 113 + tree_digest(children[1]) * 127

    expression = next(
        arena.node(child_id)
        for child_id in arena.child_ids(return_node.id)
        if arena.node(child_id).kind
        in {NodeKind.BINARY, NodeKind.INTEGER_LITERAL, NodeKind.IDENTIFIER}
    )
    tokens = TokenArena.from_source_independent(source, mode=SyntaxMode.V0_6)
    name_token = next(
        token
        for _, token in tokens.tokens.items()
        if token.kind is TokenKind.IDENTIFIER and token.text != "i64"
    )
    name_digest = 0
    for unit in source[name_token.span.start:name_token.span.end].encode("utf-8"):
        name_digest = name_digest * 31 + unit
    native_token_count = len(tokens) - sum(
        token.kind in {TokenKind.INDENT, TokenKind.DEDENT}
        for _, token in tokens.tokens.items()
    ) + 1
    digest = tree_digest(expression.id)
    digest += name_digest * 11
    digest += name_token.span.start * 13
    digest += name_token.span.end * 17
    digest += return_node.span.start * 19
    digest += native_token_count * 37
    assert function.span.start == 0
    return digest


def _sequence_tree_digest(arena, source: str, node_id: int) -> int:
    node = arena.node(node_id)
    payload = arena.payload(node)
    kind = (
        2 if node.kind is NodeKind.BINARY
        else 3 if node.kind is NodeKind.IDENTIFIER
        else 1 if node.kind is NodeKind.INTEGER_LITERAL
        else 0
    )
    operator = payload.operator_id + 1 if isinstance(payload, OperatorPayload) else 0
    digest = kind * 97 + operator * 101 + node.span.start * 103 + node.span.end * 107
    if node.kind is NodeKind.INTEGER_LITERAL:
        assert isinstance(payload, IntegerPayload)
        return digest + payload.value * 109
    if node.kind is NodeKind.IDENTIFIER:
        name_digest = 0
        for unit in source[node.span.start:node.span.end].encode("utf-8"):
            name_digest = name_digest * 31 + unit
        return digest + name_digest * 109
    assert node.kind is NodeKind.BINARY
    children = arena.child_ids(node.id)
    assert len(children) == 2
    return digest + _sequence_tree_digest(arena, source, children[0]) * 113 + _sequence_tree_digest(arena, source, children[1]) * 127


def _independent_sequence_parser_digest(source: str) -> int:
    parsed = parse_source_to_syntax_independent(source)
    arena = parsed.syntax_arena
    function = next(
        node for _, node in arena.nodes.items() if node.kind is NodeKind.FUNCTION
    )
    function_children = arena.child_ids(function.id)
    block = arena.node(function_children[1])
    assert block.kind is NodeKind.BLOCK
    sequence_digest = 0
    block_children = arena.child_ids(block.id)
    for child_id in block_children:
        statement = arena.node(child_id)
        assert statement.kind is NodeKind.RETURN
        expression_id = arena.child_ids(statement.id)[0]
        expression_digest = _sequence_tree_digest(arena, source, expression_id)
        statement_digest = (
            4 * 97
            + 3 * 101
            + statement.span.start * 103
            + statement.span.end * 107
            + expression_digest * 109
        )
        sequence_digest = sequence_digest * 131 + statement_digest
    tokens = TokenArena.from_source_independent(source, mode=SyntaxMode.V0_6)
    name_token = next(
        token
        for _, token in tokens.tokens.items()
        if token.kind is TokenKind.IDENTIFIER and token.text != "i64"
    )
    name_digest = 0
    for unit in source[name_token.span.start:name_token.span.end].encode("utf-8"):
        name_digest = name_digest * 31 + unit
    native_token_count = len(tokens) - sum(
        token.kind in {TokenKind.INDENT, TokenKind.DEDENT}
        for _, token in tokens.tokens.items()
    ) + 1
    return (
        sequence_digest
        + name_digest * 11
        + name_token.span.start * 13
        + name_token.span.end * 17
        + block.span.start * 19
        + block.span.end * 23
        + len(block_children) * 29
        + native_token_count * 37
    )


def _program_name_digest(source: str, start: int, end: int) -> int:
    digest = 0
    for unit in source[start:end].encode("utf-8"):
        digest = digest * 31 + unit
    return digest


def _program_identifier_token(source: str, start: int, end: int):
    tokens = TokenArena.from_source_independent(source, mode=SyntaxMode.V0_6)
    return next(
        token
        for _, token in tokens.tokens.items()
        if token.kind is TokenKind.IDENTIFIER
        and start <= token.span.start < token.span.end <= end
        and source[token.span.start:token.span.end] != "i64"
    )


def _independent_program_parser_digest(source: str) -> int:
    parsed = parse_source_to_syntax_independent(source)
    arena = parsed.syntax_arena

    def tree_digest(node_id: int) -> int:
        node = arena.node(node_id)
        if node.kind is not NodeKind.CALL:
            return _sequence_tree_digest(arena, source, node_id)
        children = arena.child_ids(node.id)
        assert children
        callee_digest = tree_digest(children[0])
        argument_chain = 0
        for argument_id in reversed(children[1:]):
            argument = arena.node(argument_id)
            argument_children = arena.child_ids(argument.id)
            assert len(argument_children) == 1
            expression_id = argument_children[0]
            expression = arena.node(expression_id)
            link_digest = (
                5 * 97
                + tree_digest(expression_id) * 113
                + expression.span.start * 103
                + expression.span.end * 107
            )
            if argument_chain:
                link_digest += argument_chain * 127
            argument_chain = link_digest
        digest = (
            4 * 97
            + (len(children) - 1) * 101
            + node.span.start * 103
            + node.span.end * 107
            + callee_digest * 113
        )
        if argument_chain:
            digest += argument_chain * 127
        return digest

    def statement_digest(statement_id: int) -> int:
        statement = arena.node(statement_id)
        children = arena.child_ids(statement.id)
        if statement.kind is NodeKind.WHILE:
            condition_id, block_id = children
            block = arena.node(block_id)
            block_children = arena.child_ids(block.id)
            assert block_children
            block_digest = 0
            for body_statement_id in block_children:
                block_digest = block_digest * 131 + statement_digest(body_statement_id)
            return (
                8 * 97
                + tree_digest(condition_id) * 101
                + block_digest * 103
                + statement.span.start * 107
                + arena.node(block_children[0]).span.start * 109
                + block.span.end * 113
                + len(block_children) * 127
            )
        if statement.kind is NodeKind.RETURN:
            expression_id = children[0]
            expression = arena.node(expression_id)
            return (
                7 * 97
                + tree_digest(expression_id) * 101
                + statement.span.start * 103
                + expression.span.end * 107
            )
        if statement.kind is NodeKind.VARIABLE_DECLARATION:
            declaration = arena.payload(statement)
            name = _program_identifier_token(
                source,
                statement.span.start,
                statement.span.end,
            )
            expression = arena.node(children[1])
            mutable = getattr(declaration, "flags", 0) & 1
            return (
                5 * 97
                + _program_name_digest(source, name.span.start, name.span.end) * 101
                + 2 * 103
                + mutable * 107
                + tree_digest(children[1]) * 109
                + statement.span.start * 113
                + expression.span.end * 127
            )
        if statement.kind is NodeKind.ASSIGNMENT:
            target = arena.node(children[0])
            expression = arena.node(children[1])
            return (
                6 * 97
                + _program_name_digest(source, target.span.start, target.span.end) * 101
                + tree_digest(children[1]) * 103
                + statement.span.start * 107
                + expression.span.end * 109
            )
        raise AssertionError(f"unsupported program statement: {statement.kind}")

    def function_digest(function_id: int) -> int:
        function = arena.node(function_id)
        payload = arena.payload(function)
        name = _program_identifier_token(source, function.span.start, function.span.end)
        function_children = arena.child_ids(function.id)
        block = arena.node(payload.body_id)
        parameters = [
            arena.node(child_id)
            for child_id in function_children
            if arena.node(child_id).kind is NodeKind.PARAMETER
        ]
        parameter_digest = 0
        for parameter in parameters:
            parameter_name = _program_identifier_token(
                source,
                parameter.span.start,
                parameter.span.end,
            )
            parameter_term = (
                _program_name_digest(
                    source,
                    parameter_name.span.start,
                    parameter_name.span.end,
                ) * 11
                + parameter_name.span.start * 13
                + parameter_name.span.end * 17
                + 2 * 19
            )
            parameter_digest = parameter_digest * 131 + parameter_term
        block_digest = 0
        block_children = arena.child_ids(block.id)
        for statement_id in block_children:
            block_digest = block_digest * 131 + statement_digest(statement_id)
        return (
            _program_name_digest(source, name.span.start, name.span.end) * 11
            + name.span.start * 13
            + name.span.end * 17
            + 2 * 19
            + parameter_digest * 23
            + len(parameters) * 29
            + block_digest * 31
            + block.span.start * 37
            + block.span.end * 41
            + len(block_children) * 43
        )

    program = next(
        node for _, node in arena.nodes.items() if node.kind is NodeKind.PROGRAM
    )
    functions = [
        child_id
        for child_id in arena.child_ids(program.id)
        if arena.node(child_id).kind is NodeKind.FUNCTION
    ]
    digest = 0
    for function_id in functions:
        digest = digest * 131 + function_digest(function_id)
    return digest + len(functions) * 47


def _identifier_expression_node(source: str):
    parsed = parse_source_to_syntax_independent(source)
    arena = parsed.syntax_arena
    return_node = next(
        node for _, node in arena.nodes.items() if node.kind is NodeKind.RETURN
    )
    expression = next(
        arena.node(child_id)
        for child_id in arena.child_ids(return_node.id)
        if arena.node(child_id).kind
        in {NodeKind.BINARY, NodeKind.INTEGER_LITERAL, NodeKind.IDENTIFIER}
    )
    return arena, expression


def _binary_expression_node(source: str):
    parsed = parse_source_to_syntax_independent(source)
    arena = parsed.syntax_arena
    return_node = next(
        node for _, node in arena.nodes.items() if node.kind is NodeKind.RETURN
    )
    expression = next(
        arena.node(child_id)
        for child_id in arena.child_ids(return_node.id)
        if arena.node(child_id).kind is NodeKind.BINARY
    )
    return arena, expression


@pytest.mark.parametrize(
    "case_id,root_operator,left_operator,right_operator",
    (
        (4, 0, None, 2),
        (5, 0, 2, None),
        (6, 0, 0, None),
        (7, 2, 0, None),
        (8, 2, None, 0),
        (9, 2, 0, None),
        (14, 2, 2, None),
    ),
)
def test_independent_expression_oracle_proves_precedence_and_grouping_shape(
    case_id: int,
    root_operator: int,
    left_operator: int | None,
    right_operator: int | None,
) -> None:
    arena, root = _binary_expression_node(_BINARY_PARSER_SOURCES[case_id])
    root_payload = arena.payload(root)
    assert isinstance(root_payload, OperatorPayload)
    assert root_payload.operator_id == root_operator
    children = arena.child_ids(root.id)
    assert len(children) == 2
    if left_operator is not None:
        left_payload = arena.payload(arena.node(children[0]))
        assert isinstance(left_payload, OperatorPayload)
        assert left_payload.operator_id == left_operator
    if right_operator is not None:
        right_payload = arena.payload(arena.node(children[1]))
        assert isinstance(right_payload, OperatorPayload)
        assert right_payload.operator_id == right_operator


def test_native_binary_expression_mutation_changes_structural_digest() -> None:
    assert run_source(_candidate_binary_parser_source(4)) != run_source(
        _candidate_binary_parser_source(14)
    )


@pytest.mark.parametrize(
    "case_id,expected_digest",
    ((0, 1509), (1, 2101), (2, 2285), (3, 2375)),
)
def test_ordinary_s3_lexer_slice_matches_independent_generic_frontend(
    case_id: int,
    expected_digest: int,
) -> None:
    expected = _independent_digest(_ORDINARY_SOURCES[case_id])
    assert expected == expected_digest
    assert run_source(_candidate_source(case_id)) == expected


@pytest.mark.s3_native
def test_ordinary_s3_lexer_slice_qualifies_on_linux_x86_64(
    tmp_path: Path,
) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        pytest.skip("ordinary S3 lexer qualification requires Linux x86-64")
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))

    for case_id, expected_digest in (
        (0, 1509),
        (1, 2101),
        (2, 2285),
        (3, 2375),
    ):
        compilation = compile_source(_candidate_source(case_id))
        executable = toolchain.build(
            generate_native_assembly(compilation.assembly),
            tmp_path / f"ordinary-s3-lexer-slice-{case_id}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == f"program returned: {expected_digest}\n"
        assert completed.stderr == ""


@pytest.mark.parametrize(
    "case_id,expected_digest",
    ((0, 1063349395), (1, 38641705493)),
)
def test_native_parser_minimal_function_matches_independent_syntax_oracle(
    case_id: int,
    expected_digest: int,
) -> None:
    expected = _independent_parser_digest(_PARSER_SOURCES[case_id])
    assert expected == expected_digest
    assert run_source(_candidate_parser_source(case_id)) == expected


@pytest.mark.parametrize("case_id", (2, 3))
def test_native_parser_minimal_function_rejects_malformed_input(case_id: int) -> None:
    assert run_source(_candidate_parser_source(case_id)) == -1


@pytest.mark.parametrize(
    ("expression", "expected"),
    (
        ("vector_get<i64>(view, 0)", 402),
        ("vector_get<f64>(view, 0)", 403),
        ("vector_get(view, 0)", 400),
        ("left < right", 200),
    ),
)
def test_native_expression_parser_preserves_generic_call_type_argument(
    expression: str,
    expected: int,
) -> None:
    assert run_source(_candidate_generic_call_parser_source(expression)) == expected


@pytest.mark.parametrize(
    "case_id,expected_digest",
    tuple((case_id, _independent_binary_parser_digest(source)) for case_id, source in _BINARY_PARSER_SOURCES.items()),
)
def test_native_binary_expression_matches_independent_syntax_oracle(
    case_id: int,
    expected_digest: int,
) -> None:
    expected = _independent_binary_parser_digest(_BINARY_PARSER_SOURCES[case_id])
    assert expected == expected_digest
    assert run_source(_candidate_binary_parser_source(case_id)) == expected


@pytest.mark.parametrize("case_id", (2, 3, 10, 11, 12, 13))
def test_native_binary_expression_rejects_malformed_input(case_id: int) -> None:
    assert run_source(_candidate_binary_parser_source(case_id)) == -1


@pytest.mark.parametrize("case_id", (0, 1, 10))
def test_native_identifier_primary_matches_independent_syntax_oracle(case_id: int) -> None:
    source = _IDENTIFIER_PARSER_SOURCES[case_id]
    arena, expression = _identifier_expression_node(source)
    assert expression.kind is NodeKind.IDENTIFIER
    assert isinstance(arena.payload(expression), SymbolPayload)
    assert source[expression.span.start:expression.span.end] in {
        "value",
        "counter",
        "unknown",
    }
    expected = _independent_identifier_parser_digest(source)
    assert run_source(_candidate_identifier_parser_source(case_id)) == expected


@pytest.mark.parametrize("case_id", (2, 3, 4, 5, 6, 7))
def test_native_identifier_binary_expression_matches_independent_syntax_oracle(
    case_id: int,
) -> None:
    source = _IDENTIFIER_PARSER_SOURCES[case_id]
    arena, expression = _identifier_expression_node(source)
    assert expression.kind is NodeKind.BINARY
    assert run_source(_candidate_identifier_parser_source(case_id)) == (
        _independent_identifier_parser_digest(source)
    )


def test_native_identifier_payload_is_source_derived() -> None:
    assert run_source(_candidate_identifier_parser_source(0)) != run_source(
        _candidate_identifier_parser_source(1)
    )
    assert run_source(_candidate_identifier_parser_source(4)) != run_source(
        _candidate_identifier_parser_source(5)
    )


@pytest.mark.parametrize("case_id", (8, 9))
def test_native_identifier_expression_rejects_malformed_input(case_id: int) -> None:
    assert run_source(_candidate_identifier_parser_source(case_id)) == -1


@pytest.mark.parametrize("case_id", (0, 1, 2))
def test_native_statement_sequence_matches_independent_block_oracle(case_id: int) -> None:
    source = _SEQUENCE_PARSER_SOURCES[case_id]
    expected = _independent_sequence_parser_digest(source)
    assert run_source(_candidate_sequence_parser_source(case_id)) == expected


def test_native_statement_sequence_preserves_count_and_order() -> None:
    one = run_source(_candidate_sequence_parser_source(0))
    two = run_source(_candidate_sequence_parser_source(1))
    three = run_source(_candidate_sequence_parser_source(2))
    reversed_two = run_source(_candidate_sequence_parser_source(3))
    assert one == _independent_sequence_parser_digest(_SEQUENCE_PARSER_SOURCES[0])
    assert two == _independent_sequence_parser_digest(_SEQUENCE_PARSER_SOURCES[1])
    assert three == _independent_sequence_parser_digest(_SEQUENCE_PARSER_SOURCES[2])
    assert reversed_two == _independent_sequence_parser_digest(_SEQUENCE_PARSER_SOURCES[3])
    assert len({one, two, three}) == 3
    assert two != reversed_two


@pytest.mark.parametrize("case_id", (4, 5, 6))
def test_native_statement_sequence_rejects_incomplete_internal_and_trailing_source(
    case_id: int,
) -> None:
    with pytest.raises(Exception):
        parse_source_to_syntax_independent(_SEQUENCE_PARSER_SOURCES[case_id])
    assert run_source(_candidate_sequence_parser_source(case_id)) == -1


def test_native_statement_sequence_has_no_reference_frontend_fallback() -> None:
    source = _candidate_sequence_parser_source(1)
    for forbidden in (
        "GenericLexer(",
        "GenericParser(",
        "tokenize(",
        "parse_tokens(",
        "bootstrap.s3.ast",
    ):
        assert forbidden not in source
    parser_source = source.split("export fn generic_native_parser_sequence_case", 1)[0]
    assert "generic_native_parser_sequence_case(case_id" not in parser_source


@pytest.mark.parametrize(
    "case_id,source",
    tuple((case_id, source) for case_id, source in _PROGRAM_PARSER_SOURCES.items() if case_id < 6),
)
def test_native_program_frontend_matches_independent_program_oracle(
    case_id: int,
    source: str,
) -> None:
    expected = _independent_program_parser_digest(source)
    assert run_source(_candidate_program_parser_source(case_id)) == expected


@pytest.mark.parametrize("case_id", (6, 7, 8))
def test_native_program_frontend_rejects_structural_failures(case_id: int) -> None:
    with pytest.raises(Exception):
        parse_source_to_syntax_independent(_PROGRAM_PARSER_SOURCES[case_id])
    assert run_source(_candidate_program_parser_source(case_id)) == -1


def test_native_program_frontend_preserves_call_callee_and_argument_order() -> None:
    for case_id, source in _PROGRAM_CALL_SOURCES.items():
        expected = _independent_program_parser_digest(source)
        assert run_source(_candidate_call_program_parser_source(case_id)) == expected
    swapped = _PROGRAM_CALL_SOURCES[2].replace("add(40, 2)", "add(2, 40)")
    assert _independent_program_parser_digest(swapped) != (
        _independent_program_parser_digest(_PROGRAM_CALL_SOURCES[2])
    )


def test_native_program_frontend_preserves_nested_while_and_outer_continuation() -> None:
    expected = _independent_program_parser_digest(_WHILE_PROGRAM_SOURCE)
    assert run_source(_candidate_while_program_parser_source()) == expected


def test_native_program_frontend_preserves_relational_loop_state() -> None:
    expected = _independent_program_parser_digest(_COMPARISON_PROGRAM_SOURCE)
    assert run_source(_candidate_comparison_program_parser_source()) == expected


def test_native_program_frontend_has_no_reference_frontend_fallback() -> None:
    source = _candidate_program_parser_source(5)
    for forbidden in (
        "GenericLexer(",
        "GenericParser(",
        "tokenize(",
        "parse_tokens(",
        "bootstrap.s3.ast",
    ):
        assert forbidden not in source
    parser_source = source.split("export fn generic_native_parser_program_digest", 1)[0]
    assert "generic_native_program_case_v2" not in parser_source


@pytest.mark.s3_native
def test_native_statement_sequence_qualifies_on_linux_x86_64(
    tmp_path: Path,
) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        pytest.skip("ordinary S3 statement sequence qualification requires Linux x86-64")
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))

    for case_id in (0, 1, 2, 3):
        source = _SEQUENCE_PARSER_SOURCES[case_id]
        compilation = compile_source(_candidate_sequence_parser_source(case_id))
        executable = toolchain.build(
            generate_native_assembly(compilation.assembly),
            tmp_path / f"ordinary-s3-sequence-{case_id}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == (
            f"program returned: {_independent_sequence_parser_digest(source)}\n"
        )
        assert completed.stderr == ""

    for case_id in (4, 5, 6):
        compilation = compile_source(_candidate_sequence_parser_source(case_id))
        executable = toolchain.build(
            generate_native_assembly(compilation.assembly),
            tmp_path / f"ordinary-s3-sequence-negative-{case_id}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == "program returned: -1\n"
        assert completed.stderr == ""


def test_native_parser_slice_has_no_reference_frontend_fallback() -> None:
    source = _candidate_parser_source(0)
    for forbidden in (
        "GenericLexer(",
        "GenericParser(",
        "tokenize(",
        "parse_tokens(",
        "bootstrap.s3.ast",
    ):
        assert forbidden not in source
    parser_source = source.split("export fn generic_native_parser_case", 1)[0]
    for fixture_literal in ("calc", "compute", "entry", "worker"):
        assert fixture_literal not in parser_source


@pytest.mark.s3_native
def test_native_parser_minimal_function_qualifies_on_linux_x86_64(
    tmp_path: Path,
) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {
        "x86_64",
        "amd64",
    }:
        pytest.skip("ordinary S3 parser qualification requires Linux x86-64")
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))

    for case_id, expected_digest in ((0, 1063349395), (1, 38641705493)):
        compilation = compile_source(_candidate_parser_source(case_id))
        executable = toolchain.build(
            generate_native_assembly(compilation.assembly),
            tmp_path / f"ordinary-s3-parser-slice-{case_id}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == f"program returned: {expected_digest}\n"
        assert completed.stderr == ""

    for case_id in (2, 3):
        compilation = compile_source(_candidate_parser_source(case_id))
        executable = toolchain.build(
            generate_native_assembly(compilation.assembly),
            tmp_path / f"ordinary-s3-parser-slice-negative-{case_id}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == "program returned: -1\n"
        assert completed.stderr == ""

    for case_id in _BINARY_PARSER_SOURCES:
        compilation = compile_source(_candidate_binary_parser_source(case_id))
        executable = toolchain.build(
            generate_native_assembly(compilation.assembly),
            tmp_path / f"ordinary-s3-binary-parser-slice-{case_id}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == (
            f"program returned: "
            f"{_independent_binary_parser_digest(_BINARY_PARSER_SOURCES[case_id])}\n"
        )
        assert completed.stderr == ""

    for case_id in (2, 3, 10, 11, 12, 13):
        compilation = compile_source(_candidate_binary_parser_source(case_id))
        executable = toolchain.build(
            generate_native_assembly(compilation.assembly),
            tmp_path / f"ordinary-s3-binary-parser-negative-{case_id}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == "program returned: -1\n"
        assert completed.stderr == ""

    for case_id in _IDENTIFIER_PARSER_SOURCES:
        compilation = compile_source(_candidate_identifier_parser_source(case_id))
        executable = toolchain.build(
            generate_native_assembly(compilation.assembly),
            tmp_path / f"ordinary-s3-identifier-parser-{case_id}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        expected = (
            -1
            if case_id in {8, 9}
            else _independent_identifier_parser_digest(
                _IDENTIFIER_PARSER_SOURCES[case_id]
            )
        )
        assert completed.stdout == f"program returned: {expected}\n"
        assert completed.stderr == ""
