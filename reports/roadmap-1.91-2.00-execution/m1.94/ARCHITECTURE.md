# M1.94 Architecture: TLS Server Boundary

M1.94 adds `AsyncTlsServer`, a bounded server-side session boundary over an
injected provider. The provider owns the cryptographic implementation and
returns explicit `ServerWantRead`, `ServerWantWrite`, `ServerReady`, or
`ServerFailure` outcomes. The async frame owns the pre-handshake connection and
transfers it exactly once into `AsyncTlsServerConnection` on success.

Certificate and private-key identities are mandatory configuration. Connection
and read/write budgets are explicit. There is no disable-verification switch,
custom cryptography, plaintext fallback, or detached handshake task.
