# M1.71 - Async/Await Core V1 Architecture

## MILESTONE

`M1.71 ASYNC_AWAIT_CORE_V1`

## PROBLEM

S3 needs an explicit suspension model that can preserve owned values without
borrowing ordinary lexical storage across a suspension point.

## PUBLIC_SURFACE

The hosted V1 surface is `AsyncFuture`, `AsyncFrame`, `Poll`, `AwaitPoint`,
and `OwnedSlot`. A future is move-only, can be polled until one terminal
outcome, and exposes its state-machine state for deterministic inspection.

## OWNERSHIP_MODEL

Owned values are moved into frame slots. A slot is consumed at most once and
is dropped at most once. Ordinary lexical borrows are represented by an
explicit `BorrowToken`; the frame rejects a live token at suspension. No
reference counting, GC, raw pointer, or implicit future clone is introduced.

## RESOURCE_MODEL

Frames are bounded by a caller-supplied slot count and are released on
completion, failure, cancellation, or abandonment. Suspension points are
finite and explicit; no hidden worker or unbounded queue is created by this
milestone.

## FAILURE_MODEL

Invalid poll order, double consumption, live borrow across suspension, and
slot overflow are explicit `AsyncError` values. User callbacks are converted
to an explicit failure outcome at the frame boundary; exceptions are not the
language-level async propagation mechanism.

## LOWERING_MODEL

The normative model is a compiler-generated state machine with `CREATED`,
`RUNNING`, `SUSPENDED`, `COMPLETED`, `FAILED`, and `CANCELLED` states. The
hosted implementation accepts deterministic transition callbacks so later
parser/IR lowering can target the same contract without making Python
generators the semantic model.

## DETERMINISM_MODEL

Each poll performs at most one declared transition. State names, transition
order, drop order, and terminal consumption are stable. No wall-clock or
thread scheduling is used.

## PLATFORM_MODEL

This milestone is hosted and platform-neutral. Native target certification is
not claimed here; later ARM64 milestones provide structural target contracts.

## OUT_OF_SCOPE

Executors, timers, reactors, networking, TLS, channels, select, detached
tasks, async traits, generators, and S3 source syntax changes are deferred to
their dedicated milestones.

## TEST_STRATEGY

Focused tests cover state transitions, owned-slot survival and drop, borrow
rejection, cancellation/abandonment, nested future polling, explicit failure,
and deterministic transition traces. T0/T1/T2 are limited to this module;
T3 is not required because no existing subsystem is changed.
