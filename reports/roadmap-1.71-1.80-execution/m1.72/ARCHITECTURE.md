# M1.72 - Structured Concurrency And Cancellation V1 Architecture

## MILESTONE

`M1.72 STRUCTURED_CONCURRENCY_AND_CANCELLATION_V1`

## PROBLEM

Async futures need an ownership boundary for child work so a scope cannot
silently outlive its parent or leak a suspended frame.

## PUBLIC_SURFACE

`TaskGroup` owns `TaskHandle` values. A group admits a bounded number of
children, polls them in insertion order, and closes only after every child is
terminal. A handle can be joined once; cancellation is an explicit operation.

## OWNERSHIP_MODEL

The group owns handles and their futures. A child has exactly one parent group
and there is no detached default. Joining consumes the handle's result;
closing a group cancels unfinished children before releasing them.

## RESOURCE_MODEL

`max_children` bounds the group. Cancellation is cooperative and delegates to
the M1.71 frame, which drops initialized slots exactly once. No stack is torn
down asynchronously and no worker thread is created.

## FAILURE_MODEL

Spawn overflow, join twice, child failure, child escape, and close with an
unfinished child are explicit `TaskError` values. A child failure causes the
group to request cancellation of unfinished siblings and is reported without
exception injection.

## LOWERING_MODEL

Task creation and cancellation are ordinary explicit control-flow operations
around M1.71 state machines. A future's frame remains the sole owner of
suspended values.

## DETERMINISM_MODEL

Children are identified by monotonic local IDs and polled by ID order. Group
completion, sibling cancellation, and join results do not depend on host
thread scheduling.

## PLATFORM_MODEL

Hosted, single-threaded orchestration only. Executor and reactor integration
are deferred to M1.73.

## OUT_OF_SCOPE

Detached tasks, work stealing, asynchronous stack tearing, shared ownership,
task migration between OS threads, and public async traits.

## TEST_STRATEGY

Focused tests cover spawn/join, multiple children, nested groups, child and
parent cancellation, cleanup of suspended frames, bounded admission,
idempotent cancellation, and rejection of unfinished scope closure.
