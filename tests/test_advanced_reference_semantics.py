from __future__ import annotations

import pytest

from bootstrap.s3.ir_emulator import IRExecutionError, execute_ir
from bootstrap.s3.memory_effects import MemoryEffect, MemoryRegion, may_alias
from bootstrap.s3.pipeline import compile_source


pytestmark = pytest.mark.s3_fast


def _execute(source: str, optimization: str = "O1") -> int:
    return execute_ir(compile_source(source, optimization).ir)


def test_mutable_array_element_reference_captures_index_once() -> None:
    source = """fn main() -> tryte:
    mut data: tryte[2] = [10, 20]
    mut i: tryte = 0
    p: &mut tryte = &mut data[i]
    i = 1
    *p = 42
    return data[0] + data[1]
"""
    assert _execute(source) == 62


def test_array_element_bounds_fail_at_address_creation() -> None:
    source = """fn main() -> tryte:
    mut data: tryte[2] = [10, 20]
    mut i: tryte = 2
    p: &mut tryte = &mut data[i]
    return 0
"""
    with pytest.raises(IRExecutionError, match="out of bounds"):
        _execute(source)


def test_shared_and_mutable_reborrow_preserve_identity() -> None:
    source = """fn main() -> tryte:
    mut value: tryte = 1
    r: &mut tryte = &mut value
    s: &tryte = &*r
    t: &mut tryte = &mut *r
    *t = 7
    return *s
"""
    assert _execute(source) == 7


def test_shared_record_field_reference_uses_field_storage() -> None:
    source = """record Pair:
    left: tryte
    right: tryte
fn main() -> tryte:
    pair: Pair = Pair(left=4, right=6)
    p: &tryte = &pair.left
    return *p
"""
    assert _execute(source) == 4


def test_mutable_reborrow_from_shared_reference_is_rejected() -> None:
    source = """fn main() -> tryte:
    mut value: tryte = 1
    r: &tryte = &value
    s: &mut tryte = &mut *r
    return *s
"""
    with pytest.raises(Exception, match="mutable reborrow"):
        compile_source(source, "O0")


def test_memory_effect_and_alias_queries_are_explicit_and_conservative() -> None:
    assert MemoryEffect.READ.value == "read"
    assert MemoryEffect.READ_WRITE.value == "read_write"
    root = MemoryRegion("data")
    first = MemoryRegion("data", ("element", 0))
    dynamic = MemoryRegion("data", ("element", None))
    other = MemoryRegion("other", ("element", 0))
    assert may_alias(first, first)
    assert may_alias(first, dynamic)
    assert not may_alias(first, other)
