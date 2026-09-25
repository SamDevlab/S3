# Scientific Numeric Foundation v1

## Surface

The versioned source module `s3.v1.science` composes existing S3 vector,
reference, loop, f64 arithmetic, and `sqrt` operations. It adds no compiler
opcode or backend-only scientific shortcut.

Exports are `sum`, `dot`, `mean`, `variance`, `squared_distance`, `distance`,
`l2_norm`, and `rmsd`, plus the `F64Result` record used by fallible binary
operations. Its `status` field is `0` for a valid value, `1` for unequal
vector lengths, and `2` for RMSD on an empty vector; `value` is meaningful
only when status is zero.

## Numerical contracts

All vector inputs are borrowed `f64_vector` values. The loops visit elements
in increasing index order and accumulate left-to-right. The implementation
does not reassociate operations or claim bit-identical results across
architectures.

- `sum(v)`: left-to-right sum; empty input returns `0.0`.
- `dot(a, b)`: left-to-right sum of pairwise products. Equal lengths are
  required; unequal lengths return status 1. Two empty vectors produce valid
  zero.
- `mean(v)`: arithmetic mean; empty input returns `0.0` by this module's
  defined convention.
- `variance(v)`: population variance, `sum((x - mean(v))^2) / N`; empty
  input returns `0.0` by this module's defined convention. A singleton has
  variance zero.
- `squared_distance(a, b)`: `sum((a[i] - b[i])^2)`; equal lengths are
  required. Unequal lengths return status 1; two empty vectors produce valid
  zero.
- `distance(a, b)`: `sqrt(squared_distance(a, b))`, with the same length
  status. Equal empty vectors produce valid zero.
- `l2_norm(v)`: `sqrt(dot(v, v))`; empty input produces zero.
- `rmsd(a, b)`: `sqrt(squared_distance(a, b) / N)`. Unequal lengths return
  status 1; empty equal-length inputs return status 2 because division by
  zero has no RMSD value.

No integer accumulation or checked-integer overflow is involved. f64 inputs
retain the language's IEEE-754 behavior: NaN, infinities, and signed zero are
accepted and propagate through ordinary operations and the existing `sqrt`
contract. The module adds no NaN canonicalization or fast-math guarantee.

## Compatibility

The module is additive within the existing `s3.v1` standard-library namespace
and is included in the deterministic manifest. It preserves source syntax
0.6, IR 0.6.0, Assembly 0.6.0, diagnostic schema 1.0.0, and public stable
version 1.0.0. The Python reference compiler remains the default; Linux
x86-64 native execution is an independently qualified backend path.
