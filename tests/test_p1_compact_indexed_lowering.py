from __future__ import annotations

from bootstrap.s3.backends.x86_64 import generate_native_assembly
from bootstrap.s3.parser import SyntaxMode
from bootstrap.s3.pipeline import compile_source


def _native(source: str) -> str:
    return generate_native_assembly(
        compile_source(source, mode=SyntaxMode.V0_6).assembly
    )


def test_slice_index_uses_one_unsigned_upper_bound_branch() -> None:
    native = _native(
        """
fn read(xs: &[i64], index: i64) -> i64:
    return xs[index]
fn main() -> i64:
    values: i64[2] = [1, 2]
    return read(&values, 1)
"""
    )

    assert "cmp rax, r11" in native
    assert "cmp rax, 0" not in native
    assert "jl .L__s3_failure_site" not in native


def test_static_array_index_uses_direct_constant_upper_bound_branch() -> None:
    native = _native(
        """
fn main() -> i64:
    values: i64[2] = [1, 2]
    return values[1]
"""
    )

    assert "cmp rax, 2" in native
    assert "cmp rax, 0" not in native
    assert "jge .L__s3_failure_site" not in native


def test_mutable_slice_store_shares_the_compact_bounds_shape() -> None:
    native = _native(
        """
fn write(xs: &mut [i64], index: i64) -> trit:
    xs[index] = 7
    return -1
fn main() -> trit:
    values: i64[2] = [1, 2]
    return write(&mut values, 1)
"""
    )

    assert "cmp rax, r11" in native
    assert "cmp rax, 0" not in native
    assert "jl .L__s3_failure_site" not in native
