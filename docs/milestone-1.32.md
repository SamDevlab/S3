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

Machine-numeric subtraction uses its own checked typed operation rather than
negate-then-add. This is required for valid expressions such as
`INT64_MIN - INT64_MIN`, where negating the right operand would create a false
intermediate overflow. Balanced `trit`/`tryte` subtraction retains the historic
`INVERT` + `ADD` lowering, and the legacy `TSUB` opcode remains absent.

Integer and balanced-ternary relational operators preserve the established
`COMPARE` lowering path. `f64` relations use the typed `RELATE` path so IEEE-754
unordered comparisons involving NaN can be represented without collapsing them
into an artificial three-way ordering.

### Closure verification

The permanent `numeric-domain-closure` GitHub Actions job exercises the public
source syntax and compiler stack on Linux x86-64 with the native toolchain
required. Its capability probes cover checked `i64` arithmetic, IEEE-754 `f64`,
explicit conversions, O0/O1 integration, the scientific scalar formula, and an
actual native loop whose `i64` counter reaches 1,000,000. The normal unit,
renderer, differential, SSA, native, and benchmark jobs remain independent
regression gates for the exact PR head.

### Scope boundary

M1.32 does not introduce slices, heap ownership, FFI, process APIs, containers,
or GPU execution. Those remain later roadmap capabilities.
