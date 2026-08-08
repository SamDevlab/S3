"""Physical register definitions and System V AMD64 ABI contract."""

from __future__ import annotations

# Physical registers
STACK_POINTER = "rsp"
FRAME_POINTER = "rbp"
RETURN_REGISTER = "rax"

# System V AMD64 ABI Integer Argument Registers
SYSV_INTEGER_ARGUMENT_REGISTERS = ("rdi", "rsi", "rdx", "rcx", "r8", "r9")

# System V AMD64 ABI Caller-Saved (volatile) registers
SYSV_CALLER_SAVED_REGISTERS = frozenset(
    {"rax", "rcx", "rdx", "rsi", "rdi", "r8", "r9", "r10", "r11"}
)

# System V AMD64 ABI Callee-Saved (non-volatile) registers
SYSV_CALLEE_SAVED_REGISTERS = frozenset(
    {"rbx", "rbp", "r12", "r13", "r14", "r15"}
)

# Scratch registers reserved for the emitter
EMITTER_SCRATCH_REGISTERS = frozenset({"rax", "r10", "r11"})

# Non-allocatable registers (reserved for stack and frame pointers)
NON_ALLOCATABLE_REGISTERS = frozenset({STACK_POINTER, FRAME_POINTER})

# Initial pool of allocatable registers for the future register allocator (1.21)
INITIAL_ALLOCATABLE_REGISTERS = ("rbx", "r12", "r13", "r14", "r15")


def _validate_invariants() -> None:
    # 1. rsp não allocatable
    assert STACK_POINTER not in INITIAL_ALLOCATABLE_REGISTERS
    # 2. rbp não allocatable
    assert FRAME_POINTER not in INITIAL_ALLOCATABLE_REGISTERS
    # 3. rax não initial-allocatable
    assert RETURN_REGISTER not in INITIAL_ALLOCATABLE_REGISTERS
    # 4. r10/r11 não initial-allocatable
    assert "r10" not in INITIAL_ALLOCATABLE_REGISTERS
    assert "r11" not in INITIAL_ALLOCATABLE_REGISTERS
    # 5. argument registers não initial-allocatable
    for arg_reg in SYSV_INTEGER_ARGUMENT_REGISTERS:
        assert arg_reg not in INITIAL_ALLOCATABLE_REGISTERS
    # 6. INITIAL_ALLOCATABLE_REGISTERS ⊆ SYSV_CALLEE_SAVED_REGISTERS
    alloc_set = set(INITIAL_ALLOCATABLE_REGISTERS)
    assert alloc_set.issubset(SYSV_CALLEE_SAVED_REGISTERS)
    # 7. rbp é removido do conjunto allocatable apesar de ser callee-saved
    assert FRAME_POINTER not in INITIAL_ALLOCATABLE_REGISTERS
    # 8. nenhum registrador está simultaneamente initial-allocatable e scratch/reserved
    reserved_scratch = EMITTER_SCRATCH_REGISTERS | NON_ALLOCATABLE_REGISTERS
    assert alloc_set.isdisjoint(reserved_scratch)
    # 9. ordem de INITIAL_ALLOCATABLE_REGISTERS é determinística
    assert INITIAL_ALLOCATABLE_REGISTERS == ("rbx", "r12", "r13", "r14", "r15")


_validate_invariants()
