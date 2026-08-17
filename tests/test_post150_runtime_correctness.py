from __future__ import annotations

from bootstrap.s3 import run_source
from bootstrap.s3.backends.x86_64.runtime import render_runtime
from bootstrap.s3.dynamic import (
    DEFAULT_MAX_BUFFER_BYTES,
    DynamicBytes,
    DynamicText,
    DynamicVector,
)


def _between(text: str, start: str, end: str) -> str:
    return text[text.index(start) : text.index(end, text.index(start) + len(start))]


def test_text_find_reports_utf8_byte_offsets_in_hosted_runtime() -> None:
    value = DynamicText.from_static("éx")
    needle = DynamicText.from_static("x")
    assert value.find(needle) == 2

    source = """\
fn main() -> i64:
    value: text = text_from_static("éx")
    needle: text = text_from_static("x")
    return text_find(&value, &needle)
"""
    assert run_source(source) == 2


def test_native_utf8_validator_checks_special_leads_in_correct_width_branch() -> None:
    runtime = render_runtime()
    two = _between(runtime, ".L__s3_utf8_two:", ".L__s3_utf8_three:")
    three = _between(runtime, ".L__s3_utf8_three:", ".L__s3_utf8_four:")
    four = _between(runtime, ".L__s3_utf8_four:", ".L__s3_utf8_yes:")

    assert "cmp r9d,224" not in two
    assert "cmp r9d,237" not in two
    assert "cmp r9d,224" in three
    assert "cmp r8d,160" in three
    assert "cmp r9d,237" in three
    assert "cmp r8d,159" in three
    assert "cmp r9d,240" not in three
    assert "cmp r9d,244" not in three
    assert "cmp r9d,240" in four
    assert "cmp r8d,144" in four
    assert "cmp r9d,244" in four
    assert "cmp r8d,143" in four


def test_clone_capacity_contract_depends_on_owned_value_family() -> None:
    raw = DynamicBytes(8)
    raw.push(65)
    assert raw.clone().capacity == 1

    text = DynamicText.from_static("é")
    text.reserve(8)
    assert text.clone().capacity == len("é".encode("utf-8"))

    vector = DynamicVector("i64", 8)
    vector.push(7)
    assert vector.clone().capacity == 8


def test_native_clone_routes_preserve_kind_specific_capacity_contract() -> None:
    runtime = render_runtime()
    exact = _between(
        runtime,
        ".type __s3_dyn_clone_exact_length,@function",
        ".type __s3_dyn_clone_preserve_capacity,@function",
    )
    preserve = _between(
        runtime,
        ".type __s3_dyn_clone_preserve_capacity,@function",
        ".type __s3_builtin_bytes_clone,@function",
    )
    from_bytes = _between(
        runtime,
        ".type __s3_builtin_text_from_bytes,@function",
        ".type __s3_builtin_text_find,@function",
    )

    assert "mov rdi,[r12+8]" in exact
    assert "mov rdi,[r12+16]" in preserve
    assert "__s3_builtin_bytes_clone:\n    jmp __s3_dyn_clone_exact_length" in runtime
    assert "__s3_builtin_text_clone:\n    jmp __s3_dyn_clone_exact_length" in runtime
    assert "__s3_builtin_tryte_vector_clone:\n    jmp __s3_dyn_clone_preserve_capacity" in runtime
    assert "__s3_builtin_i64_vector_clone:\n    jmp __s3_dyn_clone_preserve_capacity" in runtime
    assert "__s3_builtin_f64_vector_clone:\n    jmp __s3_dyn_clone_preserve_capacity" in runtime
    assert "__s3_builtin_i64_map_clone:\n    jmp __s3_dyn_clone_preserve_capacity" in runtime
    assert "__s3_builtin_i64_set_clone:\n    jmp __s3_dyn_clone_preserve_capacity" in runtime
    assert "mov rdi,[r12+8]" in from_bytes


def test_native_dynamic_allocation_enforces_default_active_limit() -> None:
    runtime = render_runtime()
    dyn_new = _between(
        runtime,
        ".type __s3_dyn_new,@function",
        ".type __s3_builtin_bytes_new,@function",
    )
    assert f"cmp rdi,{DEFAULT_MAX_BUFFER_BYTES}" in dyn_new
    assert "ja __s3_fail_allocation" in dyn_new


def test_native_signed_result_rendering_remains_intact() -> None:
    runtime = render_runtime()
    assert (
        "test rax, rax\n"
        "    jns .L__s3_print_digits\n"
        "    mov r9d, 1\n"
        "    neg rax\n"
        ".L__s3_print_digits:"
    ) in runtime
