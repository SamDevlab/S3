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
    IRType,
)
from bootstrap.s3.ir_serialization import (
    IR_FORMAT_VERSION,
    IRSerializationError,
    deserialize_ir,
    serialize_ir,
)
from bootstrap.s3.verifier import IRVerificationError, verify_ir


def _two_cell_module() -> IRModule:
    callee = IRFunction(
        "pair",
        (),
        IRType.TRYTE,
        (
            IRRegister(0, IRType.TRYTE),
            IRRegister(1, IRType.TRIT),
        ),
        (
            IRBasicBlock(
                "entry",
                (
                    IRInstruction(IROpcode.CONST, result=0, immediate=7),
                    IRInstruction(IROpcode.CONST, result=1, immediate=1),
                    IRInstruction(IROpcode.RETURN, operands=(0, 1)),
                ),
            ),
        ),
        result_types=(IRType.TRYTE, IRType.TRIT),
    )
    caller = IRFunction(
        "main",
        (),
        IRType.TRYTE,
        (
            IRRegister(0, IRType.TRYTE),
            IRRegister(1, IRType.TRIT),
            IRRegister(2, IRType.TRYTE),
        ),
        (
            IRBasicBlock(
                "entry",
                (
                    IRInstruction(
                        IROpcode.CALL,
                        callee="pair",
                        results=(0, 1),
                    ),
                    IRInstruction(IROpcode.CONST, result=2, immediate=0),
                    IRInstruction(IROpcode.RETURN, operands=(2,)),
                ),
            ),
        ),
    )
    return IRModule((callee, caller))


def test_ir_writer_uses_0_6_result_types_and_call_results() -> None:
    payload = json.loads(serialize_ir(_two_cell_module()))

    assert IR_FORMAT_VERSION == "0.6.0"
    assert payload["version"] == "0.6.0"
    pair = payload["module"]["functions"][0]
    call = payload["module"]["functions"][1]["blocks"][0]["instructions"][0]
    ret = pair["blocks"][0]["instructions"][-1]

    assert pair["result_types"] == ["tryte", "trit"]
    assert call["results"] == [0, 1]
    assert call["result"] is None
    assert ret["operands"] == [0, 1]


def test_ir_0_6_round_trips_multi_cell_results() -> None:
    source = serialize_ir(_two_cell_module())
    restored = deserialize_ir(source)

    assert restored == _two_cell_module()
    assert serialize_ir(restored) == source


def test_ir_reader_normalizes_0_5_width_one_to_result_lists() -> None:
    legacy = {
        "format": "s3-ir",
        "version": "0.5.0",
        "module": {
            "functions": [
                {
                    "blocks": [
                        {
                            "instructions": [
                                {
                                    "callee": None,
                                    "immediate": 0,
                                    "initialization": False,
                                    "memory": None,
                                    "opcode": "const",
                                    "operands": [],
                                    "result": 0,
                                    "source": None,
                                    "targets": [],
                                },
                                {
                                    "callee": None,
                                    "immediate": None,
                                    "initialization": False,
                                    "memory": None,
                                    "opcode": "return",
                                    "operands": [0],
                                    "result": None,
                                    "source": None,
                                    "targets": [],
                                },
                            ],
                            "name": "entry",
                            "source": None,
                        }
                    ],
                    "memory_objects": [],
                    "name": "main",
                    "parameters": [],
                    "registers": [{"index": 0, "source": None, "type": "tryte"}],
                    "return_type": "tryte",
                    "source": None,
                }
            ]
        },
    }

    module = deserialize_ir(json.dumps(legacy))
    function = module.functions[0]

    assert function.result_types == (IRType.TRYTE,)
    assert function.instructions[0].results == (0,)
    assert serialize_ir(module).endswith("\n")
    assert json.loads(serialize_ir(module))["version"] == "0.6.0"


def test_ir_0_5_rejects_0_6_result_fields() -> None:
    legacy = json.loads(serialize_ir(_two_cell_module()))
    legacy["version"] = "0.5.0"

    with pytest.raises(IRSerializationError, match="0.6.0 result fields"):
        deserialize_ir(json.dumps(legacy))


def test_verifier_rejects_call_result_width_mismatch() -> None:
    module = _two_cell_module()
    caller = module.functions[1]
    bad_call = IRInstruction(IROpcode.CALL, callee="pair", results=(0,))
    bad_caller = IRFunction(
        caller.name,
        caller.parameters,
        caller.return_type,
        caller.registers,
        (
            IRBasicBlock(
                "entry",
                (bad_call, *caller.blocks[0].instructions[1:]),
            ),
        ),
    )

    with pytest.raises(IRVerificationError, match="call result count"):
        verify_ir(IRModule((module.functions[0], bad_caller)))


def test_verifier_rejects_return_result_type_mismatch() -> None:
    function = IRFunction(
        "bad",
        (),
        IRType.TRYTE,
        (
            IRRegister(0, IRType.TRIT),
            IRRegister(1, IRType.TRYTE),
        ),
        (
            IRBasicBlock(
                "entry",
                (IRInstruction(IROpcode.RETURN, operands=(0, 1)),),
            ),
        ),
        result_types=(IRType.TRYTE, IRType.TRIT),
    )

    with pytest.raises(IRVerificationError, match="return cell 0"):
        verify_ir(IRModule((function,)))
