# M2.60 Full-Cycle Level-C Checkpoint

## WHY_NOW

M2.51 through M2.59 are now integrated on the development train. The train
needs a deterministic cross-cycle checkpoint before the next milestone group,
while the policy continues to reserve the global T4 suite for M3.00.

## ARCHITECTURAL_DECISION

The historical `level-c` profile remains the exact M2.41-M2.49 checkpoint.
M2.60 adds `level-c-full`, a separate profile that selects exactly the
file-level tests for M2.41 through M2.59, including the M2.50 checkpoint and
all M2.51-M2.59 capability shards. The profile is Level-C, not T4, and keeps
inner platform skips visible in each file's result.

## IMPLEMENTATION_SUMMARY

- Added the deterministic `level-c-full` profile to `tools/s3test.py`.
- Added the M2.41-M2.59 full-cycle shard and M2.60 profile contract tests.
- Preserved the existing M2.41-M2.49 Level-C profile unchanged.
- Added M2.60 scope documentation and impact metadata.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3 tools`: PASS.
- M2.60 contract plus `tests/test_s3test.py`: 29 passed, 0 failed.
- M2.60 T2 at source HEAD
  `37ca8610da56bb40e4805cc8487d93bb46ac8c9b`: 1 selected, 1 passed,
  0 failed, 0 timed out.
- M2.60 T3 shard at the same source HEAD: 1 selected, 1 passed, 0 failed,
  0 timed out.
- Full-cycle Level-C at the same source HEAD: 19 selected, 19 file-level
  PASS, 0 failed, 0 timed out, with 28 inner skips preserved. The skips are
  25 Linux-only M2.43 cases and 3 provider-dependent M2.45 cases.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone validates cross-cycle integration
and bounded orchestration only; no performance claim is made.

## T4_STATUS

Not run. Full T4 remains reserved for M3.00.

## STATUS

M2.60 is complete. The M2.51-M2.60 development train is ready for review and
the next train may begin only after this milestone is merged.
