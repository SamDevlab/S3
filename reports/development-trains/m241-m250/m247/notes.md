# M2.47 Official Per-Loop Repeatability Analyzer

## WHY_NOW

The persisted `s3bench` archive already had the normalized measurement and
comparison contracts from issue #131. M2.47 closes the remaining discovery
ambiguity so an archive cannot silently replace a missing run with a different
run number or duplicate one canonical benchmark across storage directories.

## ARCHITECTURAL_DECISION

Benchmark directory names remain storage-only safe names. Canonical identity is
read from `benchmark-id.txt` when present, or derived from the documents when
the marker is absent. The default three-run archive must contain exactly
`run-1`, `run-2`, and `run-3`; unexpected, missing, renumbered, or duplicate
storage layouts fail closed before measurement aggregation.

The analyzer continues to join results and comparisons by the complete
seven-field key, normalize kernel timing to `median_ns_per_loop`, keep process
timing at one loop per sample, separate scopes, and compare S3 O1/O0 only when
all scope and execution dimensions match. A comparison is `CONCLUSIVE` only
when its observed change exceeds the measured between-run variation.

## IMPLEMENTATION_SUMMARY

- Hardened deterministic run discovery to require the exact expected run names.
- Rejected unexpected child directories and duplicate canonical benchmark IDs
  spread across safe storage directories.
- Added regression coverage for missing run numbers and duplicate storage
  identities.
- Added M2.47 shard and impact metadata and documented the archive contract.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- `git diff --check`: PASS
- Focused s3bench cross-layer matrix: 79 selected, 79 passed, 0 failed,
  0 timed out.
- M2.47 T2 at source HEAD
  `14afdc4c2369657b981c78fa79b465e2df787451`: 1 selected, 1 passed,
  0 failed, 0 timed out.
- M2.47 T3 shard at the same source HEAD: 1 selected, 1 passed, 0 failed,
  0 timed out.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone validates persisted-run analysis and
report generation only; it makes no runtime performance claim.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

The analyzer validates archive structure and statistical comparability, but it
does not execute workloads or establish cross-host performance equivalence.
