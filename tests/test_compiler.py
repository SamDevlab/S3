from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.assembly import AssemblyOpcode, parse_assembly
from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.ir import IROpcode
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.lexer import SyntaxMode


FIRST_PROGRAM = Path("examples/first.s3").read_text(encoding="utf-8")


def test_first_program_compiles_through_every_stage() -> None:
    result = compile_source(FIRST_PROGRAM, mode=SyntaxMode.V0_6)
    assert result.tokens
    assert result.ast.functions[0].name == "main"
    assert result.ir.functions[0].name == "main"
    assert ".function main -> tryte" in result.assembly_text


def test_subtraction_lowers_to_invert_then_add() -> None:
    result = compile_source(
        "fn main() -> tryte:\n"
        "    mut value: tryte = 2\n"
        "    value = value + 1\n"
        "    return value - 1\n",
        mode=SyntaxMode.V0_6,
    )
    opcodes = [
        instruction.opcode
        for instruction in result.ir.functions[0].instructions
    ]
    assert IROpcode.INVERT in opcodes
    invert_index = opcodes.index(IROpcode.INVERT)
    assert opcodes[invert_index + 1] is IROpcode.ADD
    assert set(IROpcode) == {
        IROpcode.CONST,
        IROpcode.CONST_STR,
        IROpcode.MOVE,
        IROpcode.INVERT,
        IROpcode.ADD,
        IROpcode.NUMERIC_DIFFERENCE,
        IROpcode.MULTIPLY,
        IROpcode.DIVIDE,
        IROpcode.RELATE,
        IROpcode.CONVERT,
        IROpcode.MINIMUM,
        IROpcode.MAXIMUM,
        IROpcode.COMPARE,
        IROpcode.CALL,
        IROpcode.LOAD,
        IROpcode.STORE,
        IROpcode.RETURN,
        IROpcode.JUMP,
            IROpcode.BRANCH3,
        IROpcode.ADDRESS_OF,
        IROpcode.AGGREGATE_ADDRESS_OF,
        IROpcode.AGGREGATE_FIELD_LOAD,
        IROpcode.AGGREGATE_FIELD_ADDRESS,
        IROpcode.REFERENCE_LOAD,
        IROpcode.REFERENCE_STORE,
        IROpcode.SLICE_LENGTH,
        IROpcode.SLICE_LOAD,
        IROpcode.SLICE_STORE,
        }


def test_assembly_has_no_subtraction_instruction() -> None:
    result = compile_source(FIRST_PROGRAM, mode=SyntaxMode.V0_6)
    assert "TSUB" not in result.assembly_text
    assert "TSUB" not in AssemblyOpcode.__members__
    reparsed = parse_assembly(result.assembly_text)
    assert reparsed.functions[0].instructions


def test_first_program_returns_six() -> None:
    assert run_source(FIRST_PROGRAM, mode=SyntaxMode.V0_6) == 6
    result = compile_source(FIRST_PROGRAM, mode=SyntaxMode.V0_6)
    assert execute_assembly(result.assembly_text) == 6


def test_undeclared_variable_is_rejected_with_location() -> None:
    source = "fn main() -> tryte {\n    return missing;\n}\n"
    with pytest.raises(
        SemanticError,
        match=r"2:12: semantic error: undeclared variable 'missing'",
    ):
        compile_source(source, mode=SyntaxMode.V0_5)


def test_duplicate_variable_is_rejected() -> None:
    source = """\
fn main() -> tryte {
    tryte value = 1;
    tryte value = 2;
    return value;
}
"""
    with pytest.raises(SemanticError, match="duplicate declaration"):
        compile_source(source, mode=SyntaxMode.V0_5)


@pytest.mark.parametrize(
    ("type_name", "literal", "range_text"),
    (("trit", "2", r"\[-1, 1\]"), ("tryte", "365", r"\[-364, 364\]")),
)
def test_out_of_range_literal_is_rejected(
    type_name: str,
    literal: str,
    range_text: str,
) -> None:
    source = (
        f"fn main() -> {type_name} {{\n"
        f"    return {literal};\n"
        "}\n"
    )
    with pytest.raises(SemanticError, match=range_text):
        compile_source(source, mode=SyntaxMode.V0_5)


def test_return_type_is_checked() -> None:
    source = """\
fn main() -> trit {
    tryte value = 1;
    return value;
}
"""
    with pytest.raises(SemanticError, match=r"has type tryte; expected trit"):
        compile_source(source, mode=SyntaxMode.V0_5)


def test_statement_after_return_is_rejected() -> None:
    source = """\
fn main() -> tryte {
    return 0;
    tryte unreachable = 1;
}
"""
    with pytest.raises(SemanticError, match="unreachable statement after return"):
        compile_source(source, mode=SyntaxMode.V0_5)


def test_constant_source_arithmetic_overflow_is_detected_semantically() -> None:
    source = "fn main() -> tryte { return 364 + 1; }"
    with pytest.raises(SemanticError, match="tryte overflow"):
        run_source(source, mode=SyntaxMode.V0_5)


def test_all_initial_operators_execute() -> None:
    sources_and_results = [
        ("return 2 + 3;", 5),
        ("return ~2;", -2),
        ("return 5 & 1;", -4),
        ("return 5 | 1;", 10),
    ]
    for statement, expected in sources_and_results:
        source = f"fn main() -> tryte {{ {statement} }}"
        assert run_source(source, mode=SyntaxMode.V0_5) == expected
    assert (
        run_source(
            "fn main() -> trit { return 2 <=> 3; }",
            mode=SyntaxMode.V0_5,
        )
        == -1
    )
