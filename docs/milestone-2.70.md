# Milestone 2.70: Frontend Self-Hosting Level-C Checkpoint

M2.70 closes the M2.61-M2.70 frontend self-hosting train with a deterministic
Level-C profile over the lexer, parser, AST, module, diagnostics, workspace,
invalidation, Assembly frontend, and optional canary milestones.

## Checkpoint

`python tools/s3test.py level-c-frontend --format json --timeout 180`
selects exactly the nine M2.61-M2.69 milestone files in order. It is a
Level-C profile and does not select the global T4 suite.

The bounded self-hosted frontend candidate is certified as available for
explicit canary use. The Python reference remains the default execution path;
M2.70 does not promote or replace it.

## Evidence Contract

- Level-C profile: `level-c-frontend`.
- Checkpoint contract: `tests/test_m270_frontend_self_hosting_checkpoint.py`.
- Profile coverage: M2.61 through M2.69, nine files, 55 inner tests.
- Candidate state: `S3_FRONTEND_SELF_HOSTING_CANDIDATE=YES`.
- Default state: `PYTHON_REFERENCE_DEFAULT=YES`.
- No benchmark, native, performance, or global T4 claim is made.
