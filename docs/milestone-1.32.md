# Milestone 1.32 — Numeric Domains & Large Indexing

## Capability closure

The original M1.32 merge established a substantial numeric foundation but was
later classified `PARTIAL` by the post-campaign forensic audit. This closure
completes the programmer-visible numeric contract without rewriting history.

### Public numeric domains

- `i64` is a checked signed 64-bit integer domain. `+`, `-`, `*`, `/`, unary
  `-`, and comparisons are source-visible. Overflow does not silently wrap;
  division by zero and `INT64_MIN / -1` are deterministic failures.
- `f64` follows IEEE-754 binary64 for arithmetic and relational comparisons.
  NaN, infinities, and signed zero are valid values; the compiler does not
  enable fast-math or reassociation.
- Balanced `trit`/`tryte` semantics remain unchanged. `~`, `&`, and `|` remain
  balanced-ternary operations rather than being repurposed for machine numeric
  values.

### Explicit conversions

The initial explicit conversion builtins are:

- `to_i64(trit|tryte) -> i64`
- `to_f64(trit|tryte|i64) -> f64`
- `to_tryte(i64) -> tryte` with a checked `[-364, 364]` boundary

No integer/reference casts are introduced.

### Compiler stack

The numeric operations are represented through typed IR, verification, IR
emulation, S3 Assembly, Assembly verification/emulation, serialization, and
Linux x86-64 native lowering. Native `f64` arithmetic uses SSE2/XMM and the
existing mixed SysV integer/SSE calling convention.

### Scope boundary

M1.32 does not introduce slices, heap ownership, FFI, process APIs, containers,
or GPU execution. Those remain later roadmap capabilities.
