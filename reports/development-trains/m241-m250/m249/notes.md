# M2.49 Cross-Target Execution Evidence Harness

## WHY_NOW

S3 has structural backends and target-specific integration tests for Linux
x86-64, Linux AArch64, and macOS ARM64. Those artifacts are useful evidence,
but structural output, emulation, and native execution must remain separate
claims.

## ARCHITECTURAL_DECISION

The cross-target harness classifies each target independently as `NATIVE`,
`EMULATED`, `STRUCTURAL_ONLY`, or `DEFERRED`. `NATIVE` requires a matching
target host, passing correctness, and passing structural evidence. Emulation is
reported as `EMULATED`. Structural artifacts without execution are reported as
`STRUCTURAL_ONLY` and can never become native PASS. Missing targets are
materialized as `DEFERRED` entries so an incomplete matrix is visible.

## IMPLEMENTATION_SUMMARY

- Added typed target and evidence classifications for Linux x86-64, Linux
  AArch64, and macOS ARM64.
- Added deterministic aggregation, duplicate-target rejection, and explicit
  missing-target records.
- Added regressions proving native host matching, emulation separation,
  structural-only handling, failure deferral, deterministic ordering, and
  duplicate/unknown rejection.
- Added cross-target evidence documentation and impact/shard metadata.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- Focused cross-target matrix: 50 selected, 25 passed, 25 skipped, 0 failed,
  0 timed out. The 25 skips were the existing Linux x86-64-only conformance
  cases on Windows.
- M2.49 T2 at source HEAD
  `b47598475a9f1b869a5b0087d6e50a1b510ec045`: 1 selected, 1 passed,
  0 failed, 0 timed out.
- M2.49 T3 shard at the same source HEAD: 1 selected, 1 passed, 0 failed,
  0 timed out.
- `git diff --check`: PASS.

## NATIVE_EVIDENCE_SCOPE

No remote or cross-target native execution was performed by this milestone.
The implementation proves only classification and reporting policy. The
current Windows host therefore provides no new Linux AArch64 or macOS ARM64
native evidence.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

Actual native evidence still requires the corresponding target host and
toolchain. This harness deliberately does not synthesize it from assembly
text, emulation, or host-only structural validation.
