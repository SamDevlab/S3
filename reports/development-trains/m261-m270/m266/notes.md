# M2.66 Workspace Graph Candidate

## WHY_NOW

The frontend train now has bounded declaration and diagnostic contracts. M2.66
adds a canonical workspace graph boundary for module identities and import
edges before incremental invalidation work begins.

## ARCHITECTURAL_DECISION

`selfhost/frontend/workspace_candidate.s3` consumes up to eight canonical module
IDs and sixteen import edges. It validates that each edge has both a known
source and a known target, then emits a deterministic graph fingerprint. The
Python adapter canonicalizes module and edge order and supplies the reference
graph contract. Workspace discovery, filesystem access, and build activation
remain out of scope.

## IMPLEMENTATION_SUMMARY

- Added the S3-authored bounded workspace graph candidate.
- Added Python graph normalization and differential evidence.
- Added contracts for graph matching, order independence, unknown-target
  rejection, and empty-workspace rejection.
- Added M2.66 impact and shard metadata.
- Preserved fallback, activation, native, and performance policies.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3 tools`: PASS.
- Focused and adjacent tests: 75 passed, 0 failed, 0 skipped.
- M2.66 T2 at source HEAD `a71b4ae594a94a592252078c22b1809b72f4bef3`: 1
  selected, 1 passed, 0 failed, 0 timed out.
- M2.66 T3 shard at the same source HEAD: 1 selected, 1 passed, 0 failed,
  0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone establishes workspace graph evidence
only and makes no native or performance claim.

## T4_STATUS

Not run. The development-train policy reserves global T4 for M3.00.

## STATUS

M2.66 is complete and ready for review. M2.67 remains the next milestone and
must begin only after this milestone is integrated.
