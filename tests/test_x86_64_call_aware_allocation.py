"""Focused contracts for the 1.22 call-aware allocator and emitter."""

from __future__ import annotations

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64 import X8664Backend
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.backends.x86_64.liveness import analyze_liveness
from bootstrap.s3.backends.x86_64.registers import (
    CALLER_SAVED_ALLOCATABLE_REGISTERS,
    CALLEE_SAVED_ALLOCATABLE_REGISTERS,
    FULL_ALLOCATABLE_REGISTERS,
)


def _call_program() -> object:
    return parse_assembly(
        """
        .function helper -> tryte
            .param r0, tryte
        .label entry
            TRET r0
        .end
        .function main -> tryte
            .register r0, tryte
            .register r1, tryte
            .register r2, tryte
            .register r3, tryte
            .register r4, tryte
            .register r5, tryte
            .register r6, tryte
            .register r7, tryte
        .label entry
            TCONST r0, 1
            TCONST r1, 2
            TCONST r2, 3
            TCONST r3, 4
            TCONST r4, 5
            TCONST r5, 6
            TCONST r6, 7
            TCALL r7, helper, r6
            TADD r0, r0, r1
            TADD r2, r2, r3
            TADD r4, r4, r5
            TADD r0, r0, r2
            TADD r0, r0, r4
            TADD r0, r0, r7
            TRET r0
        .end
        """
    )


def test_register_contract_has_eleven_deterministic_colors() -> None:
    assert CALLEE_SAVED_ALLOCATABLE_REGISTERS == ("rbx", "r12", "r13", "r14", "r15")
    assert CALLER_SAVED_ALLOCATABLE_REGISTERS == ("rdi", "rsi", "rdx", "rcx", "r8", "r9")
    assert len(FULL_ALLOCATABLE_REGISTERS) == 11


def test_call_survivor_excludes_call_destination() -> None:
    program = _call_program()
    function = program.functions[1]
    call = next(inst for block in function.blocks for inst in block.instructions if inst.opcode.value == "TCALL")
    assert function.result_width == 1
    assert call.result_registers == (7,)
    assert 7 not in analyze_liveness(function).live_across_call(call)


def test_call_crossing_values_prefer_callee_saved_registers() -> None:
    plan = analyze_allocation(_call_program().functions[1])
    crossing = set().union(*plan.call_survivors.values())
    for register in crossing:
        physical = plan.physical_register(register)
        assert physical in FULL_ALLOCATABLE_REGISTERS
    assert any(
        plan.physical_register(register) in CALLEE_SAVED_ALLOCATABLE_REGISTERS
        for register in crossing
    )


def test_caller_saved_call_spill_slots_are_emitted_deterministically() -> None:
    assembly = X8664Backend(register_allocation=True).generate(_call_program())
    assert "call s3_helper" in assembly
    assert "mov qword ptr [rbp -" in assembly
    assert "rdi" in assembly


def test_default_path_remains_byte_identical() -> None:
    program = _call_program()
    assert X8664Backend(register_allocation=False).generate(program) == X8664Backend().generate(program)


def test_same_argument_and_destination_does_not_restore_old_value() -> None:
    program = parse_assembly(
        """
        .function helper -> tryte
            .param r0, tryte
        .label entry
            TADD r0, r0, r0
            TRET r0
        .end
        .function main -> tryte
            .register r0, tryte
        .label entry
            TCONST r0, 7
            TCALL r0, helper, r0
            TRET r0
        .end
        """
    )
    function = program.functions[1]
    call = next(inst for block in function.blocks for inst in block.instructions if inst.opcode.value == "TCALL")
    plan = analyze_allocation(function)
    assert 0 not in plan.call_survivors_for(call)
    assembly = X8664Backend(register_allocation=True).generate(program)
    assert assembly.count("call s3_helper") == 1
