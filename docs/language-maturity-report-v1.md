# S3 Language Maturity Campaign V1

## Scope and Decision

This campaign evaluates the normal Python reference compiler and current S3
language/runtime from the clean main base `5b4b8f12dc9aea94fab751136d98112a6e5c0098`.
The capability data and reproducible scale probe are in
[`language-maturity-matrix-v1.json`](language-maturity-matrix-v1.json) and
[`tools/language_maturity_scale_probe.py`](../tools/language_maturity_scale_probe.py).

Self-host research remains paused. PR #327 and its worktree were not used or
modified; Stage1 V4 remains unauthorized. The default compiler remains Python.
This campaign did not change compiler/runtime implementation code, stable
defaults, release metadata, or self-host artifacts.

## Workload Ladder

| Level | Workload | Evidence and result |
| --- | --- | --- |
| 1 | Numeric/control-flow baseline | Existing scientific/numeric and public workload tests remain the baseline; no new numerical feature was added. O0/O1 and platform-specific existing coverage are recorded separately from this campaign's native workload executions. |
| 2 | Data structures | [`insertion_sort_search.s3`](../examples/language_maturity/insertion_sort_search.s3) sorts and binary-searches runtime `i64_vector` inputs, including duplicates, empty input, hits, and misses. O0/O1 IR execution and Linux x86-64 native execution pass. |
| 3 | Encoding | [`hex_encode.s3`](../examples/language_maturity/hex_encode.s3) encodes empty, ASCII, boundary octets, and embedded-zero inputs. O0/O1 IR and native execution pass. FNV/hash was not added: the source operator set has no integer bitwise XOR/AND/shift family; ternary `&` and `|` are minimum/maximum, not bitwise operators. |
| 4 | Parsing | [`csv_integer_parser.s3`](../examples/language_maturity/csv_integer_parser.s3) parses runtime text for previously unseen signed integer lists and rejects empty fields, malformed signs, and trailing separators. O0/O1 IR and native execution pass. This is a deliberately bounded CSV grammar, not general Unicode or file parsing. |
| 5 | VM/interpreter | [`bounded_stack_vm.s3`](../examples/language_maturity/bounded_stack_vm.s3) executes five valid programs covering arithmetic, bounded memory, conditional control flow, and a loop; six malformed/invalid programs are rejected. Each test program is executed repeatedly with fresh VM state. O0/O1 IR and native execution pass. |
| 6 | Compiler canary | [`pebble_compiler.s3`](../examples/language_maturity/pebble_compiler.s3) consumes runtime text, tokenizes at runtime, parses assignments/expressions/return, checks initialized identifiers, emits bytecode, and the S3 VM executes five distinct valid programs. Five malformed or semantically invalid programs are rejected. O0/O1 IR and native execution pass. This is a small, explicitly bounded language; it is not the S3 compiler or self-hosting. |

The Pebble compiler uses parallel integer vectors for token kind/value and a
small parse-result record (`PebbleStep`). It performs parse-time semantic
checks and lowers directly to its bytecode format rather than materializing a
general AST plus a second, separately serialized IR. That is adequate for the
canary acceptance criteria (runtime lexing/parsing, semantics, artifact, and
multiple programs), but it is not evidence of a reusable general-purpose S3
compiler frontend architecture.

## Execution and Parity

The new workload test module passed on the Windows host: 40 passed and 10
Linux-native cases were skipped by their platform guards. Linux pytest was not
run: the available WSL distro had Python 3.12.3 and GCC, but neither pytest nor
pip; no packages were installed. Instead, a direct Linux native driver executed
the workload assertions without a pytest runner. The five programs (ordering,
encoding, CSV parser, bounded VM, and Pebble compiler) were compiled at O0 and
O1 by the S3 x86-64 backend, assembled with `gcc -nostartfiles -no-pie`, and run
as Linux x86-64 ELF programs: all 10 executions returned the expected zero
failure count. The multi-module record/enum case was also compiled and executed
natively and returned 19. The scale probe ran all four generated programs in
the Linux IR emulator and native backend with matching results.

The focused numeric/scientific baseline passed separately on Windows:
17 passed, 4 skipped. It is baseline evidence, not a full-suite run.

`execute_assembly` could not execute the dynamic vector workload: the hosted
Assembly emulator raised the exact error `KeyError('i64_vector_new')` when the
workload attempted the dynamic-vector builtin. This is an Assembly-emulator
runtime-coverage limitation, not an IR/native semantic disagreement. The
campaign records it as `LIMITED`; it does not substitute IR-emulator success
for Assembly-emulator parity.

## Normal Compiler Scale

The reproducible probe uses 10, 25, 50, and 100 functions, one 32-field record,
record field access, many local/function symbols, a bounded loop, and nested
`match` control flow. The Linux x86-64 WSL/Python 3.12.3 O1 run measured
compilation with `tracemalloc`; exact measurements and inputs are in the JSON
matrix. At 10 / 25 / 50 / 100 functions, respectively, source sizes were
5,439 / 13,419 / 26,719 / 53,319 bytes, IR instruction counts were 705 / 1,950 /
4,025 / 8,175, and compile times were 5.148313 / 10.212094 / 19.643453 /
47.638931 seconds. At 100 functions it compiled 12,660 tokens into 1,668 blocks,
with 11,737,478 traced Python allocation bytes. It emitted 554,336 bytes of S3
Assembly text and 5,514,577 bytes of x86-64 assembly; GCC produced a 2,206,360-
byte ELF and native execution returned 42 as expected. These are
characterization measurements, not performance claims. Compile time includes
tracemalloc overhead; `peak_traced_bytes` is Python allocation tracing, not
process RSS.

Multi-module coverage compiles three modules with explicit imports/exports,
cross-module calls, and imported record/enum types. Forward and reversed input
filesystem ordering produce equal IR, Assembly, and native assembly; hosted IR,
Assembly, and Linux x86-64 native execution all returned 19. The test also
compiles the graph in reversed source ordering and checks deterministic
artifacts.

## Capability and Documentation Audit

The matrix distinguishes source-language, reference compiler, hosted runtime,
native backend, library, experimental substrate, selfhost-only, and
Assembly-emulator coverage. Important limits include:

- vectors/maps/sets are closed type families, not arbitrary generic
  `vector<T>` / `map<K,V>` / `set<T>` source constructors;
- filesystem/resource access is capability/provider mediated, not a general
  source-level `open/read/write` API;
- runtime text APIs are bounded and byte-oriented; Unicode scalar/grapheme
  processing is not established here;
- maps/sets and FFI have existing support but were not broadened by these
  workloads;
- native scoped-resource providers remain structural/deterministic fixtures,
  not real OS file/network providers.

The following documents conflict with later executable evidence and are kept
unchanged in this campaign so the discrepancy remains visible:

- `docs/structured-data-capabilities.md` says records/enums and runtime strings
  are unsupported, while current parser/semantic/tests and later decisions
  establish records, enums, owned text, and dynamic buffers.
- `docs/milestone-1.51.md` says implementation has not started, while
  `tests/test_m151_composite_owned_values.py` exercises composite-owned values.
- `docs/decisions/ADR-0037-m1.51a-composite-owned-values.md` describes
  architecture-only closure and is inconsistent with later executable
  composite-owned-value tests. This campaign does not claim native qualification
  of the whole M1.51 scope.
- `docs/language-gaps.md` still lists runtime text construction, records, enums,
  modules, vectors, maps, and file I/O as unavailable, contrary to current
  source and executable evidence. The actual limits are narrower and are
  recorded in the capability matrix; this historical document remains
  unchanged.

## External Workload References

Embench informed the preference for small deterministic bounded workloads; its
GPL-3.0 license was inspected and no Embench source was copied or adapted.
LangArena informed category diversity (sorting, encoding, CSV, interpreters,
hashing); its MIT license was inspected and no LangArena source was copied or
adapted. QBE is treated only as a possible secondary backend and differential
oracle. Sources: [Embench](https://www.embench.org/), [Embench source and
license](https://github.com/embench/embench-iot), [LangArena repository and MIT
license](https://github.com/kostya/LangArena), [QBE overview](https://c9x.me/compile/),
and [QBE IL documentation](https://c9x.me/compile/doc/il.html).

## QBE Architecture Assessment

- `QBE_FIT`: plausible as a secondary backend after a bounded translator
  experiment; not a replacement for the S3 frontend, verifier, or current
  backend.
- `QBE_PRIMARY_BENEFIT`: compact SSA backend with C ABI support and current
  amd64, arm64, and riscv64 targets; arm64/riscv64 are the main portability
  opportunity beyond the campaign's x86-64 execution evidence.
- `QBE_SEMANTIC_GAPS`: QBE's `w/l/s/d` are machine-oriented 32/64-bit integer
  and IEEE float types, not S3's balanced values or safety model. Map `trit`
  and `tryte` only to integer carriers (`w` is sufficient for their current
  bounded representations), keeping range checks, balanced arithmetic, and
  overflow behavior explicit in verified S3 IR before translation. Map `i64`
  to `l` and `f64` to `d`.
- `QBE_ABI_GAPS`: QBE's full C ABI does not automatically implement S3's
  internal aggregate/reference conventions. S3 records need explicit layout
  and flattening or memory lowering; references may be carried as `l` values
  only after provenance, lifetime, and bounds semantics are discharged by S3.
  C wrappers would be needed where the S3 internal ABI differs from C.
- `QBE_PORTABILITY_BENEFIT`: a secondary QBE target could expose arm64 and
  riscv64 code generation without changing S3's source frontend.
- `QBE_DIFFERENTIAL_TEST_VALUE`: high if both backends consume the same
  verified S3 IR and compare execution results on deterministic workload
  programs.
- `QBE_RECOMMENDED_NEXT_EXPERIMENT`: an offline, no-production-change
  translator spike for a checked scalar subset (i64/f64, branches, calls),
  followed by IL validation and native differential tests. No QBE code or
  dependency was added here.

QBE must not own S3 checked arithmetic, bounds, trit/tryte semantics,
references, nominal type rules, or diagnostic behavior. Records and references
must be lowered to explicit machine operations/ABI storage before QBE receives
the IL.

## Self-Host Re-entry Review

Against `docs/selfhost/REENTRY_CRITERIA.md`:

| Gate | Result | Evidence-based reason |
| --- | --- | --- |
| 1 | PARTIAL | Current stable syntax/capabilities are known, but the exact required Stage1 subset has not been re-approved. |
| 2 | FAIL | No complete S3 representation/capacity/complexity matrix for every compiler identity, verifier, emitter, and whole-program structure. |
| 3 | PARTIAL | The normal Python compiler has a generic pipeline; the complete corresponding S3 selfhost pipeline remains unproven. |
| 4 | FAIL | No reviewed S3 `compile_program` composition-root design satisfying the re-entry contract. |
| 5 | FAIL | The historical Stage1 implementation remains a bounded subset, not arbitrary programs in a frozen required subset. |
| 6 | FAIL | Compiler-wide scope/declaration/type/storage identity and lookup design is not closed for re-entry. |
| 7 | FAIL | No complete mapping of the Stage1 subset to a generic selfhost IR. |
| 8 | FAIL | No complete independent verifier plan for that selfhost IR. |
| 9 | FAIL | No complete general emitter and bounded output/capacity plan for that IR. |
| 10 | NOT_EVALUATED | This campaign did not re-audit transactional allocator/checkpoint design. |
| 11 | PARTIAL | Normal compiler scaling is now measured to 100 functions; the selfhost critical-path complexity model remains unclosed. |
| 12 | PARTIAL | Historical bootstrap evidence exists, but no new complete seed-to-Stage2 lineage was qualified. |
| 13 | PARTIAL | Bounded vertical slices exist, but they do not establish a single generic selfhost path. |
| 14 | FAIL | A small Pebble grammar passes; broad feature composition and anti-specialization for a full compiler subset are not proven. |

`SELFHOST_REENTRY_AUTOMATIC=NO`; `STAGE1_V4_AUTHORIZED=NO`;
`SELFHOST_READY_FOR_REENTRY=NO`.

## Outcome

The campaign establishes materially broader workload evidence without adding
workload-specific compiler paths or modifying production compiler/runtime
logic. Level 1's existing focused baseline passed; levels 2, 4, 5, and 6 pass
within their declared bounded workloads/grammars; level 3 passes for hex
encoding but remains partial for hashing. Normal compilation scales through
100 functions and three modules on the measured setup. Five workload programs
passed hosted IR and Linux native execution at O0/O1; the separate
three-module/record/enum graph and all four scale programs also passed Linux
native execution.

The remaining blockers to a stronger maturity claim are Assembly emulator
coverage for dynamic built-ins, broader source-level filesystem/Unicode and
generic collection capabilities, and additional unseen-program/compiler
composition evidence. Linux pytest was unavailable in the WSL environment, so
the direct native runs are not reported as a Linux pytest pass. The full suite
was not run because production compiler/runtime code was unchanged. These gaps
are recorded rather than papered over; they do not authorize self-hosting.

`CAMPAIGN_COMPLETE=PARTIAL`: the independent Pebble canary passes its declared
bounded acceptance criteria and real nonnumeric workloads run natively, but
the requested broad emulator/native parity is not closed for dynamic
built-ins. `WORKLOAD_SPECIFIC_HACKS_ADDED=NO`,
`NEW_GENERAL_LANGUAGE_CAPABILITIES=NONE`,
`GENERIC_COMPILER_DIAGNOSTICS_IMPROVED=NO`,
`QBE_BACKEND_IMPLEMENTATION=OUT_OF_SCOPE`,
`SELFHOST_RESEARCH_STATUS=PAUSED`,
`SELFHOST_REENTRY_AUTOMATIC=NO`, and `STAGE1_V4_AUTHORIZED=NO`.

No stable default, PR #327, release, tag, or benchmark protocol was changed.
