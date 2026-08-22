"""Contracts for the internal deterministic native policy model."""

from __future__ import annotations

import inspect

import pytest

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64 import BASELINE_NATIVE_POLICY, X8664Backend, policy_with
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.backends.x86_64.residence import analyze_cross_block_residence
from bootstrap.s3.backends.x86_64.registers import (
    CALLER_SAVED_ALLOCATABLE_REGISTERS,
    CALLEE_SAVED_ALLOCATABLE_REGISTERS,
    FULL_ALLOCATABLE_REGISTERS,
)


pytestmark = [pytest.mark.s3_fast, pytest.mark.s3_contract]


def _program():
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
            .register r2, trit
        .label entry
            TCONST r0, 10
            TCONST r1, 1
            TCONST r2, 1
            TBR3 r2, call, exit, alt
        .label call
            TCALL r1, helper, r0
            TADD r1, r0, r1
            TRET r1
        .label exit
            TRET r0
        .label alt
            TRET r0
        .end
        """
    )


def test_baseline_policy_is_complete_and_abi_safe() -> None:
    BASELINE_NATIVE_POLICY.validate()
    assert BASELINE_NATIVE_POLICY.register_order == (
        *CALLER_SAVED_ALLOCATABLE_REGISTERS,
        *CALLEE_SAVED_ALLOCATABLE_REGISTERS,
    )
    assert BASELINE_NATIVE_POLICY.call_register_order == (
        *CALLEE_SAVED_ALLOCATABLE_REGISTERS,
        *CALLER_SAVED_ALLOCATABLE_REGISTERS,
    )
    assert set(BASELINE_NATIVE_POLICY.register_order) == set(FULL_ALLOCATABLE_REGISTERS)


def test_explicit_baseline_output_is_byte_identical() -> None:
    program = _program()
    implicit = X8664Backend().generate(program)
    explicit = X8664Backend(native_policy=BASELINE_NATIVE_POLICY).generate(program)
    assert explicit == implicit


def test_register_order_policy_is_deterministic_and_abi_safe() -> None:
    policy = policy_with(
        name="caller_first",
        register_order=(
            *CALLER_SAVED_ALLOCATABLE_REGISTERS,
            *CALLEE_SAVED_ALLOCATABLE_REGISTERS,
        ),
        call_register_order=(
            *CALLER_SAVED_ALLOCATABLE_REGISTERS,
            *CALLEE_SAVED_ALLOCATABLE_REGISTERS,
        ),
    )
    function = _program().functions[1]
    first = analyze_allocation(function, policy)
    second = analyze_allocation(function, policy)
    assert first.allocations == second.allocations
    assert set(color for color in first.allocations.values() if color) <= set(FULL_ALLOCATABLE_REGISTERS)


def test_selective_call_policy_does_not_use_whole_function_fallback() -> None:
    policy = policy_with(
        name="selective_call_residence",
        call_residence="selective_live_across_call",
    )
    function = _program().functions[1]
    plan = analyze_cross_block_residence(function, policy)
    assert plan.allocations
    assert any(color is not None for color in plan.allocations.values())


def test_invalid_register_permutation_fails_closed() -> None:
    with pytest.raises(ValueError):
        policy_with(name="invalid_order", register_order=("rax",))


def test_experimental_policy_is_keyword_only_on_backend_boundary() -> None:
    parameter = inspect.signature(X8664Backend).parameters["native_policy"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
