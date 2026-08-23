# M2.57 Canonical Compiler Serialization Foundation

## WHY_NOW

Future AST/IR differential work needs a small representation whose bytes are
stable across equivalent construction order and whose failures do not depend
on host object stringification. The existing versioned IR serializer remains
the authoritative IR artifact format; this milestone adds the complementary
debug-value boundary.

## ARCHITECTURAL_DECISION

`serialize_canonical` accepts only explicit JSON-shaped values, sorts object
keys, preserves UTF-8, rejects non-finite numbers and unsupported host objects,
and enforces a byte bound before returning. `serialize_debug` adds required
schema/version fields in a deterministic envelope. Tuple input is normalized
to JSON arrays; no arbitrary object encoder or implicit `repr` is used.

## IMPLEMENTATION_SUMMARY

- Added bounded canonical JSON serialization for debug values.
- Added versioned debug envelopes for future AST/IR snapshots.
- Added normative documentation without changing the existing IR artifact
  format.
- Added order, UTF-8, envelope, unsupported-value, and byte-limit tests.
- Added M2.57 impact and shard metadata.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- Focused canonical and existing IR serialization matrix: 26 selected,
  26 passed, 0 skipped, 0 failed.
- M2.57 T2 at source HEAD
  `d479a278e181d4c27c3a26893539d57d849a7dd2`: 1 selected, 1 passed,
  0 failed, 0 timed out.
- M2.57 T3 shard at the same source HEAD: 1 selected, 1 passed,
  0 failed, 0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone validates canonical debug bytes
only; no performance claim is made.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

AST/IR-specific snapshot schemas and differential comparison policy remain
later concerns. Existing `serialize_ir` remains unchanged and authoritative.
