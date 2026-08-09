"""Tests for the physical register contracts and System V AMD64 invariants."""

from __future__ import annotations

from bootstrap.s3.backends.x86_64.registers import (
    EMITTER_SCRATCH_REGISTERS,
    FRAME_POINTER,
    INITIAL_ALLOCATABLE_REGISTERS,
    NON_ALLOCATABLE_REGISTERS,
    RETURN_REGISTER,
    STACK_POINTER,
    SYSV_CALLEE_SAVED_REGISTERS,
    SYSV_CALLER_SAVED_REGISTERS,
    SYSV_INTEGER_ARGUMENT_REGISTERS,
)

import pytest

pytestmark = [pytest.mark.s3_fast, pytest.mark.s3_contract]


def test_argument_registers() -> None:
    assert SYSV_INTEGER_ARGUMENT_REGISTERS == ("rdi", "rsi", "rdx", "rcx", "r8", "r9")


def test_return_register() -> None:
    assert RETURN_REGISTER == "rax"


def test_pointers() -> None:
    assert STACK_POINTER == "rsp"
    assert FRAME_POINTER == "rbp"


def test_scratch_and_reserved() -> None:
    assert EMITTER_SCRATCH_REGISTERS == frozenset({"rax", "r10", "r11"})
    assert NON_ALLOCATABLE_REGISTERS == frozenset({"rsp", "rbp"})


def test_deterministic_allocatable_pool() -> None:
    assert INITIAL_ALLOCATABLE_REGISTERS == ("rbx", "r12", "r13", "r14", "r15")


def test_disjoint_invariants() -> None:
    allocatable_set = set(INITIAL_ALLOCATABLE_REGISTERS)

    # rsp and rbp must not be allocatable
    assert STACK_POINTER not in allocatable_set
    assert FRAME_POINTER not in allocatable_set
    assert NON_ALLOCATABLE_REGISTERS.isdisjoint(allocatable_set)

    # rax (return register) must not be allocatable
    assert RETURN_REGISTER not in allocatable_set

    # r10 and r11 (part of emitter scratch) must not be allocatable
    assert "r10" not in allocatable_set
    assert "r11" not in allocatable_set
    assert EMITTER_SCRATCH_REGISTERS.isdisjoint(allocatable_set)

    # Argument registers are caller-saved, and must not be in the initial callee-saved allocatable pool
    for arg_reg in SYSV_INTEGER_ARGUMENT_REGISTERS:
        assert arg_reg not in allocatable_set

    # Allocatable pool must be a subset of callee-saved registers
    assert allocatable_set.issubset(SYSV_CALLEE_SAVED_REGISTERS)

    # rbp is callee-saved, but it is a non-allocatable frame pointer, so it must not be allocatable
    assert FRAME_POINTER in SYSV_CALLEE_SAVED_REGISTERS
    assert FRAME_POINTER not in allocatable_set

    # Caller-saved registers are excluded from the initial allocatable pool
    assert SYSV_CALLER_SAVED_REGISTERS.isdisjoint(allocatable_set)
