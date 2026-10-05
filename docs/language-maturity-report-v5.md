# S3 Language Maturity V5: QBE Semantics, Real Programs, and Portability

## Scope and Provenance

Campaign: `S3_QBE_SEMANTIC_EXPANSION_REAL_PROGRAM_PORTABILITY_AND_COMPILER_MATURITY_V5`.

V5 substantially expands the experimental QBE oracle while preserving S3 as the semantic authority. The branch consumes frontend-resolved, independently verified program IR; it does not teach QBE to parse source modules, and it does not register QBE as a normal compiler backend or CLI target.

| Field | Evidence |
| --- | --- |
| Starting `origin/main` | `0876d870fa648e33a6c1b362a4347ad4496c6c4e` |
| V3 source head | `4d15802848f2b975d30b54ad3024ba6626780ce6`, confirmed ancestor of starting `origin/main` |
| PR #328 | Merged; source head `f381a558d8511cda1ca95c8d10fdc76b36609ec4` |
| PR #327 | Open; head `55f73a31e8f049a1e6d805154355917921bbd53b`; untouched |
| V5 branch | `feat/s3-qbe-semantic-expansion-v5` |
| V5 PR | [#329](https://github.com/SamDevlab/S3/pull/329), OPEN, DRAFT; no merge or Ready transition |
| Final tested source head | `f50d16c58bfd6cbbd84ecf72df51bde737b4811d` |
| QBE source | Upstream `git://c9x.me/qbe.git`, pinned at `c0818978acec60ebb6167fade60fb7012cbf20ca` |

The V5 diff contains the QBE translator, its tests, narrow emulator/x86 runtime compatibility repairs, and the native ARM64 test job. No Stage1 source was changed. Historical V1-V3 reports remain unchanged; no V4 report is implied.

## Capability Results

QBE carriers and claims are limited to the shapes that pass verified-IR validation and executable differential tests. The opcode count below means opcode families with at least one accepted shape, not unrestricted support for every operand/result shape.

| Capability | V5 result | Evidence boundary |
| --- | --- | --- |
| Checked i64 | PASS | Add, subtract, multiply, negate, and divide; 29 deterministic valid cases and 9 error cases at O0/O1; overflow, division-by-zero, and bounds diagnostics compared against S3 |
| Trit | PASS | Carrier `l`; constants, arithmetic, comparison, calls, returns, branching/match, balanced min/max, range and invalid-operation behavior |
| Tryte | PASS | Carrier `l`; range `[-364, 364]`, arithmetic/comparison/conversion cases, vectors, and balanced min/max semantics |
| F64 | PASS | Constants, arithmetic, comparisons/relations, internal calls, NaN/infinity cases, `sqrt`, vectors, and scientific workloads; no fast-math or reassociation claim |
| Fixed arrays | PASS | Scalar-element allocation, indexing, mutation where represented, checked bounds, and scalar array-element references |
| Records | PASS, bounded | Nominal identity resolved before QBE; scalar and nested scalar fields, parameters, multi-cell returns via the existing sret shape |
| Enums | PASS, bounded | Tag-only and payload enums, construction, calls/returns, payload access, and match for the represented scalar-cell layouts |
| References | PASS, bounded | Mutable scalar locals and scalar array elements, including creation-time bounds and verifier initialization rules; aggregate/slice references remain rejected |
| Dynamic values | PASS, listed families | i64/tryte/f64 vectors, bytes, text, i64 maps/sets, and text-to-i64 maps through explicit runtime signatures |
| Program composition | PASS | Direct calls, recursion, imports/exports, multiple modules, and cross-module record/enum identity after normal frontend resolution |
| Optimization levels | PASS | O0 and O1 coverage across the native and workload matrices |

The current IR has 28 opcode variants. QBE accepts 22 in constrained forms: `CONST`, `CONST_STR`, `MOVE`, `INVERT`, `ADD`, `NUMERIC_DIFFERENCE`, `MULTIPLY`, `DIVIDE`, `RELATE`, `CONVERT`, `MINIMUM`, `MAXIMUM`, `COMPARE`, `CALL`, `LOAD`, `STORE`, `ADDRESS_OF`, `REFERENCE_LOAD`, `REFERENCE_STORE`, `RETURN`, `JUMP`, and `BRANCH3`. It fails closed on `AGGREGATE_ADDRESS_OF`, `AGGREGATE_FIELD_LOAD`, `AGGREGATE_FIELD_ADDRESS`, `SLICE_LENGTH`, `SLICE_LOAD`, and `SLICE_STORE`.

The IR declares nine value types (`trit`, `tryte`, `i64`, `f64`, `string`, `bytes`, `text`, `vector`, `reference`); each has only its explicitly tested QBE forms. The runtime registry contains 91 dynamic builtin signatures, of which 85 are in the QBE allowlist. The six omitted entries are `host_capability_grant`, `resource_close`, `resource_invoke`, `resource_is_open`, `resource_kind`, and `resource_open`. Host-resource execution requires a separate host context/ABI and is not claimed by V5.

## Real Workloads

The real-workload metric is the number of distinct named workload families below, not the number of parameterized pytest cases. Each is tested at O0 and O1. The x86-64 native integration checks compare observable valid results across the IR emulator, Assembly emulator, S3 x86-64 native output, and QBE native output; separate error tests compare semantic error categories.

| Workload family | Source / evidence | x86-64 native parity |
| --- | --- | --- |
| Sorting and binary search | `examples/language_maturity/insertion_sort_search.s3` | PASS |
| CSV integer parser | `examples/language_maturity/csv_integer_parser.s3` | PASS |
| Hex encoding | `examples/language_maturity/hex_encode.s3` | PASS |
| Bounded stack VM | `examples/language_maturity/bounded_stack_vm.s3` | PASS |
| Pebble compiler | `examples/language_maturity/pebble_compiler.s3` | PASS |
| Geometry kernels | `s3.v1.geometry` standard-library module | PASS |
| Scientific vector kernels | `s3.v1.science`: dot, distance, square distance, and sqrt | PASS |
| Scientific statistics and edge cases | `s3.v1.science`: statistics, empty inputs, zero norms, NaN behavior | PASS |

`QBE_REAL_WORKLOADS_PASSING=8`, `QBE_REAL_WORKLOADS_TOTAL=8`, so the selected V5 workload coverage is `8/8`. This is not a claim that every S3 program or standard-library API is supported.

The Pebble source file measures 42,886 bytes and contains 23 top-level function declarations. Its O0/O1 canary executes through QBE and the S3 native path. V5 did not instrument Pebble AST nodes, emitted IR instruction counts, or compile time; those values are recorded as not measured rather than inferred.

## Scale and Portability

The QBE scale test compiles and executes cross-module call chains at both optimization levels for 250 functions / 10 modules and 500 functions / 20 modules. The deterministic 500-function, 20-module generated source totals 30,457 UTF-8 bytes. The current QBE scale test verifies IR and Assembly emulator results, emits QBE IL, and on the required Linux x86-64 job executes both QBE and S3 native outputs.

The prior normal-compiler characterization is inherited, not remeasured here: 53,319 source bytes, 100 functions, and 3 modules. V5 did not measure AST-node, IR-block, or IR-instruction maxima for the general normal compiler.

| QBE target | V5 evidence | Qualification limit |
| --- | --- | --- |
| x86-64 | PASS, pinned native QBE CI | Required Linux native corpus, real workloads, scale, and differential tests |
| ARM64 | PASS, 18 native cases | 9 representative programs x O0/O1 on Linux `aarch64`; does not qualify dynamic S3 runtime ABI on ARM |
| RISC-V 64 | PASS, code generation only | Real-program QBE IL accepted and assembly emitted; no native execution evidence |

The pinned QBE source was built ephemerally outside the S3 checkout on both Linux x86-64 and Linux ARM64. It was not vendored. The ARM64 job used the hosted `ubuntu-24.04-arm` runner, verified `uname -m` as `aarch64`, and passed all 18 selected cases. The x86-64 QBE job passed 286 tests and skipped 18 ARM-only cases. On Windows, the local ARM-only test selection skipped all 18 cases as expected; this is not used as ARM execution evidence.

## Validation and Provenance

On the exact tested source head `f50d16c58bfd6cbbd84ecf72df51bde737b4811d`:

- `python -m compileall bootstrap/s3 tests tools`: PASS.
- ARM64-focused Windows collection: 18 expected skips because the host is not Linux ARM64.
- `git diff --check`: PASS.
- One Windows full suite, `python -m pytest -o addopts= -q`: exit 0; 4,460 passed, 534 skipped, 572 subtests passed; 4,816.84 seconds (1:20:16). Transcript: `%TEMP%\s3-qbe-v5-windows-full-20261004-231137.log`.
- Natural PR CI on the same source head: all 15 reported checks passed, including pinned native QBE x86-64 (`286 passed, 18 skipped`), native QBE ARM64 (`18 passed`), native S3 x86-64, package, security/supply-chain, differential, numeric, renderer, benchmark, Docker, and SSA gates.

The full-suite source was frozen at `f50d16c5`. Subsequent changes in this campaign are limited to these two report artifacts and PR metadata; `SOURCE_CHANGED_AFTER_FULL_SUITE=NO`. The final documentation commit and its exact-head natural CI are tracked by PR #329 to avoid self-referential commit identifiers inside the report.

## Policy and Remaining Boundary

- `QBE_INITIAL_STATUS=EXPERIMENTAL_ORACLE`.
- `QBE_FINAL_CLASSIFICATION=ORACLE_ONLY`; no stable backend registry entry, default change, stable CLI target, or release target was added.
- `DEFAULT_COMPILER=PYTHON`; `DEFAULT_NATIVE_BACKEND=S3_X86_64`.
- `SELFHOST_IMPLEMENTATION_STATUS=PAUSED`; `SELFHOST_ARCHITECTURE_RESEARCH=ACTIVE`; Stage1 V4 was not started or authorized.
- PR #327 is untouched. PR #329 remains OPEN and DRAFT; no merge, Ready transition, tag, release, or package publication was performed.

V5 establishes broad general compiler evidence: verified program IR, type/range preservation, multi-result ABI, references, runtime-backed containers, cross-module nominal values, real workloads, and larger compilation scale. That evidence can inform future self-host architecture, but it does not close Stage1-specific lowering/emission design or authorize Stage1 implementation reentry.

The remaining QBE family is host-resource invocation and its host context/capability ABI. It is a separate architecture boundary, not a reason to weaken the existing fail-closed checks. A future design should define host context lifetime, resource ownership, invocation failure mapping, and cross-backend ABI before adding those six builtins. RISC-V native qualification is also still open. Neither gap changes QBE's experimental-oracle classification.
