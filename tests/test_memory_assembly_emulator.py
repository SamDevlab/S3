from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.assembly import (
    AssemblyOpcode,
    AssemblyParseError,
    parse_assembly,
)
from bootstrap.s3.emulator import (
    DEFAULT_MAX_MEMORY_TRITS,
    EmulatorError,
    execute_assembly,
)
from bootstrap.s3.pipeline import compile_source, run_source


ROOT = Path(__file__).parents[1]


def test_generated_memory_assembly_round_trips() -> None:
    source = (ROOT / "examples" / "static_array.s3").read_text(encoding="utf-8")
    assembly = compile_source(source).assembly
    text = assembly.render()
    assert ".memory m0, tryte, 4, mutable" in text
    assert "TSTORE" in text
    assert "TLOAD" in text
    assert "TSUB" not in text
    assert parse_assembly(text) == assembly
    assert execute_assembly(text) == 13


def test_scalar_store_and_load_execute() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 1, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 10
    TSTORE m0, r0, r1
    TLOAD r2, m0, r0
    TRET r2
.end
"""
    program = parse_assembly(source)
    opcodes = {instruction.opcode for instruction in program.functions[0].instructions}
    assert {AssemblyOpcode.TLOAD, AssemblyOpcode.TSTORE} <= opcodes
    assert execute_assembly(program) == 10


@pytest.mark.parametrize(
    ("index", "expected"),
    ((0, 4), (2, 6)),
)
def test_zero_and_last_array_indices(index: int, expected: int) -> None:
    source = f"""\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 3, mutable
.label entry
    TCONST r0, {index}
    TCONST r1, {expected}
    TSTORE m0, r0, r1
    TLOAD r2, m0, r0
    TRET r2
.end
"""
    assert execute_assembly(source) == expected


@pytest.mark.parametrize("index", (-1, 2))
def test_out_of_bounds_memory_index_is_rejected(index: int) -> None:
    source = f"""\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .memory m0, tryte, 2, mutable
.label entry
    TCONST r0, {index}
    TLOAD r1, m0, r0 ; source=9:4:20
    TRET r1
.end
"""
    with pytest.raises(
        EmulatorError,
        match=rf"function 'main'.*TLOAD.*m0 index {index}.*\[0, 2\)",
    ):
        execute_assembly(source)


def test_uninitialized_memory_read_is_rejected_with_context() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .memory m0, tryte, 1, mutable
.label entry
    TCONST r0, 0
    TLOAD r1, m0, r0 ; source=3:8:10
    TRET r1
.end
"""
    with pytest.raises(
        EmulatorError,
        match=r"function 'main'.*TLOAD.*source 3:8.*uninitialized memory m0.*index 0",
    ):
        execute_assembly(source)


def test_immutable_memory_rejects_second_store() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 1, immutable
.label entry
    TCONST r0, 0
    TCONST r1, 1
    TCONST r2, 2
    TSTORE m0, r0, r1
    TSTORE m0, r0, r2
    TRET r2
.end
"""
    with pytest.raises(EmulatorError, match="immutable and already initialized"):
        execute_assembly(source)


def test_memory_object_and_register_types_are_validated() -> None:
    unknown = """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
.label entry
    TCONST r0, 0
    TLOAD r1, m9, r0
    TRET r1
.end
"""
    with pytest.raises(EmulatorError, match="unknown memory object m9"):
        execute_assembly(unknown)

    wrong_index = """\
.function main -> tryte
    .register r0, trit
    .register r1, tryte
    .memory m0, tryte, 1
.label entry
    TCONST r0, 0
    TLOAD r1, m0, r0
    TRET r1
.end
"""
    with pytest.raises(EmulatorError, match="index must be a tryte"):
        execute_assembly(wrong_index)

    wrong_value = """\
.function main -> tryte
    .register r0, tryte
    .register r1, trit
    .register r2, tryte
    .memory m0, tryte, 1
.label entry
    TCONST r0, 0
    TCONST r1, 1
    TSTORE m0, r0, r1
    TRET r2
.end
"""
    with pytest.raises(EmulatorError, match="source type does not match"):
        execute_assembly(wrong_value)


def test_duplicate_and_invalid_memory_declarations_are_rejected() -> None:
    duplicate = """\
.function main -> tryte
    .register r0, tryte
    .memory m0, tryte, 1
    .memory m0, tryte, 1
.label entry
    TCONST r0, 0
    TRET r0
.end
"""
    with pytest.raises(AssemblyParseError, match="duplicate memory object m0"):
        parse_assembly(duplicate)

    invalid_length = """\
.function main -> tryte
    .register r0, tryte
    .memory m0, tryte, 0
.label entry
    TCONST r0, 0
    TRET r0
.end
"""
    with pytest.raises(EmulatorError, match="invalid length 0"):
        execute_assembly(invalid_length)

    too_long = """\
.function main -> tryte
    .register r0, tryte
    .memory m0, trit, 366
.label entry
    TCONST r0, 0
    TRET r0
.end
"""
    with pytest.raises(EmulatorError, match="indexable maximum 365"):
        execute_assembly(too_long)


def test_maximum_tryte_array_fits_default_memory_limit() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    .memory m0, tryte, 365
.label entry
    TCONST r0, 0
    TRET r0
.end
"""
    assert DEFAULT_MAX_MEMORY_TRITS == 6561
    assert execute_assembly(source) == 0


def test_tryte_memory_costs_six_logical_trits() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    .memory m0, tryte, 1
.label entry
    TCONST r0, 0
    TRET r0
.end
"""
    with pytest.raises(
        EmulatorError,
        match=r"function 'main' requires 6 logical trits.*limit is 5",
    ):
        execute_assembly(source, max_memory_trits=5)


def test_multiple_objects_over_default_memory_limit_are_rejected() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    .memory m0, tryte, 365
    .memory m1, tryte, 365
    .memory m2, tryte, 365
.label entry
    TCONST r0, 0
    TRET r0
.end
"""
    with pytest.raises(
        EmulatorError,
        match=(
            r"function 'main' requires 6570 logical trits of frame memory; "
            r"limit is 6561"
        ),
    ):
        execute_assembly(source)


def test_custom_smaller_memory_limit_is_enforced_per_frame() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    .memory m0, tryte, 2
.label entry
    TCONST r0, 0
    TRET r0
.end
"""
    with pytest.raises(
        EmulatorError,
        match=(
            r"function 'main' requires 12 logical trits of frame memory; "
            r"limit is 11"
        ),
    ):
        execute_assembly(source, max_memory_trits=11)


def test_recursive_frames_have_independent_memory() -> None:
    source = (ROOT / "examples" / "recursive_memory.s3").read_text(
        encoding="utf-8"
    )
    assert run_source(source) == 6


def test_overflow_before_memory_store_remains_detectable() -> None:
    source = """\
fn main() -> tryte {
    mut tryte value = 364;
    value = value + 1;
    return value;
}
"""
    with pytest.raises(EmulatorError, match="tryte overflow"):
        run_source(source)


def test_memory_instruction_rejects_undeclared_register() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    .memory m0, tryte, 1
.label entry
    TLOAD r0, m0, r99
    TRET r0
.end
"""
    with pytest.raises(EmulatorError, match="invalid register r99"):
        execute_assembly(source)


def test_old_assembly_without_memory_remains_compatible() -> None:
    source = (ROOT / "examples" / "assembly_recursive_sum.s3asm").read_text(
        encoding="utf-8"
    )
    assert execute_assembly(source) == 10
