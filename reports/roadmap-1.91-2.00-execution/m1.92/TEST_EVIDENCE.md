# M1.92 Test Evidence

Focused tests cover FIFO mutex promotion, double unlock rejection, waiter
overflow, cancellation, manual-event broadcast order, auto-reset wake order,
and event overflow. The M1.92 focused gate is recorded by
`tests/test_m192_async_sync.py`.

No benchmark, native claim, merge, tag, release, or remote write is part of
this checkpoint.
