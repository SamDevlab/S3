from __future__ import annotations

import json

import pytest

from bootstrap.s3.ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRModule,
    IROpcode,
    IRRegister,
    IRStaticString,
    IRType,
)
from bootstrap.s3.ir_serialization import IRSerializationError, deserialize_ir, serialize_ir
from bootstrap.s3.optimizer import optimize_ir
from bootstrap.s3.verifier import IRVerificationError, verify_ir


def _module_with_static_string() -> IRModule:
    return IRModule(
        (
            IRFunction(
                "main",
                (),
                IRType.TRYTE,
                (
                    IRRegister(0, IRType.STRING),
                    IRRegister(1, IRType.TRYTE),
                ),
                (
                    IRBasicBlock(
                        "entry",
                        (
                            IRInstruction(
                                IROpcode.CONST_STR,
                                result=0,
                                static_string="s0",
                            ),
                            IRInstruction(IROpcode.CONST, result=1, immediate=0),
                            IRInstruction(IROpcode.RETURN, operands=(1,)),
                        ),
                    ),
                ),
            ),
        ),
        (IRStaticString("s0", "olá\n"),),
    )


def test_const_str_ir_verifies_and_serializes_static_string_table() -> None:
    module = _module_with_static_string()
    verify_ir(module)

    payload = json.loads(serialize_ir(module))
    static_entry = payload["module"]["static_strings"][0]
    instruction = payload["module"]["functions"][0]["blocks"][0]["instructions"][0]

    assert static_entry == {
        "byte_count": 5,
        "id": "s0",
        "sha256": "97bc03074ee52a8e760b5ce321cd57fb0c312df23388a480b5a035a1279539d9",
        "utf8_bytes": [111, 108, 195, 161, 10],
        "value": "olá\n",
    }
    assert instruction["opcode"] == "const_str"
    assert instruction["static_string"] == "s0"
    assert deserialize_ir(serialize_ir(module)) == module


def test_ir_without_static_strings_keeps_legacy_module_shape() -> None:
    module = IRModule(
        (
            IRFunction(
                "main",
                (),
                IRType.TRYTE,
                (IRRegister(0, IRType.TRYTE),),
                (
                    IRBasicBlock(
                        "entry",
                        (
                            IRInstruction(IROpcode.CONST, result=0, immediate=0),
                            IRInstruction(IROpcode.RETURN, operands=(0,)),
                        ),
                    ),
                ),
            ),
        )
    )

    assert "static_strings" not in json.loads(serialize_ir(module))["module"]


def test_const_str_requires_known_static_string_id() -> None:
    module = _module_with_static_string()
    bad_instruction = IRInstruction(
        IROpcode.CONST_STR,
        result=0,
        static_string="s1",
    )
    bad_function = module.functions[0]
    bad_module = IRModule(
        (
            IRFunction(
                bad_function.name,
                bad_function.parameters,
                bad_function.return_type,
                bad_function.registers,
                (
                    IRBasicBlock(
                        "entry",
                        (
                            bad_instruction,
                            bad_function.blocks[0].instructions[1],
                            bad_function.blocks[0].instructions[2],
                        ),
                    ),
                ),
            ),
        ),
        module.static_strings,
    )

    with pytest.raises(IRVerificationError, match="unknown static string 's1'"):
        verify_ir(bad_module)


def test_numeric_ir_opcodes_do_not_accept_string_values() -> None:
    block = IRBasicBlock(
        "entry",
        (
            IRInstruction(IROpcode.CONST_STR, result=0, static_string="s0"),
            IRInstruction(IROpcode.ADD, result=1, operands=(0, 0)),
            IRInstruction(IROpcode.RETURN, operands=(1,)),
        ),
    )
    module = IRModule(
        (
            IRFunction(
                "main",
                (),
                IRType.STRING,
                (IRRegister(0, IRType.STRING), IRRegister(1, IRType.STRING)),
                (block,),
            ),
        ),
        (IRStaticString("s0", "x"),),
    )

    with pytest.raises(IRVerificationError, match="add does not support string values"):
        verify_ir(module)


def test_static_string_metadata_is_validated_on_deserialization() -> None:
    payload = json.loads(serialize_ir(_module_with_static_string()))
    payload["module"]["static_strings"][0]["byte_count"] = 999

    with pytest.raises(IRSerializationError, match="byte_count does not match"):
        deserialize_ir(json.dumps(payload))


def test_o1_preserves_static_string_table_and_removes_dead_const_str() -> None:
    optimized = optimize_ir(_module_with_static_string(), "O1")

    assert optimized.static_strings == (IRStaticString("s0", "olá\n"),)
    opcodes = [
        instruction.opcode
        for function in optimized.functions
        for block in function.blocks
        for instruction in block.instructions
    ]
    assert IROpcode.CONST_STR not in opcodes
    verify_ir(optimized)
