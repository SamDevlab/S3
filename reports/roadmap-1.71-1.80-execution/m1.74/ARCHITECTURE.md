# M1.74 - Async Networking V1 Architecture

## MILESTONE

`M1.74 ASYNC_NETWORKING_V1`

## PROBLEM

Existing M1.67/M1.48 network providers are blocking. Async networking needs
the same owned socket semantics while allowing readiness-driven operations to
remain pending without blocking the M1.73 executor.

## PUBLIC_SURFACE

`AsyncNetworkService` creates futures for TCP connect/accept/read/write, UDP
send/receive, and DNS resolution. An injected `AsyncNetworkProvider` returns
`PendingOperation`, `PendingResource`, a value, or an explicit provider
failure. `AsyncNetworkHandle` is an owned resource identity.

## OWNERSHIP_MODEL

Socket handles are registered exactly once and closed idempotently. A resource
obtained while an operation is pending is first moved into the async frame;
cancellation/drop closes it. A successful handle transfer consumes the frame
slot. Read/write buffers are bytes owned by the operation, not long-lived
lexical borrows.

## RESOURCE_MODEL

The service has a bounded handle limit and the provider owns the readiness
mechanism. Partial connect/accept resources are closed on every failure path.

## FAILURE_MODEL

Invalid arguments, closed handles, provider failure, timeout, peer EOF, and
resource limits are `AsyncNetworkError` values. An operation cannot complete
twice because it is represented by a consumed M1.71 future.

## LOWERING_MODEL

Each network call is a future whose pending transition is resumed by the
executor after a reactor signal or timer. No blocking call is required by the
async contract; a blocking provider is not a valid async provider.

## DETERMINISM_MODEL

Fixtures return stable operation outcomes and the service sorts DNS results by
the existing numeric address encoding. Handle IDs are monotonic.

## PLATFORM_MODEL

The public contract is platform-neutral. Loopback and OS selector adapters
may be added without changing ownership semantics; public internet is never a
test dependency.

## OUT_OF_SCOPE

TLS handshake, channels/select, remote DNS/TCP certification, and blocking
fallbacks hidden behind an async name.

## TEST_STRATEGY

Focused local-provider tests cover connect/accept, partial read/write, UDP,
DNS, timeout/pending, cancellation, peer close, and handle cleanup.
