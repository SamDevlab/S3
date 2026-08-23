# M2.67 Incremental Invalidation Candidate

## WHY_NOW

M2.66 established canonical bounded workspace modules and import edges. M2.67
adds the next frontend self-hosting boundary: determining which importers must
be invalidated after a module changes.

## ARCHITECTURAL_DECISION

`selfhost/frontend/invalidation_candidate.s3` treats an import edge as
`importer -> dependency`. For each module it performs a bounded depth-first
reachability check toward the changed set. The depth is the bounded module
count, which covers all simple paths in the graph and guarantees termination in
the presence of cycles. The candidate does not discover files, persist caches,
or activate incremental builds.

## IMPLEMENTATION_SUMMARY

- Added the S3-authored incremental invalidation fingerprint candidate.
- Added Python canonicalization, bounded validation, and differential evidence.
- Added direct, transitive, order-independent, and fail-closed contracts.
- Added M2.67 impact and shard metadata.
- Preserved fallback, activation, native, benchmark, and performance policies.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS.
- M2.61–M2.67 focused and adjacent regression set: 82 passed, 0 failed,
  0 skipped.
- M2.67 T2 at source HEAD
  `04e5c1d8f367313cd8ebe790c6f88ab8adf69939`: 1 selected, 1 passed,
  0 failed, 0 timed out.
- M2.67 T3 shard at the same source HEAD: 1 selected, 1 passed, 0 failed,
  0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone establishes invalidation evidence,
not runtime or native performance behavior.

## T4_STATUS

Not run. The development-train policy reserves global T4 for M3.00.

## STATUS

M2.67 is complete and ready for review. M2.68 remains the next milestone and
must begin only after this milestone is integrated.
