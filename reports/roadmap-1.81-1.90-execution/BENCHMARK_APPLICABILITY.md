# M1.81-M1.90 Benchmark Applicability

This matrix records the executable benchmark campaign published on
`benchmark/m181-m190-executable-campaign-20260819` at
`fbf53a0eb8cf39ed0245438b6b47dfde63658b20`.

No result below is a comparative performance claim without a pinned executable
reference toolchain and an equivalent observable workload. The S3 PR received
additional post-review hardening after these benchmark runs, so characterization
numbers must be rerun before being attributed to the newer S3 source head.

| AREA | S3_CAPABILITY_READY | CORRECTNESS_HARNESS_READY | REFERENCE_TOOLCHAIN_AVAILABLE | PERFORMANCE_TIMING_VALID | STRUCTURAL_ONLY | DEFERRED_REASON |
|---|---|---|---|---|---|---|
| async task creation/completion | YES | YES | NO | CHARACTERIZATION_ONLY | NO | No pinned executable reference runtime is installed locally. |
| await-chain depth | YES | YES | NO | CHARACTERIZATION_ONLY | NO | No pinned executable reference runtime is installed locally. |
| bounded channels | YES | YES | NO | CHARACTERIZATION_ONLY | NO | Correctness covers capacities 1/8/64; no pinned comparable reference runtime is installed locally. |
| multithread executor | YES | YES | NO | CHARACTERIZATION_ONLY | NO | No pinned executable reference executor is installed locally. |
| process I/O | YES | YES | NO | CHARACTERIZATION_ONLY | NO | Local bounded child contract is executable; no comparable reference toolchain is pinned. |
| loopback HTTP | YES | YES | NO | CHARACTERIZATION_ONLY | NO | Local TCP loopback contract is executable; no comparable reference toolchain is pinned. |
| loopback TLS | PARTIAL | PARTIAL | NO | NO | YES | Secure policy is checked, but no pinned local certificate fixture/handshake campaign is present. |
| registry/cache | YES | YES | NO | CHARACTERIZATION_ONLY | NO | The fixture transport proves digest-before-cache behavior, not comparative registry performance. |
| package signature verification | PARTIAL | DEFERRED | NO | NO | NO | The production Ed25519 provider `cryptography` is unavailable on this host. |
| Linux AArch64 structure/code quality | YES | YES | PINNED_REFERENCE_ONLY | NO | YES | Windows host cannot assemble/link/execute Linux AArch64 natively. |
| macOS ARM64 structure/code quality | YES | YES | PINNED_REFERENCE_ONLY | NO | YES | Windows host cannot assemble/link/execute macOS ARM64 natively. |
| release bundle reproducibility | YES | YES | NO | CHARACTERIZATION_ONLY | NO | Repeated local bundle hashes are determinism evidence, not external performance evidence. |

## Executed benchmark gates

- M1.81-M1.90 campaign correctness: `PASS=10`, `FAIL=0`, `DEFERRED=1`.
- Channels correctness covers capacities `1`, `8`, and `64` with FIFO/count/checksum/close invariants.
- M1.81-M1.90 smoke: `PASS_CHARACTERIZATION_ONLY`; no comparative result is promoted.
- Existing JSMN `--verify-only`: differential correctness PASS with explicit `S3_REPO`.
- Existing JSMN `--smoke`: exit `0`; six fixtures completed, native timings unavailable on Windows.
- No JSMN full benchmark and no M1.81-M1.90 full comparative benchmark was run.

## Post-review source hardening note

The S3 publication branch later received correctness hardening for typed
AAPCS64 floating-point value classes, fail-closed release-bundle verification,
HTTP global deadlines/ASCII request boundaries, canonical registry origins,
and native AArch64 evidence binding. Those changes require focused benchmark
correctness/smoke reruns before the benchmark report can certify the newer S3
head. The existing benchmark evidence remains historical and is not rewritten.

The historical S3 T4 also remains unchanged. This report does not promote a
performance result, publish an artifact, or authorize a release.
