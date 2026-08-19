# M1.91-M2.00 Benchmark Plan

Benchmarks are correctness-first. Every campaign must define an independent
observable contract, an exact source/commit, workload identity, environment,
warmup/repetition protocol, and a result schema before timing begins.

| Milestone | Correctness workload | Timing eligibility |
|---|---|---|
| M1.91 | select order, readiness, cancellation | characterization after proof |
| M1.92 | bounded contention and wake ordering | characterization after proof |
| M1.93 | loopback streaming, framing, backpressure | eligible with pinned fixture |
| M1.94 | trusted and rejected TLS handshakes | provider/environment dependent |
| M1.95 | cold/warm resolver and cache graph | eligible with offline registry |
| M1.96 | signature and trust-policy verdicts | provider-dependent characterization |
| M1.97 | ELF/relocation/link/native output | native AArch64 only |
| M1.98 | equivalent workload across targets | comparable matrix required |
| M1.99 | pinned hot-path before/after counters | promotion only with reproducibility |
| M2.00 | bundle/reproducibility/provenance | release evidence, not a speed claim |

No public services, synthetic timing, unpinned toolchains, or benchmark-specific
compiler branches are acceptable. Structural-only and deferred results must
remain explicit and cannot be promoted to performance evidence.
