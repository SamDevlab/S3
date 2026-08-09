"""Contracts for backend sequences with implicit register effects."""

from __future__ import annotations

import inspect

import pytest

from bootstrap.s3.backends.x86_64.emitter import X8664Emitter
from bootstrap.s3.backends.x86_64.registers import (
    EMITTER_SCRATCH_REGISTERS,
    FULL_ALLOCATABLE_REGISTERS,
)
from bootstrap.s3.backends.x86_64.runtime import render_runtime


pytestmark = pytest.mark.s3_contract


IMPLICIT_REGISTER_SEQUENCES = {
    "rep stosb": {
        "implicit_clobbers": frozenset({"rdi", "rcx", "rax"}),
        "policy": "preserved by r10/r11 around metadata initialization when RA is enabled",
    },
    "syscall": {
        "implicit_inputs": frozenset({"rax", "rdi", "rsi", "rdx"}),
        "implicit_clobbers": frozenset({"rcx", "r11"}),
        "policy": "standalone runtime region, outside allocator-managed logical residency",
    },
    "div/idiv": {
        "implicit_inputs": frozenset({"rax", "rdx"}),
        "implicit_clobbers": frozenset({"rax", "rdx"}),
        "policy": "standalone runtime region, outside allocator-managed logical residency",
    },
}


def test_inventory_only_lists_sequences_present_in_backend() -> None:
    emitter_source = inspect.getsource(X8664Emitter)
    runtime_source = render_runtime()

    assert "rep stosb" in emitter_source
    assert "syscall" in runtime_source
    assert "div r10" in runtime_source
    assert "idiv r10" in runtime_source
    assert "rep movsb" not in emitter_source + runtime_source


def test_implicit_clobbers_are_not_unprotected_allocatable_registers() -> None:
    rep = IMPLICIT_REGISTER_SEQUENCES["rep stosb"]
    assert set(rep["implicit_clobbers"]) & set(FULL_ALLOCATABLE_REGISTERS) == {"rdi", "rcx"}
    assert EMITTER_SCRATCH_REGISTERS.isdisjoint({"rdi", "rcx"})


def test_rep_stosb_ra_path_preserves_allocated_argument_registers() -> None:
    source = inspect.getsource(X8664Emitter._initialize_metadata)
    assert '"    mov r10, rdi"' in source
    assert '"    mov r11, rcx"' in source
    assert '"    mov rdi, r10"' in source
    assert '"    mov rcx, r11"' in source


def test_runtime_implicit_sequences_declare_standalone_policy() -> None:
    for name in ("syscall", "div/idiv"):
        assert "standalone runtime region" in IMPLICIT_REGISTER_SEQUENCES[name]["policy"]
