# M1.50 Architecture Preflight

Status: `CLOSED_FOR_BOUNDED_COMPONENT`; portable execution remains dependent
on M1.49.

The single selected component is the existing Assembly renderer subset, not a
diagnostic formatter, parser, verifier, or compiler. Its Python reference is
the current renderer/reference harness and its existing candidate fixture
corpus. Input is the bounded structured renderer fixture; output is exact
Assembly text plus the existing structured failure form. Serialization is the
already versioned deterministic fixture format.

The component may use only the bounded `core`, text, and collection contracts;
no filesystem, network, dynamic host service, Python object, or hidden global
state is allowed. The build path is M1.45 and the test path is M1.46. The
differential oracle remains Python byte-for-byte output. Promotion requires
clean-lockfile build, hosted/native parity, O0/O1 parity, deterministic output,
and explicit candidate status; it never becomes the default compiler in M1.50.

Memory budget and exact portable artifact gate remain delegated to M1.49, so
M1.50 must not claim complete self-hosting.
