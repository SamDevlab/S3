# P2 Semantic Test Bundle

The whole PR #312 is not required. Its useful boundary delta is test-only
commit `c07b2c486b98e8408119f44ceedceb46c6d2549b`. Relative to P2
`1a76e341...`, it adds 217 lines only to
`tests/test_exact_segment_instruction_budget.py`; no implementation changes.
The corrected live #312 inventory also includes
`reports/s3-exact-segment-budget/SEGMENT_PLANNER_AUDIT.md` (13 changed files).

## Required Test Delta

1. Invalid limit domain rejected in both modes: negative, above U64, boolean,
   float, and string values.
2. Build/execute matrix in both modes at `0x7ffffffe`, `0x7fffffff`,
   `0x80000000`, `0x80000001`, 10,000,000,000, and U64_MAX, comparing P0/P2
   observable results and checking limit/precharge encodings.
3. Synthetic near-U64 segment-weight encoding (`W=U64_MAX-1`, `L=U64_MAX`),
   explicitly encoding-only, not an executable plan.
4. Supporting test-only imports/helpers for FFI, frame layout, liveness, and
   precharge assertions.

These additions are `BOUNDARY_TEST` and `REQUIRED_P2_REGRESSION_TEST`. They
can accompany P2 after the frozen-output expectation is resolved for the
target base. Linux x86-64 closure evidence at c07 reports 75 focused passed
and a full suite of 4,390 passed, 1 skipped, 572 subtests, 0 failed, exit 0.
The valid transcript SHA-256 is
`6ebbbdc645cb66b3fcfea5b5683b64c416acd15eff11181ab2a99f6473f0e8b0`.

```text
PR_REQUIRED=NO
TEST_DELTA_REQUIRED=YES
SEMANTIC_TEST_BUNDLE_INCLUDED=NO
```

No test was edited or copied during this audit. In the one stable-base trial,
`test_default_mode_matches_frozen_e07_native_assembly_bytes` expected 50,066
bytes and observed 49,947 for `linear`. The cause was not established and no
expectation was modified. The focused trial is not green.
