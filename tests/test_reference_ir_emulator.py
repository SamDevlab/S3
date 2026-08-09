from __future__ import annotations

import pytest

from bootstrap.s3.ir import IRBasicBlock, IRFunction, IRInstruction, IRModule, IROpcode, IRRegister, IRType
from bootstrap.s3.ir_emulator import IRExecutionError
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.verifier import IRVerificationError, verify_ir


pytestmark = [pytest.mark.s3_fast, pytest.mark.s3_contract, pytest.mark.s3_differential]


def _run(source: str, optimization: str = "O0") -> int:
    return run_source(source, optimization=optimization)


def test_reference_ir_is_explicit_and_not_integer() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut value: tryte = 1\n"
        "    ref: &mut tryte = &mut value\n"
        "    *ref = 7\n"
        "    return *ref\n"
    )
    module = compile_source(source).ir
    instructions = module.functions[0].instructions
    assert any(item.opcode is IROpcode.ADDRESS_OF for item in instructions)
    assert any(item.opcode is IROpcode.REFERENCE_LOAD for item in instructions)
    assert any(item.opcode is IROpcode.REFERENCE_STORE for item in instructions)
    assert any(register.type is IRType.REFERENCE for register in module.functions[0].registers)
    assert _run(source, "O0") == _run(source, "O1") == 7


def test_direct_and_indirect_storage_are_coherent_in_both_optimizations() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut value: tryte = 1\n"
        "    ref: &mut tryte = &mut value\n"
        "    *ref = 5\n"
        "    value = 7\n"
        "    return *ref\n"
    )
    assert _run(source, "O0") == 7
    assert _run(source, "O1") == 7


def test_copied_reference_and_two_aliases_share_storage() -> None:
    source = (
        "fn main() -> tryte:\n"
        "    mut value: tryte = 1\n"
        "    first: &mut tryte = &mut value\n"
        "    second: &mut tryte = first\n"
        "    *first = 9\n"
        "    *second = 10\n"
        "    return *first\n"
    )
    assert _run(source, "O0") == _run(source, "O1") == 10


def test_mutable_reference_parameter_updates_caller_storage() -> None:
    source = (
        "fn modify(ref: &mut tryte) -> tryte:\n"
        "    *ref = 10\n"
        "    return *ref\n"
        "fn main() -> tryte:\n"
        "    mut value: tryte = 1\n"
        "    result: tryte = modify(&mut value)\n"
        "    return value\n"
    )
    assert _run(source, "O0") == _run(source, "O1") == 10


def test_reference_parameter_read_preserves_caller_frame_identity() -> None:
    source = (
        "fn read(ref: &tryte) -> tryte:\n"
        "    return *ref\n"
        "fn main() -> tryte:\n"
        "    value: tryte = 11\n"
        "    return read(&value)\n"
    )
    assert _run(source, "O0") == _run(source, "O1") == 11


def test_malformed_reference_ir_is_rejected() -> None:
    registers = (
        IRRegister(0, IRType.TRYTE),
        IRRegister(1, IRType.TRYTE),
    )
    function = IRFunction(
        "main", (), IRType.TRYTE, registers,
        (IRBasicBlock("entry", (
            IRInstruction(IROpcode.REFERENCE_LOAD, result=1, operands=(0,), reference_target=IRType.TRYTE),
            IRInstruction(IROpcode.RETURN, operands=(1,)),
        )),),
    )
    with pytest.raises(IRVerificationError):
        verify_ir(IRModule((function,)))


def test_shared_reference_store_is_rejected_by_ir_validation() -> None:
    registers = (
        IRRegister(0, IRType.REFERENCE, reference_target=IRType.TRYTE, reference_mutable=False),
        IRRegister(1, IRType.TRYTE),
    )
    function = IRFunction(
        "main", (), IRType.TRYTE, registers,
        (IRBasicBlock("entry", (
            IRInstruction(IROpcode.REFERENCE_STORE, operands=(0, 1), reference_target=IRType.TRYTE, reference_mutable=False),
            IRInstruction(IROpcode.RETURN, operands=(1,)),
        )),),
    )
    with pytest.raises(IRVerificationError):
        verify_ir(IRModule((function,)))
