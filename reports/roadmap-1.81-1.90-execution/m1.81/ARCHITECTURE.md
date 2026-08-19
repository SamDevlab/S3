# M1.81 Native Async IR and Resumable Frames

## Problem

M1.71 records async suspension as a deterministic frontend plan and hosted
future state machine, but the compiler IR does not yet carry the frame,
program-counter, or resume edges. M1.81 graduates that plan into a distinct,
verifiable IR representation without making direct-call execution normative.

## Public surface

`AsyncIRProgram`, `AsyncIRFunction`, `AsyncIRFrame`, `AsyncIRSlot`,
`AsyncIROp`, `AsyncIRBlock`, and `execute_async_ir` are hosted compiler/runtime
contracts. `lower_async_ir` converts an existing `AsyncStateMachinePlan` into
the deterministic native async IR model.

## Ownership and borrow model

Each frame slot has one owner and an explicit initialized/moved state. A slot
that is moved is excluded from later cleanup. Ordinary lexical borrows remain
forbidden across suspension; M1.81 does not add frame-self borrow syntax.

## Resource and failure model

Frame slots, suspension states, blocks, and terminal transitions are bounded.
Invalid resume, poll after terminal consumption, uninitialized access,
use-after-move, missing cleanup, and invalid suspension targets fail closed
through verifier errors. Cancellation walks initialized, non-moved slots once.

## Lowering model

Every async function receives a frame descriptor with a deterministic state
table. Each await becomes a `SUSPEND` edge from the running block to a named
suspended block and a `RESUME` edge to the next running block. Completion,
failure, and cancellation are explicit terminal blocks. The representation is
IR-owned; the old hosted direct-call plan remains compatibility metadata only.

## Runtime model

The hosted executor interprets the async IR one operation at a time. A frame
can be polled once per step, suspended, resumed, completed, failed, or
cancelled. Terminal consumption is one-shot and cleanup is deterministic.

## Determinism and platform model

Function order, frame slot order, state numbering, block names, and serialized
operations are stable. M1.81 execution is hosted. Native certification remains
deferred unless the available target/toolchain can execute this IR directly.

## Security and out of scope

No public raw pointers, GC, general reference counting, JIT, implicit sharing,
or exception-driven language control flow are introduced. M1.82 futures,
multithread transfer, and platform-native async lowering are out of scope.

## Test strategy

Focused tests cover zero/one/multiple awaits, nested plans, frame ownership,
move/drop behavior, cancellation at each state, terminal errors, invalid
resume and deterministic layout/serialization. Existing M1.71 focused tests
remain the regression proof.
