# Stage1 Bootstrap ABI

This is the deterministic Linux x86-64 ABI contract for the Stage1 bootstrap
emitter. It follows the System V AMD64 calling convention for integer and
pointer-shaped values. It is a code-generation contract, not evidence that
the current bounded IR can yet express every listed operation.

## Registers

- Integer and pointer return values use `rax` (the low 32-bit form is `eax`
  when the value is emitted as a 32-bit tryte-compatible result).
- Integer and pointer arguments use `rdi`, `rsi`, `rdx`, `rcx`, `r8`, and
  `r9`, in that order.
- Additional integer or pointer arguments are passed in the caller-owned
  stack argument area at the ABI-defined position.
- Callee-saved registers are `rbx`, `rbp`, and `r12` through `r15`.
- Caller-saved registers are `rax`, `rcx`, `rdx`, `rsi`, `rdi`, `r8` through
  `r11`.

## Stack and calls

- The stack is 16-byte aligned at each call boundary as required by SysV
  AMD64. A function prologue accounts for the return-address effect before
  issuing nested calls.
- The caller owns outgoing argument space and may freely use caller-saved
  registers across a call only after preserving values that remain live.
- A foreign declaration contributes a symbol reference only. It does not
  receive a synthesized body from the emitter.

## Deterministic frame layout

- The future stack-first emitter assigns frame slots in stable IR order:
  parameters first, then locals, then intermediate value temporaries.
- Each slot has a fixed 8-byte width in the bootstrap implementation contract;
  narrow S3 values are sign-extended or truncated at their explicitly typed
  operation boundary.
- Slot offsets are negative offsets from `rbp` after the canonical prologue.
  The exact frame size is rounded up to preserve the 16-byte call alignment.
- No pointer addresses, hash iteration order, timestamps, or register
  allocation decisions may influence the layout.

## Current qualification boundary

The current verified IR preserves function identity, aggregate parameter/local
counts, bounded call metadata, packed value records, and bounded CFG target
lanes. It does not yet preserve the per-instruction typed definition/use and
result relationships required to map parameters, locals, arithmetic,
comparisons, calls, and branches to these ABI locations. The general emitter
therefore remains fail-closed at `GENERAL_EMITTER_CAPABILITY_GAP`; this
document does not promote unsupported shapes.
