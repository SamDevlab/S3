from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.assembly import (
    AssemblyOpcode,
    parse_assembly,
)
from bootstrap.s3.emulator import EmulatorError, execute_assembly
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.lexer import SyntaxMode


RECURSIVE_SOURCE = Path("examples/recursive_sum.s3").read_text(encoding="utf-8")


def test_generated_assembly_contains_parameters_labels_calls_and_branches() -> None:
    compilation = compile_source(RECURSIVE_SOURCE, mode=SyntaxMode.V0_6)
    text = compilation.assembly_text
    assert ".param r0, tryte" in text
    assert ".label entry" in text
    assert "TCALL" in text
    assert "TBR3" in text
    assert "TINV" in text
    assert "TADD" in text
    assert "TSUB" not in text


def test_assembly_round_trip_preserves_complete_model() -> None:
    assembly = compile_source(RECURSIVE_SOURCE, mode=SyntaxMode.V0_6).assembly
    reparsed = parse_assembly(assembly.render())
    assert reparsed == assembly
    assert reparsed.render() == assembly.render()


def test_parser_recognizes_tcall_tbr3_and_tjmp() -> None:
    source = """\
.function helper -> tryte
    .param r0, tryte
.label entry
    TRET r0
.end

.function main -> tryte
    .register r0, trit
    .register r1, tryte
    .register r2, tryte
.label entry
    TCONST r0, 0
    TBR3 r0, negative, neutral, positive
.label negative
    TJMP done
.label neutral
    TJMP done
.label positive
    TJMP done
.label done
    TCONST r1, 4
    TCALL r2, helper, r1
    TRET r2
.end
"""
    program = parse_assembly(source)
    opcodes = {
        instruction.opcode
        for function in program.functions
        for instruction in function.instructions
    }
    assert {
        AssemblyOpcode.TCALL,
        AssemblyOpcode.TBR3,
        AssemblyOpcode.TJMP,
    } <= opcodes
    assert execute_assembly(program) == 4


def test_assembly_rejects_nonexistent_function() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
.label entry
    TCALL r0, absent
    TRET r0
.end
"""
    with pytest.raises(EmulatorError, match="nonexistent function 'absent'"):
        execute_assembly(source)


def test_assembly_rejects_nonexistent_label() -> None:
    source = """\
.function main -> tryte
.label entry
    TJMP missing
.end
"""
    with pytest.raises(EmulatorError, match="unknown label 'missing'"):
        execute_assembly(source)


def test_assembly_rejects_call_type_mismatch() -> None:
    source = """\
.function helper -> trit
    .param r0, trit
.label entry
    TRET r0
.end

.function main -> trit
    .register r0, tryte
    .register r1, trit
.label entry
    TCONST r0, 1
    TCALL r1, helper, r0
    TRET r1
.end
"""
    with pytest.raises(EmulatorError, match="incompatible argument types"):
        execute_assembly(source)


def test_assembly_rejects_undeclared_register_in_unreachable_block() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
.label entry
    TCONST r0, 0
    TRET r0
.label unreachable
    TCONST r99, 1
    TRET r99
.end
"""
    with pytest.raises(EmulatorError, match="invalid register r99"):
        execute_assembly(source)


def test_tbr3_requires_trit_and_three_distinct_labels() -> None:
    wrong_type = """\
.function main -> tryte
    .register r0, tryte
.label entry
    TCONST r0, 0
    TBR3 r0, a, b, c
.label a
    TRET r0
.label b
    TRET r0
.label c
    TRET r0
.end
"""
    with pytest.raises(EmulatorError, match="condition must be a trit"):
        execute_assembly(wrong_type)

    duplicate = """\
.function main -> trit
    .register r0, trit
.label entry
    TCONST r0, 0
    TBR3 r0, a, a, c
.label a
    TRET r0
.label c
    TRET r0
.end
"""
    with pytest.raises(EmulatorError, match="labels must be distinct"):
        execute_assembly(duplicate)


def test_main_parameters_are_rejected_by_emulator() -> None:
    source = """\
.function main -> tryte
    .param r0, tryte
.label entry
    TRET r0
.end
"""
    with pytest.raises(EmulatorError, match="must not declare parameters"):
        execute_assembly(source)


def test_assembly_block_without_return_or_jump_is_rejected() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
.label entry
    TCONST r0, 1
.end
"""
    with pytest.raises(EmulatorError, match="has no terminator"):
        execute_assembly(source)


def test_assembly_function_without_tret_is_rejected() -> None:
    source = """\
.function main -> tryte
.label entry
    TJMP entry
.end
"""
    with pytest.raises(EmulatorError, match="has no TRET instruction"):
        execute_assembly(source)


def test_source_metadata_appears_in_runtime_error() -> None:
    source = """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
.label entry
    TCONST r0, 364
    TCONST r1, 1
    TADD r2, r0, r1 ; source=7:12:42
    TRET r2
.end
"""
    with pytest.raises(
        EmulatorError,
        match=r"function 'main'.*assembly line 8.*source 7:12.*overflow",
    ):
        execute_assembly(source)


def test_unconditional_jump_from_source_switch_continuation() -> None:
    source = """\
fn helper(x: trit) -> tryte {
    switch (x) {
        -1: {}
        0: {}
        1: {}
    }
    return 7;
}

fn main() -> tryte {
    return helper(0);
}
"""
    compilation = compile_source(source, mode=SyntaxMode.V0_5)
    assert "TJMP" in compilation.assembly_text
    assert run_source(source, mode=SyntaxMode.V0_5) == 7




