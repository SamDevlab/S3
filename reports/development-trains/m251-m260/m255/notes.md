# M2.55 Source Manager and Canonical Span Infrastructure

## WHY_NOW

Diagnostics and future frontend components need one identity for each source
file, exact offsets, and deterministic line/column mapping across multiple
files. Existing parser-local spans do not provide that shared ownership model.

## ARCHITECTURAL_DECISION

`SourceManager` assigns stable integer IDs to uniquely named source files and
tracks bounded total source storage. `SourceSpan` is an immutable half-open
range tied to one source ID. Line mapping is computed from canonical newline
offsets with one-based coordinates, including CRLF and Unicode source text.
Unknown sources, duplicate names, capacity overflow, and invalid spans fail
closed. Existing parser span types remain unchanged.

## IMPLEMENTATION_SUMMARY

- Added bounded multi-file source registration and source-name lookup.
- Added immutable source-file metadata and canonical source spans.
- Added offset-to-line/column mapping and line-text extraction.
- Added deterministic multi-file, Unicode, CRLF, capacity, and bounds tests.
- Added M2.55 impact and shard metadata.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- Focused source-manager and adjacent bounded-text matrix: 15 selected,
  15 passed, 0 skipped, 0 failed.
- M2.55 T2 at source HEAD
  `d63a2d56a81e6e88ae2702a868d58fcd28dd652d`: 1 selected, 1 passed,
  0 failed, 0 timed out.
- M2.55 T3 shard at the same source HEAD: 1 selected, 1 passed,
  0 failed, 0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone validates source identity and span
correctness only; no performance claim is made.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

Parser integration, source loading from host services, and structured
diagnostics formatting remain later concerns. The current manager is the
canonical hosted source foundation.
