# M2.53 Arena / Region Memory Foundation

## WHY_NOW

Compiler-owned AST and IR work needs bounded temporary storage with an explicit
lifetime boundary. The existing dynamic-value allocator tracks individual
buffers but does not provide mark/rewind semantics for compiler regions.

## ARCHITECTURAL_DECISION

`Arena` is a fixed-capacity hosted reference region. Allocations are monotonic
and aligned, capacity never grows implicitly, and `ArenaMark` makes rewinding
explicit. Handles created after a rewind are invalidated and cannot read or
write reused storage. The module does not replace the dynamic-value allocator,
define a native heap ABI, or claim garbage collection.

## IMPLEMENTATION_SUMMARY

- Added a bounded `Arena` with fixed-capacity aligned allocation.
- Added explicit mark, rewind, and reset operations.
- Added checked fixed-size `ArenaBlock` read/write handles.
- Added deterministic capacity, bounds, foreign-mark, and use-after-rewind
  regressions.
- Added M2.53 impact and shard metadata.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- Focused arena and adjacent dynamic-buffer matrix: 23 selected, 22 passed,
  1 skipped, 0 failed. The skip is the pre-existing Linux-native FFI test in
  `tests/test_dynamic.py` on Windows.
- M2.53 T2 at source HEAD
  `576e769a60d95e5a1b36c15e52d62d4b9bbf8993`: 1 selected, 1 passed,
  0 failed, 0 timed out.
- M2.53 T3 shard at the same source HEAD: 1 selected, 1 passed,
  0 failed, 0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone validates bounded region lifetime
and handle safety only; no performance claim is made.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

AST/IR integration, native region descriptors, and cross-process serialization
remain later concerns. The current API is intentionally a hosted foundation.
