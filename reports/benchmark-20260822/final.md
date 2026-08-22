# Benchmark Evidence 2026-08-22

## Provenance

- Tested S3 source: `6604b9d07c607579df9c5c0759d8f2a708ba72d1`
- Benchmark repository: `fd5f5b48f36a1c4805bfbc69590f220e70d65951`
- Benchmark branch: `benchmark/m235-mega-hardening-linux-20260822`
- Latest validated harness lineage: PR #9
- Raw transcript: `reports/benchmark-20260822/raw/m199-characterization-raw.txt`
- Raw transcript SHA-256: `b93ddf26b0d3f42fd352025835ddf73f24550672b581f1bbc870437395813c8a`

The harness resolved both local Git HEADs and failed closed on mismatch.

## Protocol

This repository exposes M1.99 JSMN and self-move characterization, not a
P1-P18 corpus. No unavailable workload was synthesized. The executed M1.99
protocol used the same parsed `AssemblyProgram` and workload: OFF is the
original program, ON is `eliminate_redundant_noop_moves(original)`, and timing
is hosted Emulator execution. Native x86 generation is only a supplementary
structural probe; no native speedup claim is made.

## Result

- Correctness: `PASS`
- Timing class: `CHARACTERIZATION_ONLY`
- Native speedup claim: `NO`
- Native comparative validity: `false`
- Native structural probe: `PASS`
- Benchmark exit: `0`
- M1.99 baseline derived by harness: `2a5f7bdb0e0dfd03fcae5249cb76bff118a642b6`

The numbers in the raw transcript are hosted-emulator characterization only and
must not be read as native performance evidence.
