# S3 Language Maturity Campaign V2

## Scope and Snapshot

Campaign: `S3_LANGUAGE_MATURITY_V2_ASSEMBLY_PARITY_COMPILER_CANARY_AND_QBE_ORACLE_V1`.

This report extends, but does not rewrite, the historical [V1 report](language-maturity-report-v1.md) and [V1 matrix](language-maturity-matrix-v1.json). V1's workload and compiler-scale measurements remain the baseline; they were not remeasured here.

| Field | Evidence |
| --- | --- |
| Starting HEAD | `9d508bfbd26851d6dafe6e84ac83535f6b9d1c3f` |
| Branch | `feat/s3-language-maturity-real-workloads-v1-20261004` |
| PR | [#328](https://github.com/SamDevlab/S3/pull/328), open draft; do not merge |
| Final implementation/test HEAD | `ed71d8a476c6d1d612aa08fd71637b2eb85d9d7c` |
| Natural CI snapshot HEAD | `f87cf2135330f643cda1fb3e91702f2dd09b640c` |
| PR #327 | Unchanged at `55f73a31e8f049a1e6d805154355917921bbd53b`; open draft |

The campaign closes hosted dynamic-runtime execution in Assembly and proves a bounded S3-written compiler pipeline. It adds an experimental, fail-closed QBE translator, but does not prove that QBE accepts or executes its output in this environment. No language syntax, stable backend registration, default backend, compiler default, or release surface changed.

## Phase A: Assembly Dynamic Runtime Parity

The original gap was missing runtime dispatch and a scalar-only Assembly value model: a dynamic call such as `i64_vector_new` reached ordinary function lookup and failed with `KeyError`. The repair routes registered built-ins through the existing IR dynamic-runtime implementation and gives Assembly registers/memory the existing dynamic values and reference cells. The verifier remains structural and independent from runtime execution.

The inventory test checks all 91 named entries in `DYNAMIC_BUILTIN_SIGNATURES` against the semantic builtin registry, Assembly verifier signatures, the shared emulator adapter, and native x86-64 runtime labels. The Assembly emulator now dispatches those registered built-ins and the generated composite-vector runtime signatures. Before this change, Assembly had no executable dynamic-builtin dispatcher.

Evidence:

- Eight source-compiled family programs compare IR and Assembly results: tryte, i64, and f64 vectors; bytes; text; integer map/set; text map; and composite vector.
- Mutation is observable through references in vector, text, map/set, and composite-vector operations.
- Negative capacity, out-of-bounds access, and invalid UTF-8 compare exception class and message between IR and Assembly.
- Five maturity workloads (ordering, hex encoding, CSV parsing, bounded VM, and Pebble compiler) compare Assembly with IR at O0 and O1.
- Static Assembly strings retain their established `sN` handle behavior. Only a dynamic builtin argument whose registered signature says `STRING` is resolved to literal contents at that runtime boundary.

`ASSEMBLY_DYNAMIC_BUILTIN_DISPATCH=PASS`, `ASSEMBLY_DYNAMIC_VALUE_MODEL=PASS`, `ASSEMBLY_MUTATION_PARITY=PASS`, and focused dynamic error parity passed. No Assembly-format change, heap redesign, ownership redesign, or verifier redesign was required. The natural Linux x86-64 CI run passed the native gate at CI snapshot HEAD `f87cf213…`; this is distinct from Windows-hosted IR/Assembly parity.

## Phase B: Pebble Compiler Architecture

The Pebble grammar remains unchanged. Its source implementation is S3 code and now has explicit stages:

`runtime text -> tokenizer -> parser -> indexed AST -> semantic validation -> tiny IR -> independent IR verifier -> bytecode emitter -> existing VM`

The AST uses parallel indexed vectors for node kind/value/children and statement roots. The parser materializes a six-node example AST. Semantic checking is a separate pass and preserves initialization/use and assignment-target checks. The tiny IR has six opcodes: constant, local load, local store, add, subtract, and return. Its S3 verifier checks opcode, IDs, definition/use state, local bounds, instruction shapes, and return form before the emitter runs. The emitter consumes verified IR; parsing does not emit bytecode directly.

Evidence:

- Five fixed valid and five fixed invalid programs preserve the original canary corpus.
- Six malformed IR cases are rejected, alongside a valid verifier case.
- Twelve unseen valid programs are generated deterministically with seed `20261004`; a test-only Python evaluator is compared with the S3 compiler and VM. Python does not participate in S3 compilation.
- Repeated compilation yields identical IR, Assembly, and generated x86 text.
- The fixed Pebble workload participates in the existing IR/Assembly parity test and Linux-native workload gate; Windows skips the native platform cases.

`PEBBLE_AST=PASS`, `PEBBLE_SEMANTIC_PASS=PASS`, `PEBBLE_IR=PASS`, `PEBBLE_IR_VERIFIER=PASS`, `PEBBLE_BYTECODE_EMITTER=PASS`, and fixed/generated valid and invalid canaries passed focused evidence. This establishes `COMPILER_WRITING_CAPABILITY=PROVEN_BOUNDED`, not a general compiler frontend, S3 self-hosting, or self-host readiness.

## Phase C: Experimental QBE Oracle

`QBE_BACKEND_STATUS=EXPERIMENTAL_ORACLE`. The translator is in `tools/qbe_oracle.py`, consumes the normal verified S3 IR, and invokes `verify_ir` before translation. It is not in stable backend registries or the normal CLI.

The deliberately limited subset is deterministic constants/moves for i64/f64 and internal trit values, i64/f64 comparisons and relations, scalar internal calls, jumps, exact `BRANCH3` dispatch for -1/0/+1, and scalar returns. i64 maps to QBE `l`; f64 maps to `d`; trit is only an internal `l` carrier whose verifier-bounded values are preserved by explicit -1/0/+1 control flow. Tryte has no V1 mapping. Checked i64 arithmetic, division, memory, records, references, dynamic values, external calls, and non-scalar ABI shapes fail closed.

Ten O0/O1 translations across five bounded programs are checked for determinism and structural content. Negative tests cover unsupported dynamic, aggregate/reference, tryte/trit ABI/result, checked arithmetic, and malformed verified IR. The native test harness is written to compare `execute_ir`, S3 Assembly execution, S3 x86-64 native execution, and QBE native execution when Linux x86-64, QBE, and a C compiler are available.

This Windows host has no QBE executable or usable Linux native toolchain/WSL distribution. No binary was downloaded or built. Consequently:

- `QBE_TRANSLATOR=PASS_STRUCTURAL` and `QBE_IL_DETERMINISTIC=PASS`.
- `QBE_NATIVE_EXECUTION=BLOCKED_TOOLCHAIN`.
- `QBE_DIFFERENTIAL_NATIVE=NOT_PROVEN` and QBE IL acceptance by the QBE executable is not evaluated.
- QBE native performance and backend-validation claims are absent.

The next QBE step is to run the existing bounded three-way native corpus on a suitable Linux x86-64 host with a pinned QBE revision. Do not expand the subset before that evidence exists.

## Validation and Remaining Failures

Latest focused command covered Assembly dynamic parity, Assembly emulator, maturity workloads, dynamic runtime families, and QBE translator tests: `140 passed, 29 skipped`. `python -m compileall -q bootstrap tests tools` passed. `git diff --check` passed.

The required Windows full suite terminated with exit 1: `4345 passed, 365 skipped, 6 failed, 572 subtests passed`. The six failures comprise:

1. Five tests in `tests/test_s3_16_public_dataset_agent_kernels.py` fail the same byte hash assertion. `core.autocrlf=true` converts the fixture's single final LF to CRLF in the working tree. The Git blob SHA-256 is the manifest's expected `daf23bc747d7d483391efad709b47ead8854bf2f70405829b2833cd0fee2a924`; the CRLF checkout hash is `afb74dc054c8eabed4faaec1312aba07c3aea6cd2e2d6220173644a01363f54b`. `git diff` reports the fixture and manifest unchanged. The fixture was not modified.
2. `tests/test_reliability_runner_v2.py::test_r1_timeout_kills_descendant_process_tree` failed once in the loaded full run, then passed when run alone. The reliability runner and its test were not changed; this remains classified as an intermittent Windows scheduling/process-tree test result, not silently waived.

The QBE native test body was subsequently strengthened to include S3 x86-64 execution in the three-way differential. Its focused collection/structural suite passed (`36 passed, 10 skipped` with static-text regressions); the native branch remains skipped here because the toolchain is absent.

The natural CI snapshot for HEAD `f87cf2135330f643cda1fb3e91702f2dd09b640c` passed all 13 checks, including the three Python unit matrices, renderer, benchmark, native x86-64, numeric-domain closure, differential, packaging, supply chain, and Docker capability gates. A subsequent report-only commit changes the PR head; do not transfer this earlier green result to that later SHA. The exact final PR head must be checked separately, and its result is captured by the PR checks and final campaign report.

The V1 normal-compiler scale evidence remains unchanged: up to 53,319 source bytes, 100 functions, 3 modules, 6,884 AST nodes, 1,668 IR blocks, and 8,175 IR instructions. No new performance measurements or claims were made.

## Self-Host Re-entry and Release Policy

The existing V1 audit against `docs/selfhost/REENTRY_CRITERIA.md` is unchanged: Gate 1 PARTIAL; Gate 2 FAIL; Gate 3 PARTIAL; Gates 4-9 FAIL; Gate 10 NOT_EVALUATED; Gates 11-13 PARTIAL; Gate 14 FAIL. Pebble is a bounded independent compiler canary and does not upgrade any self-host gate.

`SELFHOST_RESEARCH_STATUS=PAUSED`, `SELFHOST_REENTRY_AUTOMATIC=NO`, `STAGE1_V4_AUTHORIZED=NO`, `SELFHOST_READY_FOR_REENTRY=NO`, and `DEFAULT_COMPILER=PYTHON`. The production x86-64 backend remains authoritative. QBE is experimental only. PR #328 remains Draft; no merge, tag, release, default-backend promotion, self-host restart, or shutdown is authorized by this report.

## Assessment

The campaign closes hosted Assembly execution for the currently registered dynamic runtime families and proves a bounded compiler-writing architecture. QBE has a deterministic, fail-closed structural translator and a prepared native differential harness, but no QBE executable evidence exists. The local Windows full suite is not green for the two explicitly classified existing/environmental issues above; the natural Linux CI snapshot at `f87cf213…` passed. The report-only commit following that snapshot requires its own terminal natural CI result. QBE native execution remains a separate blocked/partial result unless a qualified Linux toolchain becomes available.
