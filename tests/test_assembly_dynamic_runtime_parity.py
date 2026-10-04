from __future__ import annotations

import pytest

from bootstrap.s3.assembly_verifier import _dynamic_builtin_signature
from bootstrap.s3.backends.x86_64.runtime import _dynamic_runtime
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.ir import DYNAMIC_BUILTIN_SIGNATURES
from bootstrap.s3.ir_emulator import _execute_dynamic_builtin, execute_ir
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.semantic import _DYNAMIC_BUILTINS


_FAMILY_PROGRAMS = (
    (
        "i64-vector",
        """\
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(2)
    discard i64_vector_push(&mut values, 41)
    discard i64_vector_set(&mut values, 0, 7)
    return i64_vector_get(&values, 0) + i64_vector_len(&values)
""",
        8,
    ),
    (
        "tryte-vector",
        """\
fn main() -> i64:
    mut values: tryte_vector = tryte_vector_new(2)
    discard tryte_vector_push(&mut values, -3)
    discard tryte_vector_set(&mut values, 0, 9)
    return to_i64(tryte_vector_get(&values, 0))
""",
        9,
    ),
    (
        "f64-vector",
        """\
fn main() -> i64:
    mut values: f64_vector = f64_vector_new(2)
    discard f64_vector_push(&mut values, 1.5)
    discard f64_vector_set(&mut values, 0, 2.5)
    mut matches: trit = f64_vector_get(&values, 0) == 2.5
    return to_i64(matches)
""",
        -1,
    ),
    (
        "bytes",
        """\
fn main() -> i64:
    mut data: bytes = bytes_new(2)
    discard bytes_push(&mut data, 65)
    discard bytes_set(&mut data, 0, 66)
    return to_i64(bytes_get(&data, 0)) + bytes_len(&data)
""",
        67,
    ),
    (
        "text",
        """\
fn main() -> i64:
    mut value: text = text_from_static("Aé")
    needle: text = text_from_static("!")
    discard text_reserve(&mut value, 4)
    discard text_append_static(&mut value, "!")
    return text_len(&value) + text_find(&value, &needle)
""",
        7,
    ),
    (
        "i64-map-and-set",
        """\
fn main() -> i64:
    mut mapping: i64_map = i64_map_new(2)
    discard i64_map_put(&mut mapping, 7, 70)
    mut values: i64_set = i64_set_new(2)
    discard i64_set_add(&mut values, 7)
    return i64_map_get(&mapping, 7) + i64_set_len(&values)
""",
        71,
    ),
    (
        "text-map",
        """\
fn main() -> i64:
    mut mapping: map<text, i64> = map_new<text, i64>(2)
    key: text = text_from_static("alpha")
    discard map_put<text, i64>(&mut mapping, &key, 73)
    return map_get<text, i64>(&mapping, &key)
""",
        73,
    ),
    (
        "composite-vector",
        """\
record Pair:
    left: i64
    right: i64
fn main() -> i64:
    mut values: vector<Pair> = vector_new<Pair>(1)
    discard vector_push<Pair>(&mut values, Pair(left=8, right=9))
    return vector_get<Pair>(&values, 0).left
""",
        8,
    ),
)


def test_dynamic_builtin_inventory_is_closed_across_existing_layers() -> None:
    builtin_names = set(DYNAMIC_BUILTIN_SIGNATURES)
    native_runtime = "\n".join(_dynamic_runtime())

    assert len(builtin_names) == 91
    assert builtin_names == set(_DYNAMIC_BUILTINS)
    assert all(_dynamic_builtin_signature(name) for name in builtin_names)
    assert all(f"__s3_builtin_{name}" in native_runtime for name in builtin_names)
    assert callable(_execute_dynamic_builtin)


@pytest.mark.parametrize(("family", "source", "expected"), _FAMILY_PROGRAMS)
def test_dynamic_builtin_families_match_ir_and_assembly(
    family: str, source: str, expected: int
) -> None:
    compilation = compile_source(source)
    ir_result = execute_ir(compilation.ir)
    assembly_result = execute_assembly(compilation.assembly)

    assert ir_result == expected, family
    assert assembly_result == ir_result, family


@pytest.mark.parametrize(
    "source",
    [
        """\
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(-1)
    return i64_vector_len(&values)
""",
        """\
fn main() -> i64:
    mut values: i64_vector = i64_vector_new(0)
    return i64_vector_get(&values, 0)
""",
        """\
fn main() -> i64:
    mut raw: bytes = bytes_new(1)
    discard bytes_push(&mut raw, 255)
    mut value: text = text_from_bytes(&raw)
    return text_len(&value)
""",
    ],
    ids=["negative-capacity", "out-of-bounds", "invalid-utf8"],
)
def test_dynamic_runtime_errors_match_ir_and_assembly(source: str) -> None:
    compilation = compile_source(source)

    with pytest.raises(Exception) as ir_error:
        execute_ir(compilation.ir)
    with pytest.raises(type(ir_error.value)) as assembly_error:
        execute_assembly(compilation.assembly)

    assert str(assembly_error.value) == str(ir_error.value)
