# M2.56 Structured Diagnostics Runtime

## WHY_NOW

The hosted diagnostics runtime already has typed codes, categories, phases,
source positions, bounded collections, and deterministic serialization. Its
remaining construction gap was incremental message assembly without an
explicit byte bound.

## ARCHITECTURAL_DECISION

`DiagnosticMessageBuilder` is a bounded UTF-8 construction boundary layered on
the existing `Diagnostic` schema. It rejects non-text fragments, counts encoded
bytes rather than code points, bounds note count and note bytes, and fails
before a fragment that would exceed a limit is appended. It never truncates or
parses message text, and the resulting diagnostic remains immutable and
deterministically serialized.

## IMPLEMENTATION_SUMMARY

- Added bounded message and note construction to the existing diagnostics
  runtime.
- Preserved all existing categories, codes, phases, and JSON fields.
- Documented the bounded construction contract in the diagnostics spec.
- Added UTF-8, atomic-limit, note-limit, and type-validation regressions.
- Added M2.56 impact and shard metadata.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- Focused diagnostics matrix: 22 selected, 22 passed, 0 skipped, 0 failed.
- M2.56 T2 at source HEAD
  `a2bf7b19aa461ef786e0a9020f9a6c1697e6168a`: 3 selected, 3 passed,
  0 failed, 0 timed out.
- M2.56 T3 shard at the same source HEAD: 1 selected, 1 passed,
  0 failed, 0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone validates diagnostic construction
and serialization contracts only; no performance claim is made.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

Frontend adoption of the builder and source-manager-backed diagnostic spans
remain later integration concerns. Existing diagnostic producers continue to
operate unchanged.
