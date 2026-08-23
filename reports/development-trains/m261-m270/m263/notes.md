# M2.63 Canonical AST Candidate

## WHY_NOW

The M2.62 parser candidate established a bounded V0.6 grammar. M2.63 adds the
canonical AST boundary so layout-only changes can be compared independently of
the source presentation.

## ARCHITECTURAL_DECISION

`selfhost/frontend/ast_candidate.s3` validates the M2.62 grammar and emits a
canonical fingerprint over the function node, function name, primitive return
type, and primitive literal kind/value. Newline and indentation tokens are
validated for structure but excluded from the canonical fields. The Python
adapter parses the same source into the reference AST and derives the same
canonical fields. Differential evidence remains exact-input and provenance
bound.

## IMPLEMENTATION_SUMMARY

- Added the S3-authored canonical AST candidate.
- Added canonical Python AST extraction and differential evidence.
- Added contracts for integer, float, and string literals, layout invariance,
  value sensitivity, and rejected expression shapes.
- Added M2.63 impact and shard metadata.
- Preserved fallback, activation, native, and performance policies.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3 tools`: PASS.
- Focused and adjacent tests: 52 passed, 0 failed, 0 skipped.
- M2.63 T2 at source HEAD `68c0c3f7629441b7795b1f1ce7d2a07f3f59a943`: 1
  selected, 1 passed, 0 failed, 0 timed out.
- M2.63 T3 shard at the same source HEAD: 1 selected, 1 passed, 0 failed,
  0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone establishes canonical AST evidence
only and makes no native or performance claim.

## T4_STATUS

Not run. The development-train policy reserves global T4 for M3.00.

## STATUS

M2.63 is complete and ready for review. M2.64 remains the next milestone and
must begin only after this milestone is integrated.
