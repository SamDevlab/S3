# M2.37 Async and Network Production Soak

`M2_37_ASYNC_NETWORK_SOAK=PARTIAL`

The bounded executor now exposes deterministic resource snapshots and explicit
reaping of terminal tasks/timers. A 32-cycle workload completed with zero live
tasks, timers, queued wakeups, or ready items after each reap. Existing async,
thread, channel, HTTP/1, HTTP/2, and TLS focused contracts pass. This is a
bounded soak, not an indefinite production-duration claim; native Linux and
vetted TLS soak remain environment deferred.
