# M2.51 Dynamic Text Foundation

## WHY_NOW

Compiler components need bounded runtime text that can be built from input,
passed as an owned value, and handled without implicit growth or host-specific
encoding behavior. The existing M1.39 text value provided the storage boundary;
M2.51 closes the remaining host ownership and error surface.

## ARCHITECTURAL_DECISION

`DynamicText` remains an owned UTF-8 value backed by exact-capacity
`DynamicBytes`. Text moves transfer the backing storage and make the source
unusable. Append remains bounded and atomic: capacity is checked before any
byte is written. Invalid Unicode encoding and invalid value-family operations
produce S3 dynamic errors rather than leaking host exceptions or attributes.

No implicit capacity growth, heap policy change, source-language syntax change,
or native descriptor ABI claim was introduced.

## IMPLEMENTATION_SUMMARY

- Added explicit `DynamicText.move()` ownership transfer.
- Normalized invalid Unicode encoding to `TextEncodingError`.
- Rejected invalid append/find value families with `DynamicError`.
- Added regressions for move invalidation, bounded atomic append, encoding
  failures, and wrong-family operations.
- Added M2.51 impact/shard metadata.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- Focused dynamic text matrix: 24 selected, 23 passed, 1 skipped, 0 failed.
  The skip is the pre-existing Linux-native FFI test on Windows.
- M2.51 T2 at source HEAD
  `e5a064fb4704f1acce125582f9e73c6e889e7078`: 3 selected, 3 passed,
  0 failed, 0 timed out.
- M2.51 T3 shard at the same source HEAD: 1 selected, 1 passed, 0 failed,
  0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone validates bounded ownership and text
correctness only; no performance claim is made.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

The native descriptor ABI and source-language dynamic text integration remain
separate later concerns. This milestone hardens the hosted runtime foundation.
