# M1.68 Architecture Preflight

## Existing authority

M1.67 supplies blocking TCP and DNS primitives. The repository has no custom
TLS or cryptographic implementation, so TLS must remain a provider adapter.

## Selected implementation

Use Python `ssl.create_default_context` with `CERT_REQUIRED`, hostname checking,
and TLS 1.2/1.3 bounds. Connect, wrap, read, write, and close are blocking and
bounded. All expected provider failures map to typed `TlsError` values. The
connection owns the wrapped socket and closes it idempotently.

## Boundary

No insecure mode is exposed by the normal API. Tests inject only a local fake
socket/context to verify configuration; no private keys or certificates enter
the repository. A real-chain fixture is an environment certification concern,
not a reason to weaken verification.
