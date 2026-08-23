# M2.65 Diagnostic Recovery Candidate

## WHY_NOW

The frontend candidates now have bounded lexer, parser, AST, and declaration
contracts. M2.65 adds a fail-closed diagnostic/recovery boundary before later
Level-H integration work.

## ARCHITECTURAL_DECISION

`selfhost/frontend/diagnostic_candidate.s3` maps six stable frontend diagnostic
IDs to a compact category/action result: lexical invalid input, unterminated
literal, invalid dedent, parse syntax, obsolete brace syntax, and semantic
invalid program. Unknown IDs return rejection. The Python adapter extracts the
same IDs from reference lexer/parser failures and the differential harness
compares exact category/action results. This is a bounded recovery contract,
not a replacement for diagnostic rendering or a claim of complete Level-H.

## IMPLEMENTATION_SUMMARY

- Added the S3-authored diagnostic category and recovery-action candidate.
- Added Python reference extraction from lexer/parser diagnostic codes.
- Added contracts for all six known IDs, source-level lexical evidence, and
  unknown-code rejection.
- Added M2.65 impact and shard metadata.
- Preserved parser/runtime behavior and fail-closed activation policy.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3 tools`: PASS.
- Focused and adjacent tests: 72 passed, 0 failed, 0 skipped.
- M2.65 T2 at source HEAD `e1d0a29d5a4ccaec3108799506649f0787128c3d`: 1
  selected, 1 passed, 0 failed, 0 timed out.
- M2.65 T3 shard at the same source HEAD: 1 selected, 1 passed, 0 failed,
  0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone establishes diagnostic/recovery
evidence only and makes no native or performance claim.

## T4_STATUS

Not run. The development-train policy reserves global T4 for M3.00.

## STATUS

M2.65 is complete and ready for review. M2.66 remains the next milestone and
must begin only after this milestone is integrated.
