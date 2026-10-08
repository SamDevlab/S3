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


def test_nextgen_semantic_pass_supports_more_than_eight_function_locals() -> None:
    declarations = "".join(f"    value_{index}: i64 = {index}\n" for index in range(9))
    source = "fn main() -> i64:\n" + declarations + "    return value_0 + value_8\n"

    assert _ng_semantic_status(source) == 0


def test_record_field_resolution_accepts_equivalent_nominal_type_ids() -> None:
    source_text = "modelTokenfieldtoken"
    wrapper = f"""
fn main() -> vector<i64>:
    mut source_text: text = text_from_static({json.dumps(source_text)})
    mut source: bytes = bytes_from_text(&source_text)
    mut types: vector<NgTypeDescriptor> = vector_new<NgTypeDescriptor>(16)
    mut records: vector<NgRecord> = vector_new<NgRecord>(1)
    mut fields: vector<NgField> = vector_new<NgField>(1)
    mut functions: vector<NgFunction> = vector_new<NgFunction>(1)
    mut parameters: vector<NgParameter> = vector_new<NgParameter>(1)
    mut nodes: vector<NgAstNode> = vector_new<NgAstNode>(2)
    mut result: vector<i64> = vector_new<i64>(4)
    mut record_type_id: i64 = 0
    mut alias_type_id: i64 = 0
    mut status: i64 = ng_initialize_type_table(&mut types)
    record_type_id = vector_len<NgTypeDescriptor>(&types) + 1
    discard vector_push<NgTypeDescriptor>(&mut types, NgTypeDescriptor(kind=7, module_start=0, module_end=5, name_start=5, name_end=10, element_type=-1, target_type=-1, mutable=0, first_field=0, field_count=1))
    alias_type_id = vector_len<NgTypeDescriptor>(&types) + 1
    discard vector_push<NgTypeDescriptor>(&mut types, NgTypeDescriptor(kind=7, module_start=0, module_end=5, name_start=5, name_end=10, element_type=-1, target_type=-1, mutable=0, first_field=0, field_count=1))
    discard vector_push<NgRecord>(&mut records, NgRecord(module_index=0, name_start=5, name_end=10, type_id=record_type_id, first_field=0, field_count=1, exported=1))
    discard vector_push<NgField>(&mut fields, NgField(record_index=0, name_start=10, name_end=15, type_id=1, order=0))
    discard vector_push<NgParameter>(&mut parameters, NgParameter(name_start=15, name_end=20, type_kind=alias_type_id))
    discard vector_push<NgFunction>(&mut functions, NgFunction(start=0, end=20, name_start=0, name_end=0, local_name_start=0, local_name_end=0, first_parameter=0, parameter_count=1, return_type=1, first_node=0, body_node=1, module_index=0, exported=0, name_fingerprint=0, local_name_fingerprint=0))
    discard vector_push<NgAstNode>(&mut nodes, NgAstNode(kind=2, start=15, end=20, left=-1, right=0, operation=0))
    discard vector_push<NgAstNode>(&mut nodes, NgAstNode(kind=14, start=15, end=15, left=0, right=-1, operation=10))
    discard vector_push<i64>(&mut result, alias_type_id)
    status = ng_resolve_record_field_nodes(&source, &types, &records, &fields, &functions, &parameters, &mut nodes)
    discard vector_push<i64>(&mut result, status)
    discard vector_push<i64>(&mut result, vector_get<NgAstNode>(&nodes, 1).right)
    discard vector_push<i64>(&mut result, vector_get<NgAstNode>(&nodes, 1).operation)
    return result
"""
    compilation = compile_source(_NG_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    output = execute_ir(compilation.ir)
    assert hasattr(output, "element_type")
    values = [int(value) for value in output]
    assert values[1:] == [0, 1, values[0]], values


def test_local_declaration_index_preserves_order_and_reduces_lookup_work() -> None:
    declaration_count = 128
    lookup_count = 32
    names = [f"n{index:03d}" for index in range(declaration_count)]
    source_text = " ".join(names + ["n000"] + ["n001"] * lookup_count)
    shadow_start = declaration_count * 5
    lookup_start = shadow_start + 5
    wrapper = f"""
fn main() -> vector<i64>:
    mut source_text: text = text_from_static({json.dumps(source_text)})
    mut source: bytes = bytes_from_text(&source_text)
    mut nodes: vector<NgAstNode> = vector_new<NgAstNode>({declaration_count + 1})
    mut functions: vector<NgFunction> = vector_new<NgFunction>(1)
    mut declarations: vector<i64> = vector_new<i64>({declaration_count + 1})
    mut symbols: vector<NgLocalLookupSymbol> = vector_new<NgLocalLookupSymbol>({declaration_count + 1})
    mut buckets: vector<i64> = vector_new<i64>({(declaration_count + 1) * 2 + 1})
    mut offsets: vector<i64> = vector_new<i64>({declaration_count + 2})
    mut occurrences: vector<i64> = vector_new<i64>({declaration_count + 1})
    mut result: vector<i64> = vector_new<i64>(5)
    mut status: i64 = 0
    mut index: i64 = 0
    mut before: NgAstNode = NgAstNode(kind=14, start=0, end=0, left=-1, right=-1, operation=0)
    mut target: NgAstNode = NgAstNode(kind=2, start=5, end=9, left=-1, right=-1, operation=0)
    mut lookup: NgLocalLookupResult = NgLocalLookupResult(index=-1, probes=0)
    mut probes_total: i64 = 0
    discard vector_push<NgFunction>(&mut functions, NgFunction(start=0, end=bytes_len(&source), name_start=0, name_end=0, local_name_start=0, local_name_end=0, first_parameter=0, parameter_count=0, return_type=1, first_node=0, body_node={declaration_count + lookup_count + 1}, module_index=0, exported=0, name_fingerprint=0, local_name_fingerprint=0))
    while index < {declaration_count}:
        discard vector_push<NgAstNode>(&mut nodes, NgAstNode(kind=7, start=index * 5, end=index * 5 + 4, left=-1, right=-1, operation=1))
        index = index + 1
    discard vector_push<NgAstNode>(&mut nodes, NgAstNode(kind=7, start={shadow_start}, end={shadow_start + 4}, left=-1, right=-1, operation=2))
    discard ng_collect_local_declaration_indices(&nodes, &mut declarations)
    status = ng_build_local_declaration_lookup(&source, &functions, &nodes, &declarations, &mut symbols, &mut buckets, &mut offsets, &mut occurrences)
    discard vector_push<i64>(&mut result, status)
    index = 0
    while index < {lookup_count}:
        before.start = {lookup_start} + index * 5
        before.end = before.start + 4
        lookup = ng_prior_local_declaration(&source, &nodes, vector_get<NgFunction>(&functions, 0), before, {declaration_count + 1} + index, target, &mut symbols, &mut buckets, &mut offsets, &mut occurrences)
        probes_total = probes_total + lookup.probes
        match lookup.index <=> 1:
            0:
                lookup = lookup
            -1:
                return result
            1:
                return result
        index = index + 1
    discard vector_push<i64>(&mut result, probes_total)
    before.start = {lookup_start}
    before.end = {lookup_start + 4}
    lookup = ng_prior_local_declaration(&source, &nodes, vector_get<NgFunction>(&functions, 0), before, {declaration_count + 1}, NgAstNode(kind=2, start=0, end=4, left=-1, right=-1, operation=0), &mut symbols, &mut buckets, &mut offsets, &mut occurrences)
    discard vector_push<i64>(&mut result, lookup.index)
    before.start = {shadow_start}
    before.end = {shadow_start + 4}
    lookup = ng_prior_local_declaration(&source, &nodes, vector_get<NgFunction>(&functions, 0), before, {declaration_count}, NgAstNode(kind=2, start=0, end=4, left=-1, right=-1, operation=0), &mut symbols, &mut buckets, &mut offsets, &mut occurrences)
    discard vector_push<i64>(&mut result, lookup.index)
    lookup = ng_prior_local_declaration(&source, &nodes, vector_get<NgFunction>(&functions, 0), before, {declaration_count - 2}, NgAstNode(kind=2, start={127 * 5}, end={127 * 5 + 4}, left=-1, right=-1, operation=0), &mut symbols, &mut buckets, &mut offsets, &mut occurrences)
    discard vector_push<i64>(&mut result, lookup.index)
    return result
"""
    compilation = compile_source(_NG_SOURCE + "\n" + wrapper)
    assert compilation.ir is not None
    output = execute_ir(compilation.ir)
    assert hasattr(output, "element_type")
    status, indexed_probes, shadowed, before_shadow, use_before_declaration = [int(value) for value in output]
    assert status == 0
    assert indexed_probes < lookup_count * declaration_count // 8
    assert shadowed == declaration_count
    assert before_shadow == 0
    assert use_before_declaration == -1


def test_nextgen_semantic_pass_resolves_forward_calls_and_argument_types() -> None:
    source = (
        "fn main() -> i64:\n    return add(20, 22)\n"
        "fn add(left: i64, right: i64) -> i64:\n    return left + right\n"
    )
    assert compile_source(source).ir is not None
    assert _ng_semantic_status(source) == 0


def test_nextgen_semantic_scopes_break_to_the_enclosing_loop() -> None:
    valid_source = (
        "fn loop(value: trit) -> i64:\n"
        "    while value:\n"
        "        break\n"
        "    return 0\n"
        "fn main() -> i64:\n"
        "    return loop(0)\n"
    )
    invalid_source = "fn main() -> i64:\n    break\n    return 0\n"

    assert compile_source(valid_source).ir is not None
    assert _ng_semantic_status(valid_source) == 0
    with pytest.raises(SemanticError, match="break outside loop"):
        compile_source(invalid_source)
    assert _ng_semantic_status(invalid_source) == -16


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


def test_nextgen_semantics_supports_three_way_comparison_of_trit_results() -> None:
    source = (
        "fn current_state() -> trit:\n"
        "    return -1\n"
        "fn classify() -> i64:\n"
        "    match current_state() <=> 0:\n"
        "        -1:\n"
        "            return -1\n"
        "        0:\n"
        "            return 0\n"
        "        1:\n"
        "            return 1\n"
        "fn main() -> i64:\n"
        "    return classify()\n"
    )
    assert compile_source(source).ir is not None
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


def test_nextgen_semantic_checks_generic_vector_get_and_set_descriptors() -> None:
    valid = (
        "module app\n"
        "record Token:\n    value: i64\n"
        "fn read(items: &vector<Token>, index: i64) -> Token:\n"
        "    return vector_get<Token>(items, index)\n"
        "fn read_mut(items: &mut vector<Token>, index: i64) -> Token:\n"
        "    return vector_get<Token>(items, index)\n"
        "fn write(items: &mut vector<Token>, index: i64, item: Token) -> tryte:\n"
        "    return vector_set<Token>(items, index, item)\n"
    )
    wrong_get_element = (
        "module app\n"
        "record Token:\n    value: i64\n"
        "record Other:\n    value: i64\n"
        "fn read(items: &vector<Token>, index: i64) -> Other:\n"
        "    return vector_get<Other>(items, index)\n"
    )
    wrong_get_index = (
        "module app\n"
        "fn read(items: &vector<i64>, index: trit) -> i64:\n"
        "    return vector_get<i64>(items, index)\n"
    )
    wrong_get_arity = (
        "module app\n"
        "fn read(items: &vector<i64>) -> i64:\n"
        "    return vector_get<i64>(items)\n"
    )
    wrong_get_result = (
        "module app\n"
        "record Token:\n    value: i64\n"
        "fn read(items: &vector<Token>, index: i64) -> tryte:\n"
        "    return vector_get<Token>(items, index)\n"
    )
    immutable_set = (
        "module app\n"
        "fn write(items: &vector<i64>, index: i64, item: i64) -> tryte:\n"
        "    return vector_set<i64>(items, index, item)\n"
    )
    wrong_set_value = (
        "module app\n"
        "record Token:\n    value: i64\n"
        "record Other:\n    value: i64\n"
        "fn write(items: &mut vector<Token>, index: i64, item: Other) -> tryte:\n"
        "    return vector_set<Token>(items, index, item)\n"
    )
    wrong_set_result = (
        "module app\n"
        "fn write(items: &mut vector<i64>, index: i64, item: i64) -> i64:\n"
        "    return vector_set<i64>(items, index, item)\n"
    )

    assert _ng_module_semantic_statuses(
        [valid, wrong_get_element, wrong_get_index, wrong_get_arity, wrong_get_result,
         immutable_set, wrong_set_value, wrong_set_result]
    ) == [0, -14, -14, -14, -14, -14, -14, -14]


def test_nextgen_semantic_types_bytes_from_text_shared_reference() -> None:
    valid = (
        "module app\n"
        "fn materialize(value: &text) -> bytes:\n"
        "    return bytes_from_text(value)\n"
        "fn main() -> i64:\n"
        "    return 0\n"
    )
    wrong_target = (
        "module app\n"
        "fn materialize(value: &bytes) -> bytes:\n"
        "    return bytes_from_text(value)\n"
    )
    missing_reference = (
        "module app\n"
        "fn materialize(value: text) -> bytes:\n"
        "    return bytes_from_text(value)\n"
    )
    wrong_arity = (
        "module app\n"
        "fn materialize() -> bytes:\n"
        "    return bytes_from_text()\n"
    )

    assert compile_source(valid).ir is not None
    assert _ng_module_semantic_statuses([valid, wrong_target, missing_reference, wrong_arity]) == [
        0,
        -14,
        -14,
        -14,
    ]


def test_nextgen_semantic_types_bytes_concat_shared_references() -> None:
    valid = (
        "module app\n"
        "fn join(left: &bytes, right: &bytes) -> bytes:\n"
        "    return bytes_concat(left, right)\n"
        "fn capacity(value: &bytes) -> i64:\n"
        "    return bytes_capacity(value)\n"
        "fn reserve(value: &mut bytes, amount: i64) -> tryte:\n"
        "    return bytes_reserve(value, amount)\n"
        "fn append_capacity(target: &mut bytes, source: &bytes) -> i64:\n"
        "    mut capacity_before: i64 = bytes_capacity(target)\n"
        "    mut required: i64 = bytes_len(target) + bytes_len(source)\n"
        "    discard bytes_reserve(target, required)\n"
        "    return capacity_before\n"
    )
    mutable_inputs = (
        "module app\n"
        "fn join(left: &mut bytes, right: &bytes) -> bytes:\n"
        "    return bytes_concat(left, right)\n"
    )
    wrong_target = (
        "module app\n"
        "fn join(left: &bytes, right: &text) -> bytes:\n"
        "    return bytes_concat(left, right)\n"
    )
    missing_reference = (
        "module app\n"
        "fn join(left: bytes, right: &bytes) -> bytes:\n"
        "    return bytes_concat(left, right)\n"
    )
    wrong_arity = (
        "module app\n"
        "fn join(left: &bytes) -> bytes:\n"
        "    return bytes_concat(left)\n"
    )
    immutable_reserve = (
        "module app\n"
        "fn reserve(value: &bytes, amount: i64) -> tryte:\n"
        "    return bytes_reserve(value, amount)\n"
    )
    wrong_capacity_target = (
        "module app\n"
        "fn capacity(value: &text) -> i64:\n"
        "    return bytes_capacity(value)\n"
    )

    assert _ng_module_semantic_statuses(
        [
            valid,
            mutable_inputs,
            wrong_target,
            missing_reference,
            wrong_arity,
            immutable_reserve,
            wrong_capacity_target,
        ]
    ) == [0, 0, -14, -14, -14, -14, -14]


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


@pytest.mark.parametrize(
    ("initializer", "expected_status"),
    [
        ("Pair(left=1, right=-1).left", 0),
        ("Pair(left=1).left", -14),
        ("Pair(left=1, left=2, right=-1).left", -14),
        ("Pair(missing=1, right=-1).left", -14),
        ("Pair(left=1, right=2).left", -14),
    ],
)
def test_nextgen_record_constructor_checks_named_fields_and_types(
    initializer: str,
    expected_status: int,
) -> None:
    source = (
        "module app\n"
        "record Pair:\n"
        "    left: i64\n"
        "    right: trit\n"
        "fn main() -> i64:\n"
        f"    return {initializer}\n"
    )
    assert _ng_module_semantic_statuses([source]) == [expected_status]


def test_nextgen_field_resolution_does_not_confuse_generic_argument_with_constructor() -> None:
    source = (
        "module app\n"
        "record Token:\n"
        "    kind: i64\n"
        "fn main() -> i64:\n"
        "    return vector_new<Token>(1).kind\n"
    )
    assert _ng_module_semantic_statuses([source]) == [-14]


@pytest.mark.parametrize(
    ("declaration", "assignment", "expected_status"),
    [
        ("mut pair", "pair.left = 23", 0),
        ("mut pair", "pair.left = pair.right", -14),
        ("pair", "pair.left = 23", -16),
    ],
)
def test_nextgen_semantics_checks_record_field_assignment(
    declaration: str,
    assignment: str,
    expected_status: int,
) -> None:
    source = (
        "module app\n"
        "record Pair:\n"
        "    left: i64\n"
        "    right: trit\n"
        "fn main() -> i64:\n"
        f"    {declaration}: Pair = Pair(left=19, right=1)\n"
        f"    {assignment}\n"
        "    return pair.left\n"
    )
    assert _ng_module_semantic_statuses([source]) == [expected_status]


def test_nextgen_field_resolution_does_not_bind_a_later_local_declaration() -> None:
    source = (
        "module app\n"
        "record Pair:\n"
        "    value: i64\n"
        "fn main() -> i64:\n"
        "    let observed: i64 = pair.value\n"
        "    let pair: Pair = Pair(value=1)\n"
        "    return observed\n"
    )

    assert _ng_module_semantic_statuses([source])[0] < 0
