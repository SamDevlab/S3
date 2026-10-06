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
        _module_body("selfhost/compiler_ng/types.s3"),
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


def _ng_module_semantic_statuses(sources: list[str]) -> list[int]:
    wrapper = """
fn ng_module_semantic_status(input_source: text) -> i64:
    mut source_bytes: bytes = bytes_from_text(&input_source)
    mut source_length: i64 = bytes_len(&source_bytes)
    mut tokens: vector<NgToken> = vector_new<NgToken>(source_length + 1)
    mut imports: vector<NgImport> = vector_new<NgImport>(source_length + 1)
    mut modules: vector<NgModule> = vector_new<NgModule>(2)
    mut records: vector<NgRecord> = vector_new<NgRecord>(source_length + 1)
    mut fields: vector<NgField> = vector_new<NgField>(source_length + 1)
    mut functions: vector<NgFunction> = vector_new<NgFunction>(source_length + 1)
    mut parameters: vector<NgParameter> = vector_new<NgParameter>(source_length + 1)
    mut nodes: vector<NgAstNode> = vector_new<NgAstNode>(source_length + 1)
    mut types: vector<NgTypeDescriptor> = vector_new<NgTypeDescriptor>(source_length + 8)
    mut module_item: NgModule = NgModule(source_index=0, source_start=0, source_end=0, path_start=0, path_end=0, name_start=0, name_end=0, body_token_index=0, first_function=0, function_count=0, first_import=0, import_count=0)
    mut status: i64 = ng_lex(&source_bytes, &mut tokens)
    match status <=> 0:
        -1:
            return -100
        0:
            status = ng_initialize_type_table(&mut types)
        1:
            return -100
    match status <=> 0:
        -1:
            return -100
        0:
            module_item = ng_parse_module_header(&mut source_bytes, &tokens, 0, 0, source_length, 0, 0, &mut imports)
            status = ng_parse_module_functions(&source_bytes, &tokens, module_item, &mut types, &mut records, &mut fields, &mut parameters, &mut nodes, &mut functions)
        1:
            return -100
    match status <=> 0:
        -1:
            return status
        0:
            discard vector_push<NgModule>(&mut modules, module_item)
            status = ng_validate_nominal_types(&source_bytes, &types, &modules, &records)
        1:
            return status
    match status <=> 0:
        -1:
            return status
        0:
            return ng_check_program_typed(&source_bytes, &types, &records, &fields, &functions, &parameters, &mut nodes)
        1:
            return status

fn main() -> vector<i64>:
    mut result: vector<i64> = vector_new<i64>(16)
"""
    for source in sources:
        wrapper += f'    discard vector_push<i64>(&mut result, ng_module_semantic_status(text_from_static({json.dumps(source)})))\n'
    wrapper += "    return result\n"
    compilation = compile_source(_NG_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    output = execute_ir(compilation.ir)
    assert hasattr(output, "element_type")
    return [int(value) for value in output]


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


def test_nextgen_semantic_pass_checks_discarded_call_expression() -> None:
    source = (
        "fn effect(value: i64) -> i64:\n"
        "    return value\n"
        "fn run(value: i64) -> i64:\n"
        "    discard effect(value)\n"
        "    return value\n"
    )
    assert _ng_semantic_status(source) == 0


def test_nextgen_semantics_types_relational_operators_as_trit() -> None:
    source = (
        "fn comparisons(left: i64, right: i64) -> i64:\n"
        "    equal: trit = left == right\n"
        "    not_equal: trit = left != right\n"
        "    less: trit = left < right\n"
        "    less_equal: trit = left <= right\n"
        "    greater: trit = left > right\n"
        "    greater_equal: trit = left >= right\n"
        "    return 0\n"
    )
    assert _ng_semantic_status(source) == 0


def test_nextgen_semantics_checks_while_with_nested_match_and_keeps_loop_fallthrough() -> None:
    source = (
        "fn main() -> i64:\n"
        "    mut index: i64 = 0\n"
        "    while index < 3:\n"
        "        match index <=> 1:\n"
        "            -1:\n"
        "                index = index + 1\n"
        "            0:\n"
        "                index = index + 1\n"
        "            1:\n"
        "                index = index + 1\n"
        "    return index\n"
    )
    assert _ng_semantic_status(source) == 0


def test_nextgen_semantics_does_not_propagate_loop_body_return_to_function() -> None:
    source = (
        "fn main() -> i64:\n"
        "    while 1 < 0:\n"
        "        return 5\n"
        "    return 0\n"
    )
    assert _ng_semantic_status(source) == 0


def test_nextgen_semantic_checks_generic_vector_new_against_contextual_type() -> None:
    valid = (
        "module app\n"
        "fn build(capacity: i64) -> vector<i64>:\n"
        "    return vector_new<i64>(capacity)\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    valid_record = (
        "module app\n"
        "record Token:\n"
        "    kind: i64\n"
        "    start: i64\n"
        "    end: i64\n"
        "fn build(capacity: i64) -> vector<Token>:\n"
        "    return vector_new<Token>(capacity)\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    wrong_result_type = (
        "module app\n"
        "fn build() -> vector<tryte>:\n"
        "    return vector_new<i64>(1)\n"
    )
    wrong_capacity_type = (
        "module app\n"
        "fn build(capacity: trit) -> vector<i64>:\n"
        "    return vector_new<i64>(capacity)\n"
    )
    dynamic_element = (
        "module app\n"
        "fn build() -> vector<bytes>:\n"
        "    return vector_new<bytes>(1)\n"
    )
    assert compile_source(valid).ir is not None
    assert compile_source(valid_record).ir is not None
    assert _ng_module_semantic_statuses([valid, valid_record, wrong_result_type, wrong_capacity_type, dynamic_element]) == [0, 0, -14, -14, -14]


def test_nextgen_semantic_checks_generic_vector_push_element_and_mutability() -> None:
    immutable_container = (
        "module app\n"
        "fn append(values: &vector<i64>) -> tryte:\n"
        "    return vector_push<i64>(values, 7)\n"
    )
    mismatched_element = (
        "module app\n"
        "fn append(values: &mut vector<i64>) -> tryte:\n"
        "    return vector_push<tryte>(values, 7)\n"
    )
    assert _ng_module_semantic_statuses([immutable_container, mismatched_element]) == [-14, -14]


def test_nextgen_semantics_compare_complete_nominal_vector_and_reference_descriptors() -> None:
    valid = (
        "module app\n"
        "record Token:\n    value: i64\n"
        "fn consume(item: &mut vector<Token>) -> i64:\n    return 1\n"
        "fn relay(item: &mut vector<Token>) -> i64:\n    return consume(item)\n"
        "fn pass_items(items: vector<Token>) -> vector<Token>:\n    return items\n"
        "fn relay_items(items: vector<Token>) -> vector<Token>:\n    return pass_items(items)\n"
        "fn pass_data(data: &bytes) -> &bytes:\n    return data\n"
        "fn relay_data(data: &bytes) -> &bytes:\n    return pass_data(data)\n"
    )
    wrong_nominal = (
        "module app\n"
        "record Token:\n    value: i64\n"
        "record Other:\n    value: i64\n"
        "fn consume(item: Token) -> i64:\n    return 1\n"
        "fn relay(item: Other) -> i64:\n    return consume(item)\n"
    )
    wrong_mutability = (
        "module app\n"
        "record Token:\n    value: i64\n"
        "fn consume(item: &mut vector<Token>) -> i64:\n    return 1\n"
        "fn relay(item: &vector<Token>) -> i64:\n    return consume(item)\n"
    )
    assert _ng_module_semantic_statuses([valid, wrong_nominal, wrong_mutability]) == [0, -14, -14]


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
