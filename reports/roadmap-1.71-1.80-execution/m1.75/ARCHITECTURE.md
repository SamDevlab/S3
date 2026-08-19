# M1.75 - Async TLS Client V1 Architecture

## MILESTONE

`M1.75 ASYNC_TLS_CLIENT_V1`

## PROBLEM

TLS must participate in the async reactor without blocking the executor or
weakening the secure defaults already established by M1.68.

## PUBLIC_SURFACE

`AsyncTlsConfig`, `AsyncTlsService`, and `AsyncTlsClient` expose a provider
neutral handshake plus bounded read/write/close operations. Provider progress
is represented by `WantRead`, `WantWrite`, `Ready`, or `Failure` values.

## OWNERSHIP_MODEL

The underlying connection is moved into the TLS future frame while a handshake
is pending. Failure/cancellation drops it exactly once; successful handshake
transfers it to the client. Client close is idempotent and owns provider
cleanup.

## RESOURCE_MODEL

Read/write sizes and TLS configuration are bounded. No blocking retry loop is
allowed inside a handshake poll.

## FAILURE_MODEL

Certificate validation, hostname mismatch, timeout, provider I/O, and closed
client are explicit `AsyncTlsError` values. Certificate and hostname
validation cannot be disabled through the V1 configuration.

## LOWERING_MODEL

Handshake WANT_READ/WANT_WRITE transitions become ordinary pending futures
awakened by M1.73 reactor readiness. There is no exception injection or busy
loop.

## DETERMINISM_MODEL

Provider outcomes are consumed one at a time. Configuration and operation
limits are validated before provider calls.

## PLATFORM_MODEL

The existing vetted TLS provider remains authoritative for real sockets. This
layer is portable and can be backed by `ssl.MemoryBIO` or an OS TLS provider;
trusted external-chain execution may remain an environment deferment.

## OUT_OF_SCOPE

Custom cryptography, insecure fallback, global verification disable, server
TLS, certificate store management, and public-internet tests.

## TEST_STRATEGY

Local provider tests cover WANT transitions, trusted handshake, hostname and
certificate rejection, timeout/failure, cancellation cleanup, bounded I/O,
and close behavior.
