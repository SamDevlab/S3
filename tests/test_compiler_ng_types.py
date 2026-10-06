from __future__ import annotations

from pathlib import Path

from bootstrap.s3.dynamic import DynamicVector
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.pipeline import compile_source


_ROOT = Path(__file__).parents[1]


def _module_body(relative_path: str) -> str:
    return "\n".join(
        line
        for line in (_ROOT / relative_path).read_text(encoding="utf-8").splitlines()
        if not line.startswith("module ") and not line.startswith("from ")
    )


def _type_probe() -> list[int]:
    source = "module_a.Token module_b.Token"
    wrapper = f'''\
fn main() -> vector<i64>:
    mut source_text: text = text_from_static("{source}")
    mut source: bytes = bytes_from_text(&source_text)
    mut types: vector<NgTypeDescriptor> = vector_new<NgTypeDescriptor>(32)
    mut result: vector<i64> = vector_new<i64>(64)
    mut status: i64 = ng_initialize_type_table(&mut types)
    mut module_a: i64 = ng_intern_nominal_type(&source, &mut types, 0, 8, 9, 14)
    mut module_b: i64 = ng_intern_nominal_type(&source, &mut types, 15, 23, 24, 29)
    mut module_a_again: i64 = ng_intern_nominal_type(&source, &mut types, 0, 8, 9, 14)
    mut vector_i64: i64 = ng_intern_vector_type(&mut types, 1)
    mut vector_trit: i64 = ng_intern_vector_type(&mut types, 2)
    mut vector_i64_again: i64 = ng_intern_vector_type(&mut types, 1)
    mut immutable_vector_ref: i64 = ng_intern_reference_type(&mut types, vector_i64, 0)
    mut mutable_vector_ref: i64 = ng_intern_reference_type(&mut types, vector_i64, 1)
    mut immutable_vector_ref_again: i64 = ng_intern_reference_type(&mut types, vector_i64, 0)
    mut bytes_type: i64 = ng_builtin_type_id(&types, 5)
    mut bytes_ref: i64 = ng_intern_reference_type(&mut types, bytes_type, 0)
    mut mutable_bytes_ref: i64 = ng_intern_reference_type(&mut types, bytes_type, 1)
    mut bytes_ref_again: i64 = ng_intern_reference_type(&mut types, bytes_type, 0)
    mut invalid_nominal: i64 = ng_intern_nominal_type(&source, &mut types, -1, 8, 9, 14)
    mut invalid_vector: i64 = ng_intern_vector_type(&mut types, 99)
    mut invalid_reference_target: i64 = ng_intern_reference_type(&mut types, 99, 0)
    mut invalid_reference_mutability: i64 = ng_intern_reference_type(&mut types, vector_i64, 2)
    mut type_count: i64 = vector_len<NgTypeDescriptor>(&types)
    mut repeated_init: i64 = ng_initialize_type_table(&mut types)
    mut partial_types: vector<NgTypeDescriptor> = vector_new<NgTypeDescriptor>(4)
    mut partial_init: i64 = 0
    mut partial_count: i64 = 0
    discard vector_push<NgTypeDescriptor>(&mut partial_types, NgTypeDescriptor(kind=1, module_start=-1, module_end=-1, name_start=-1, name_end=-1, element_type=-1, target_type=-1, mutable=0, first_field=0, field_count=0))
    partial_init = ng_initialize_type_table(&mut partial_types)
    partial_count = vector_len<NgTypeDescriptor>(&partial_types)
    discard vector_push<i64>(&mut result, status)
    discard vector_push<i64>(&mut result, module_a)
    discard vector_push<i64>(&mut result, module_b)
    discard vector_push<i64>(&mut result, module_a_again)
    discard vector_push<i64>(&mut result, vector_i64)
    discard vector_push<i64>(&mut result, vector_trit)
    discard vector_push<i64>(&mut result, vector_i64_again)
    discard vector_push<i64>(&mut result, immutable_vector_ref)
    discard vector_push<i64>(&mut result, mutable_vector_ref)
    discard vector_push<i64>(&mut result, immutable_vector_ref_again)
    discard vector_push<i64>(&mut result, to_i64(ng_type_equal(&source, &types, module_a, module_b)))
    discard vector_push<i64>(&mut result, to_i64(ng_type_equal(&source, &types, module_a, module_a_again)))
    discard vector_push<i64>(&mut result, to_i64(ng_type_equal(&source, &types, vector_i64, vector_trit)))
    discard vector_push<i64>(&mut result, to_i64(ng_type_equal(&source, &types, vector_i64, vector_i64_again)))
    discard vector_push<i64>(&mut result, to_i64(ng_type_equal(&source, &types, immutable_vector_ref, mutable_vector_ref)))
    discard vector_push<i64>(&mut result, to_i64(ng_type_equal(&source, &types, immutable_vector_ref, immutable_vector_ref_again)))
    discard vector_push<i64>(&mut result, ng_builtin_type_id(&types, 1))
    discard vector_push<i64>(&mut result, bytes_type)
    discard vector_push<i64>(&mut result, ng_builtin_type_id(&types, 6))
    discard vector_push<i64>(&mut result, ng_builtin_type_id(&types, 9))
    discard vector_push<i64>(&mut result, ng_primitive_type_id(&types, 1))
    discard vector_push<i64>(&mut result, ng_primitive_type_id(&types, 5))
    discard vector_push<i64>(&mut result, bytes_ref)
    discard vector_push<i64>(&mut result, mutable_bytes_ref)
    discard vector_push<i64>(&mut result, bytes_ref_again)
    discard vector_push<i64>(&mut result, to_i64(ng_type_equal(&source, &types, bytes_ref, mutable_bytes_ref)))
    discard vector_push<i64>(&mut result, to_i64(ng_type_equal(&source, &types, bytes_ref, bytes_ref_again)))
    discard vector_push<i64>(&mut result, ng_primitive_type_id(&types, 9))
    discard vector_push<i64>(&mut result, invalid_nominal)
    discard vector_push<i64>(&mut result, invalid_vector)
    discard vector_push<i64>(&mut result, invalid_reference_target)
    discard vector_push<i64>(&mut result, invalid_reference_mutability)
    discard vector_push<i64>(&mut result, to_i64(ng_type_equal(&source, &types, 0, 0)))
    discard vector_push<i64>(&mut result, type_count)
    discard vector_push<i64>(&mut result, vector_len<NgTypeDescriptor>(&types))
    discard vector_push<i64>(&mut result, partial_init)
    discard vector_push<i64>(&mut result, partial_count)
    discard vector_push<i64>(&mut result, repeated_init)
    discard vector_push<i64>(&mut result, vector_len<NgTypeDescriptor>(&types))
    return result
'''
    compiler_source = _module_body("selfhost/compiler_ng/types.s3")
    compilation = compile_source(compiler_source + "\n" + wrapper)
    assert compilation.ir is not None
    output = execute_ir(compilation.ir)
    assert isinstance(output, DynamicVector)
    assert output.element_type == "i64"
    return [int(value) for value in output]


def test_ng_type_table_interns_composite_and_nominal_types_deterministically() -> None:
    first = _type_probe()
    second = _type_probe()

    assert first == second
    assert first == [
        0, 7, 8, 7, 9, 10, 9, 11, 12, 11, 0, -1, 0, -1, 0, -1,
        1, 5, 6, -1, 1, -1, 13, 14, 13, 0, -1,
        -1, -1, -1, -1, -1, 0, 14, 14, -1, 1, 0, 14,
    ]
