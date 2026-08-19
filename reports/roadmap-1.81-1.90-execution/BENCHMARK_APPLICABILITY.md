# M1.81-M1.90 Benchmark Applicability

This matrix records the local correction-campaign state at S3 commit
`25b8e53231917b4c0b4f4b676f8ea71b9a2802e9`. The benchmark worktree is
`S3-Benchmarks-m181-m190-executable-20260819` at its private local branch.
No result below is a comparative performance claim without a pinned reference
toolchain and an equivalent observable workload.

| AREA | S3_CAPABILITY_READY | CORRECTNESS_HARNESS_READY | REFERENCE_TOOLCHAIN_AVAILABLE | PERFORMANCE_TIMING_VALID | STRUCTURAL_ONLY | DEFERRED_REASON |
|---|---|---|---|---|---|---|
| async task creation/completion | YES | YES | NO | CHARACTERIZATION_ONLY | NO | No pinned executable reference runtime is installed locally. |
| await-chain depth | YES | YES | NO | CHARACTERIZATION_ONLY | NO | No pinned executable reference runtime is installed locally. |
| bounded channels | YES | NO | NO | NO | NO | Campaign-specific channel oracle has not been promoted yet. |
| multithread executor | YES | YES | NO | CHARACTERIZATION_ONLY | NO | No pinned executable reference executor is installed locally. |
| process I/O | YES | YES | NO | CHARACTERIZATION_ONLY | NO | Local bounded child contract is executable; no comparable reference toolchain is pinned. |
| loopback HTTP | YES | YES | NO | CHARACTERIZATION_ONLY | NO | Local TCP loopback contract is executable; no comparable reference toolchain is pinned. |
| loopback TLS | PARTIAL | PARTIAL | NO | NO | YES | Secure policy is checked, but no pinned local certificate fixture/handshake campaign is present. |
| registry/cache | YES | YES | NO | CHARACTERIZATION_ONLY | NO | The fixture transport proves digest-before-cache behavior, not comparative registry performance. |
| package signature verification | PARTIAL | DEFERRED | NO | NO | NO | The production Ed25519 provider `cryptography` is unavailable on this host. |
| process I/O bounded capture | YES | YES | NO | CHARACTERIZATION_ONLY | NO | Same local-process characterization as process I/O; no cross-toolchain comparison. |
| Linux AArch64 structure/code quality | YES | YES | PINNED_REFERENCE_ONLY | NO | YES | Windows host cannot assemble/link/execute Linux AArch64 natively. |
| macOS ARM64 structure/code quality | YES | YES | PINNED_REFERENCE_ONLY | NO | YES | Windows host cannot assemble/link/execute macOS ARM64 natively. |
| release bundle reproducibility | YES | YES | NO | CHARACTERIZATION_ONLY | NO | Repeated local bundle hashes are valid determinism evidence, not external performance evidence. |

## Executed gates

- M1.81-M1.90 campaign correctness: `PASS=9`, `FAIL=0`, `DEFERRED=1`.
- M1.81-M1.90 smoke: `PASS_CHARACTERIZATION_ONLY`; seven bounded checks timed
  with `time.perf_counter_ns`, one warmup, one repetition.
- Existing JSMN `--verify-only`: differential correctness PASS with only
  `S3_REPO` set explicitly.
- Existing JSMN `--smoke`: exit `0`; six fixtures completed, native timings
  unavailable on Windows.
- No JSMN full benchmark was run.

The historical S3 T4 remains unchanged. This report does not promote a
benchmark result, publish an artifact, or authorize a remote write.

