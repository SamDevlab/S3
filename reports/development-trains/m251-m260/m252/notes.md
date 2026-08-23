# M2.52 Deterministic Collections

## WHY_NOW

Compiler and runtime collection behavior needs deterministic replay and stable
first-seen ordering so that equivalent executions produce equivalent observable
results. This milestone also closes the moved-value access boundary for indexed
map reads.

## ARCHITECTURAL_DECISION

`DynamicMap` and `DynamicSet` retain insertion/first-seen order across seeded
replay, update, removal, and set compaction. Indexed map access validates the
live ownership state before validating or reading an index, so moved values
cannot be observed through a secondary access path. No hash randomization,
implicit ordering, native ABI, or heap policy claim was introduced.

## IMPLEMENTATION_SUMMARY

- Hardened `DynamicMap.key_at()` and `DynamicMap.value_at()` with live-state
  validation before indexed access.
- Added deterministic seeded replay regressions for ordered maps and sets.
- Added moved-map indexed-access regression coverage.
- Added M2.52 impact and shard metadata.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- Focused collection and dynamic-buffer matrix: 31 selected, 31 passed,
  0 skipped, 0 failed.
- M2.52 T2 at source HEAD
  `3be16005c14ef6eabd3d5934302dc4f68060291a`: 3 selected, 3 passed,
  0 failed, 0 timed out.
- M2.52 T3 shard at the same source HEAD: 1 selected, 1 passed,
  0 failed, 0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone validates deterministic collection
semantics and ownership safety only; no performance claim is made.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

Cross-process deterministic serialization and source-language collection
syntax remain separate later concerns. This milestone closes the hosted
collection ordering and moved-access contract.
