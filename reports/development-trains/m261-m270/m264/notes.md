# M2.64 Module and Import Candidate

## WHY_NOW

The lexer, parser, and canonical AST candidates now provide a bounded frontend
substrate. M2.64 introduces the first self-hosted declaration boundary for
module identity and imported symbol identity.

## ARCHITECTURAL_DECISION

`selfhost/frontend/module_candidate.s3` recognizes two explicitly bounded
declaration shapes: `module <name>` and `from <module> import <name>`, each with
V0.6 newline and EOF termination. The S3 candidate emits a canonical
fingerprint that includes the declaration kind and symbol hashes. The Python
adapter supplies the reference token contract and compares exact input through
the differential harness. File resolution, workspace search, and runtime
activation remain out of scope.

## IMPLEMENTATION_SUMMARY

- Added the S3-authored module/import declaration candidate.
- Added the Python adapter and differential evidence object.
- Added contracts for both declaration forms, symbol sensitivity, and closed
  rejection of unsupported forms.
- Added M2.64 impact and shard metadata.
- Preserved fallback, activation, native, and performance policies.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3 tools`: PASS.
- Focused and adjacent tests: 57 passed, 0 failed, 0 skipped.
- M2.64 T2 at source HEAD `0f043a16fb4989d7e53868ab77206d00fd9b7b13`: 1
  selected, 1 passed, 0 failed, 0 timed out.
- M2.64 T3 shard at the same source HEAD: 1 selected, 1 passed, 0 failed,
  0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone establishes module/import boundary
evidence only and makes no native or performance claim.

## T4_STATUS

Not run. The development-train policy reserves global T4 for M3.00.

## STATUS

M2.64 is complete and ready for review. M2.65 remains the next milestone and
must begin only after this milestone is integrated.
