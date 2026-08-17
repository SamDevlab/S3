# M1.48 Architecture Preflight

Status: `CLOSED_WITH_MINIMAL_PROFILE`.

The first network profile is TCP stream networking only, with IPv4 and IPv6
represented by one normalized address record. DNS is not part of the source
contract; callers provide numeric addresses. Operations are blocking with an
integer millisecond timeout. There is no async syntax, thread model, UDP, TLS,
or unrestricted remote test.

The API is capability-scoped: connect, listen, and accept produce opaque
stream/listener handles; read and write are bounded and may be partial. Zero
bytes at EOF is distinct from timeout and error. Close is idempotent at the
provider boundary but use after close is a deterministic S3 resource error.
The S3 owner controls lifetime and cleanup.

The hosted fake provider must emit the same ordered operation/error trace as
the Linux loopback provider for the same corpus. Resource limits cover open
handles, bytes per operation, and total operations. The roadmap is not
reordered.
