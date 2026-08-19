# M1.73 - Executor, Reactor And Timers V1 Architecture

## MILESTONE

`M1.73 ASYNC_EXECUTOR_REACTOR_AND_TIMERS_V1`

## PROBLEM

M1.71 futures and M1.72 task groups need bounded scheduling and readiness
signals without introducing thread migration or platform-specific public
semantics.

## PUBLIC_SURFACE

`AsyncExecutor` owns futures, a ready queue, `TimerHandle`, and a
platform-neutral `ReactorRegistration`. `FakeClock` provides deterministic
monotonic time for tests. `DeterministicReactor` is a hosted readiness oracle;
OS poller adapters are intentionally private future work.

## OWNERSHIP_MODEL

The executor owns every admitted task and registration. A task ID is not an
owned future clone. Wake requests are coalesced per task and discarded after a
terminal state. Closing the executor cancels unfinished futures and releases
timers/registrations.

## RESOURCE_MODEL

Limits cover tasks, queued wakeups, timers, and I/O registrations. Queues are
bounded and `run_until_idle(max_steps=...)` has a finite execution budget.

## FAILURE_MODEL

Admission overflow, duplicate registration, invalid timer deadlines,
cancelled timers, unknown wake IDs, and executor closure are explicit
`ExecutorError` values. There is no busy-spin: an empty ready queue returns an
idle report.

## LOWERING_MODEL

The executor only drives M1.71 poll transitions. Futures explicitly arrange
their next wake through a task ID, timer, or reactor registration.

## DETERMINISM_MODEL

Ready IDs, timer deadlines/IDs, and reactor keys are processed in stable order.
The clock is monotonic and injectable. Wakeup coalescing prevents schedule
history from changing observable results.

## PLATFORM_MODEL

Single-threaded cooperative execution. Reactor semantics are portable; epoll,
kqueue, IOCP, and io_uring are not exposed or required by V1.

## OUT_OF_SCOPE

Work stealing, multi-thread executors, blocking I/O in the executor loop,
wall-clock correctness, and OS-specific public APIs.

## TEST_STRATEGY

Focused tests cover run-to-completion, fair ready progress, wake coalescing,
timer ordering/cancellation, reactor readiness, all resource limits, and
shutdown cleanup using a fake monotonic clock.
