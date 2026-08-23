# M2.70 Frontend Self-Hosting Level-C Checkpoint

## WHY_NOW

M2.61-M2.69 established the bounded frontend candidate chain and its explicit
canary boundary. M2.70 certifies that chain as a deterministic Level-C train
checkpoint.

## ARCHITECTURAL_DECISION

The self-hosted frontend candidate is available for explicit canary use, but
the Python reference remains the default. This checkpoint does not promote the
candidate, alter production selection, or introduce native or performance
claims.

## IMPLEMENTATION_SUMMARY

- Added the `level-c-frontend` profile for M2.61-M2.69.
- Added deterministic ordered shard metadata and a non-T4 checkpoint contract.
- Preserved the historical `level-c` and `level-c-full` profiles unchanged.

## TEST_EVIDENCE

- Final tested source head: `2ec6edca679a64dd923ff09757c5dd319df3a2e3`.
- M2.70 checkpoint focus: 3 passed, 0 failed, 0 skipped.
- Smart shard `m270`: 1 selected file, 3 passed, 0 failed, 0 timed out.
- `level-c-frontend`: 9 selected files, 55 inner tests passed, 0 failed,
  0 timed out.
- `python -m compileall -q bootstrap/s3 tools`: PASS.
- `git diff --check`: PASS.

## CERTIFICATION_STATE

- `S3_FRONTEND_SELF_HOSTING_CANDIDATE=YES`.
- `PYTHON_REFERENCE_DEFAULT=YES`.
- `NATIVE_CANDIDATE_ACTIVATION=NOT_IN_SCOPE`.
- `BENCHMARK=NOT_RUN`.
- `T4=NOT_RUN`; global T4 remains reserved for M3.00.

## STATUS

M2.70 source validation is complete at
`2ec6edca679a64dd923ff09757c5dd319df3a2e3`. The M2.61-M2.70 frontend train
is ready for its documentation checkpoint and integration review.
