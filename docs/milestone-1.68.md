# Milestone 1.68 - TLS Client Provider V1

## Architecture status

M1.68 adds an owned blocking `TlsClient` backed by Python's vetted system
OpenSSL provider. Its default context requires certificate validation, enables
hostname validation, and limits negotiation to TLS 1.2 through TLS 1.3. The
client exposes bounded read/write and idempotent close operations with typed
`Result` errors. Connection timeout configuration is bounded to 60 seconds.

No cryptographic primitive, certificate parser, insecure default, secret
logging, or private-key fixture was added. Server TLS and custom stores remain
out of scope. An explicitly supplied CA file is passed to the provider and is
never copied into diagnostics.

## Tests and environment

Tests validate provider configuration, hostname failure mapping, bounded I/O,
cleanup, connection failure, and provider presence with injected local doubles.
No public internet is required. A real certificate fixture is deliberately not
committed; end-to-end certificate-chain execution remains dependent on a
locally supplied trusted fixture/provider environment.

## Implementation status, public surface, and dependency

COMPLETE for the hosted verified TLS client provider. Trusted certificate-chain
execution is `DEFERRED_BY_ENVIRONMENT`; M1.69 consumes the explicit Result and
resource-close model for thread results and lifecycle errors.
