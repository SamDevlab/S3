# Experimental library contracts

These modules live below `ecosystem/libraries`, not in the official standard
library. Applications consume them through the repository's existing S3 module
imports and offline package resolver. Package source paths are repository
relative and network-free.

## `s3-integer-summary`

Public module: `s3.ecosystem.integer_summary`.

- `summarize_i64(&i64_vector) -> I64Summary` returns status, count, sum, min,
  and max. Empty input is represented by the module's status and zero-valued
  fields; callers must check status before interpreting extrema.
- Input is an S3 `i64_vector`; there is no allocation beyond the returned
  record. The routine traverses input in order and is deterministic.
- Signed sum overflow is not checked. The caller must keep the mathematical
  sum within `i64` range.
- Consumed by the data-quality and graph applications.

## `s3-balanced-ternary`

Public module: `s3.ecosystem.balanced_ternary`.

- `encode_i64(i64) -> BalancedDigits` and `decode_i64(BalancedDigits) ->
  DecodeResult` expose status-bearing bounded conversions.
- Encoded values use at most 19 balanced trits and cover `-581130733` through
  `581130733`. Values outside that range return a non-success status; they are
  not truncated or wrapped.
- Digits are stored least-significant first as ordinary integer codes
  `0 => -1`, `1 => 0`, `2 => 1`. The library does not alter built-in `trit` or
  `tryte`, nor claim a compact-memory or speed advantage.
- Boundary and round-trip cases are exercised by the balanced-state app and
  the data-quality app.

## `s3-key-value-records`

Public module: `s3.ecosystem.key_value_records`.

- `parse_i64_record` accepts one ASCII `key=value` pair, with a non-empty key,
  one separator, an optional minus sign and up to six decimal digits.
- The result includes status, key/value components. Malformed, empty, repeated
  separators, non-ASCII bytes, and out-of-range values are rejected by status;
  this is not an INI/CSV/JSON parser.
- Input is bounded and processing is deterministic. Unicode normalization,
  escaping, and general-purpose text storage are not supported.
- Valid and invalid fixtures are covered by the event-log application.

## Reuse, tests, and examples

Each package has a `package.toml`, source module, and at least one importing
application. `python -m ecosystem.application_lab run` verifies lock identity,
topological package reuse, source hashes, fixture hashes, and exact app outputs.
These contracts are experimental and may change before promotion to the
official standard library.
