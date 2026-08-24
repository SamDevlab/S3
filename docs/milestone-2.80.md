# Milestone 2.80: Semantic Self-Hosting Checkpoint

M2.80 closes the M2.71-M2.80 semantic train with a reproducible Level-C
profile over M2.71 through M2.79.

## Checkpoint

`python tools/s3test.py level-c-semantic --format json --timeout 180`
selects exactly the nine semantic milestone files in order. The profile is a
Level-C checkpoint and does not select global T4.

The bounded semantic candidate is certified as available for explicit canary
use. The Python reference remains the default execution path. The checkpoint
does not promote or replace production semantic analysis.

## Evidence Contract

- Level-C profile: `level-c-semantic`.
- Checkpoint contract: `tests/test_m280_semantic_self_hosting_checkpoint.py`.
- Profile coverage: M2.71 through M2.79, nine files.
- Candidate state: `S3_SEMANTIC_SELF_HOSTING_CANDIDATE=YES`.
- Default state: `PYTHON_REFERENCE_DEFAULT=YES`.
- Candidate selection remains explicit opt-in with visible fail-closed
  fallback.
- No benchmark, native, performance, or global T4 claim is made.

## Non-claims

M2.80 is not full compiler self-hosting. It does not claim Stage 1/2/3
bootstrap, native compiler execution, default-path promotion, performance
improvement or Docker/OCI integration.
