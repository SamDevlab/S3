# M1.98 Architecture: Cross-Platform Backend Parity

`build_backend_parity_matrix` requires the exact registered Linux x86-64,
Linux AArch64, and macOS ARM64 targets. Each emitted assembly identity is
checked against its target-specific ABI/symbol markers, and a missing target or
provider fails rather than falling back to another backend. Source identity and
the hosted semantic result are shared across the matrix; target assembly
digests and instruction counts remain distinct evidence.

Native execution status remains explicitly deferred until target-specific
toolchain evidence is supplied. Structural parity is not native certification.
