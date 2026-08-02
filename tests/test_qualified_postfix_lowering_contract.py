from __future__ import annotations

import pytest

from bootstrap.s3.emulator import execute_assembly
from bootstrap.s3.ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRModule,
    IROpcode,
    IRRegister,
    IRType,
)
from bootstrap.s3.pipeline import compile_source, compile_sources
from bootstrap.s3.verifier import IRVerificationError, verify_ir


def _call_instructions(function: IRFunction) -> list[IRInstruction]:
    return [
        instruction
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CALL
    ]


def test_qualified_calls_lower_to_concrete_ir_callees_and_verify() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from math import inc\n"
            "from math import one\n"
            "fn main() -> tryte:\n"
            "    return math.inc(math.one())\n"
        ),
        "math.s3": (
            "module math\n"
            "export fn one() -> tryte:\n"
            "    return 1\n"
            "export fn inc(value: tryte) -> tryte:\n"
            "    return value + 1\n"
        ),
    }

    compilation = compile_sources(sources, "O0")
    verify_ir(compilation.ir)
    main = next(function for function in compilation.ir.functions if function.name == "main")

    calls = _call_instructions(main)
    assert [call.callee for call in calls] == [
        "__s3mod_math__one",
        "__s3mod_math__inc",
    ]
    assert all("." not in (call.callee or "") for call in calls)
    assert execute_assembly(compilation.assembly) == 2


def test_qualified_enum_variants_lower_to_existing_discriminants() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from colors import marker\n"
            "fn main() -> tryte:\n"
            "    match colors.marker():\n"
            "        colors.Sign.Negative:\n"
            "            return -1\n"
            "        colors.Sign.Zero:\n"
            "            return 0\n"
            "        colors.Sign.Positive:\n"
            "            return 1\n"
        ),
        "colors.s3": (
            "module colors\n"
            "export enum Sign:\n"
            "    Negative\n"
            "    Zero\n"
            "    Positive\n"
            "export fn marker() -> Sign:\n"
            "    return Sign.Positive\n"
        ),
    }

    compilation = compile_sources(sources, "O0")
    verify_ir(compilation.ir)
    constants = [
        instruction.immediate
        for function in compilation.ir.functions
        for instruction in function.instructions
        if instruction.opcode is IROpcode.CONST
    ]

    assert 2 in constants
    assert execute_assembly(compilation.assembly) == 1


def test_record_members_lower_to_flattened_scalar_parameters() -> None:
    source = (
        "record Pair:\n"
        "    left: tryte\n"
        "    right: tryte\n"
        "fn sum(pair: Pair) -> tryte:\n"
        "    return pair.left + pair.right\n"
        "fn main() -> tryte:\n"
        "    pair: Pair = Pair(left=2, right=3)\n"
        "    return sum(pair)\n"
    )

    compilation = compile_source(source, "O0")
    verify_ir(compilation.ir)
    sum_function = next(
        function for function in compilation.ir.functions if function.name == "sum"
    )

    assert [(parameter.name, parameter.type) for parameter in sum_function.parameters] == [
        ("pair__left", IRType.TRYTE),
        ("pair__right", IRType.TRYTE),
    ]
    assert [instruction.opcode for instruction in sum_function.instructions] == [
        IROpcode.ADD,
        IROpcode.RETURN,
    ]
    assert execute_assembly(compilation.assembly) == 5


def test_member_access_after_qualified_single_field_record_call_reuses_call_result() -> None:
    sources = {
        "main.s3": (
            "module main\n"
            "from maker import make\n"
            "fn main() -> tryte:\n"
            "    return maker.make().value\n"
        ),
        "maker.s3": (
            "module maker\n"
            "record Box:\n"
            "    value: tryte\n"
            "export fn make() -> Box:\n"
            "    return Box(value=7)\n"
        ),
    }

    compilation = compile_sources(sources, "O0")
    verify_ir(compilation.ir)
    main = next(function for function in compilation.ir.functions if function.name == "main")
    calls = _call_instructions(main)
    returns = [
        instruction
        for instruction in main.instructions
        if instruction.opcode is IROpcode.RETURN
    ]

    assert [call.callee for call in calls] == ["__s3mod_maker__make"]
    assert returns == [
        IRInstruction(
            opcode=IROpcode.RETURN,
            operands=(calls[0].results[0],),
            location=returns[0].location,
        )
    ]
    assert execute_assembly(compilation.assembly) == 7


def test_source_unit_order_does_not_change_qualified_lowering_ir() -> None:
    main_source = (
        "module main\n"
        "from math import inc\n"
        "fn main() -> tryte:\n"
        "    return math.inc(4)\n"
    )
    math_source = (
        "module math\n"
        "export fn inc(value: tryte) -> tryte:\n"
        "    return value + 1\n"
    )

    left = compile_sources(
        {"main.s3": main_source, "math.s3": math_source},
        "O0",
    ).ir.to_dict()
    right = compile_sources(
        {"math.s3": math_source, "main.s3": main_source},
        "O0",
    ).ir.to_dict()

    assert left == right


def test_verifier_rejects_unresolved_textual_member_or_unknown_member_opcode() -> None:
    module = IRModule(
        functions=(
            IRFunction(
                name="main",
                parameters=(),
                return_type=IRType.TRYTE,
                registers=(IRRegister(0, IRType.TRYTE),),
                blocks=(
                    IRBasicBlock(
                        "entry",
                        (
                            IRInstruction(
                                opcode=IROpcode.CALL,
                                result=0,
                                callee="math.inc",
                            ),
                            IRInstruction(opcode=IROpcode.RETURN, operands=(0,)),
                        ),
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(IRVerificationError, match="call to nonexistent function"):
        verify_ir(module)

    unknown_member_ir = IRModule(
        functions=(
            IRFunction(
                name="main",
                parameters=(),
                return_type=IRType.TRYTE,
                registers=(IRRegister(0, IRType.TRYTE),),
                blocks=(
                    IRBasicBlock(
                        "entry",
                        (
                            IRInstruction(opcode="member", result=0),
                            IRInstruction(opcode=IROpcode.RETURN, operands=(0,)),
                        ),
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(IRVerificationError, match="unknown IR opcode 'member'"):
        verify_ir(unknown_member_ir)
