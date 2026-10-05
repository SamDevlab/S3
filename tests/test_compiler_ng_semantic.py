from __future__ import annotations

import json
from pathlib import Path

import pytest

from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.pipeline import compile_source


_ROOT = Path(__file__).parents[1]


def _module_body(relative_path: str) -> str:
    return "\n".join(
        line
        for line in (_ROOT / relative_path).read_text(encoding="utf-8").splitlines()
        if not line.startswith("module ") and not line.startswith("from ")
    )


_NG_SOURCE = "\n".join(
    (
        _module_body("selfhost/compiler_ng/character_classes.s3"),
        _module_body("selfhost/compiler_ng/lexer.s3"),
        _module_body("selfhost/compiler_ng/parser.s3"),
        _module_body("selfhost/compiler_ng/semantic.s3"),
    )
)


def _ng_semantic_status(source: str) -> int:
    wrapper = f"""
fn main() -> i64:
    mut source_text: text = text_from_static({json.dumps(source)})
    mut source_bytes: bytes = bytes_from_text(&source_text)
    mut tokens: vector<NgToken> = vector_new<NgToken>({len(source.encode("utf-8")) + 1})
    mut functions: vector<NgFunction> = vector_new<NgFunction>({len(source.encode("utf-8")) + 1})
    mut parameters: vector<NgParameter> = vector_new<NgParameter>({len(source.encode("utf-8")) + 1})
    mut nodes: vector<NgAstNode> = vector_new<NgAstNode>({len(source.encode("utf-8")) + 1})
    mut lex_status: i64 = ng_lex(&source_bytes, &mut tokens)
    match lex_status <=> 0:
        -1:
            return -1
        0:
            mut parse_status: i64 = ng_parse_program(&source_bytes, &tokens, &mut functions, &mut parameters, &mut nodes)
            match parse_status <=> 0:
                -1:
                    return -2
                0:
                    return ng_check_program(&source_bytes, &functions, &parameters, &nodes)
                1:
                    return -2
        1:
            return -1
"""
    compilation = compile_source(_NG_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    return int(execute_ir(compilation.ir))


def test_nextgen_semantic_pass_accepts_resolved_typed_parameters_and_arithmetic() -> None:
    source = (
        "fn add(left: i64, right: i64) -> i64:\n    return left + right * 2\n"
        "fn main() -> i64:\n    return 0\n"
    )
    assert compile_source(source).ir is not None
    assert _ng_semantic_status(source) == 0


def test_nextgen_semantic_pass_resolves_forward_calls_and_argument_types() -> None:
    source = (
        "fn main() -> i64:\n    return add(20, 22)\n"
        "fn add(left: i64, right: i64) -> i64:\n    return left + right\n"
    )
    assert compile_source(source).ir is not None
    assert _ng_semantic_status(source) == 0


def test_nextgen_semantic_pass_tracks_initialized_mutable_locals() -> None:
    source = (
        "fn add_one(value: i64) -> i64:\n"
        "    mut current: i64 = value\n"
        "    current = current + 1\n"
        "    return current\n"
        "fn main() -> i64:\n    return add_one(41)\n"
    )
    assert compile_source(source).ir is not None
    assert _ng_semantic_status(source) == 0


def test_nextgen_semantic_pass_checks_exhaustive_terminal_ternary_match() -> None:
    source = (
        "fn choose(value: trit) -> i64:\n"
        "    match value:\n"
        "        -1:\n"
        "            return 10\n"
        "        0:\n"
        "            return 20\n"
        "        1:\n"
        "            return 30\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    assert compile_source(source).ir is not None
    assert _ng_semantic_status(source) == 0


def test_nextgen_semantic_accepts_maximum_contextual_tryte_literal() -> None:
    source = (
        "fn maximum() -> tryte:\n    return 364\n"
        "fn main() -> i64:\n    return 0\n"
    )
    assert compile_source(source).ir is not None
    assert _ng_semantic_status(source) == 0


@pytest.mark.parametrize(
    "source",
    [
        "fn minimum() -> trit:\n    return -1\nfn main() -> i64:\n    return 0\n",
        "fn minimum() -> tryte:\n    return -364\nfn main() -> i64:\n    return 0\n",
        "fn maximum() -> tryte:\n    return 364\nfn main() -> i64:\n    return 0\n",
    ],
)
def test_nextgen_semantics_accepts_signed_contextual_numeric_boundaries(source: str) -> None:
    assert compile_source(source).ir is not None
    assert _ng_semantic_status(source) == 0


@pytest.mark.parametrize(
    "source",
    [
        "fn out_of_range() -> trit:\n    return -2\nfn main() -> i64:\n    return 0\n",
        "fn out_of_range() -> trit:\n    return 2\nfn main() -> i64:\n    return 0\n",
        "fn out_of_range() -> tryte:\n    return -365\nfn main() -> i64:\n    return 0\n",
        "fn out_of_range() -> tryte:\n    return 365\nfn main() -> i64:\n    return 0\n",
    ],
)
def test_nextgen_semantics_rejects_signed_contextual_numeric_out_of_range(source: str) -> None:
    with pytest.raises(SemanticError):
        compile_source(source)


@pytest.mark.parametrize(
    "literal",
    ["9223372036854775808", "-9223372036854775808"],
)
def test_nextgen_semantics_rejects_i64_literal_outside_reference_range(literal: str) -> None:
    source = f"fn outside() -> i64:\n    return {literal}\nfn main() -> i64:\n    return 0\n"
    with pytest.raises(SemanticError):
        compile_source(source)
    assert _ng_semantic_status(source) == -14


@pytest.mark.parametrize(
    ("source", "expected_status"),
    [
        (
            "fn main() -> i64:\n    return missing\n",
            -12,
        ),
        (
            "fn wrong(value: i64) -> trit:\n    return value\n"
            "fn main() -> i64:\n    return 0\n",
            -15,
        ),
        (
            "fn main(value: i64, value: i64) -> i64:\n    return value\n",
            -11,
        ),
        (
            "fn calc(left: i64, right: trit) -> i64:\n    return left + right\n"
            "fn main() -> i64:\n    return 0\n",
            -14,
        ),
        (
            "fn main() -> i64:\n    return 1\nfn main() -> i64:\n    return 2\n",
            -10,
        ),
        (
            "fn main() -> i64:\n    return missing(1)\n",
            -13,
        ),
        (
            "fn take(value: i64) -> i64:\n    return value\n"
            "fn main() -> i64:\n    return take()\n",
            -14,
        ),
        (
            "fn take(value: i64) -> i64:\n    return value\n"
            "fn main(value: tryte) -> i64:\n    return take(value)\n",
            -14,
        ),
        (
            "fn take(value: tryte) -> i64:\n    return 1\n"
            "fn main() -> i64:\n    return take(365)\n",
            -14,
        ),
        (
            "fn main(condition: trit) -> i64:\n"
            "    mut value: i64 = 1\n"
            "    value = condition\n"
            "    return value\n",
            -14,
        ),
        (
            "fn main() -> i64:\n"
            "    value: i64 = 1\n"
            "    value = 2\n"
            "    return value\n",
            -16,
        ),
        (
            "fn main() -> i64:\n"
            "    value: i64 = 1\n"
            "    value: i64 = 2\n"
            "    return value\n",
            -11,
        ),
        (
            "fn main() -> i64:\n"
            "    return value\n"
            "    value: i64 = 1\n",
            -12,
        ),
        (
            "fn choose(value: i64) -> i64:\n"
            "    match value:\n"
            "        -1:\n"
            "            return 1\n"
            "        0:\n"
            "            return 2\n"
            "        1:\n"
            "            return 3\n"
            "fn main() -> i64:\n"
            "    return 0\n",
            -14,
        ),
        (
            "fn choose(value: trit) -> i64:\n"
            "    match value:\n"
            "        -1:\n"
            "            return 1\n"
            "        1:\n"
            "            return 3\n"
            "fn main() -> i64:\n"
            "    return 0\n",
            -18,
        ),
    ],
)
def test_nextgen_semantics_rejects_invalid_symbols_and_types_like_reference(
    source: str,
    expected_status: int,
) -> None:
    with pytest.raises(SemanticError):
        compile_source(source)
    assert _ng_semantic_status(source) == expected_status
