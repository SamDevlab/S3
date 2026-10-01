# S3 1.13 Gate Zero: Capability Reality

Base: `5b4b8f12dc9aea94fab751136d98112a6e5c0098` (`origin/main`, 2026-09-28).
PR #326 (S3 1.12) and S3-Benchmarks PR #30 are merged. This inventory is
source/test based; roadmap labels are not treated as implementation evidence.

| Capability | Classification | Evidence and boundary |
|---|---|---|
| Production source compiler | `PRODUCTION_REFERENCE` | `bootstrap/s3/pipeline.py`, `lowering.py`, `codegen.py`; Python owns the complete production compile path. |
| Independent hosted generic frontend | `HOSTED_GENERIC` | `bootstrap/s3/frontend_control_plane.py`; source enters the hosted whole-program phases. |
| S3-native bounded lexer | `S3_NATIVE_EXECUTABLE` | `selfhost/substrate/generic_lexer_state.s3`; `tests/test_native_frontend_slice.py`; returns token-derived observations, not a compiler token artifact API. |
| S3-native bounded parser | `S3_NATIVE_EXECUTABLE` | Same source and test; parses a limited function/expression/statement/call/while subset but exports digests, not a durable syntax tree for a consumer. |
| S3-native semantic execution | `S3_NATIVE_EXECUTABLE` | `native_semantic_execution.s3` and `native_typed_value_protocol.s3`; executes/evaluates source and returns values. It does not create compiler semantic identities or IR. |
| `IRProgramShape` | `S3_NATIVE_SHAPE_ONLY` | `generic_ir_program.s3`; parallel-vector record plus anchor; no parser/lowerer/verifier/emitter path consumes it. |
| `NativeIR` verifier | `S3_NATIVE_EXECUTABLE` | `verifier_kernel.s3`, `tests/test_generic_syntax_ir_verifier.py`; verifier consumes S3-constructed test records. The source parser does not populate these records. |
| Semantic identity/type arena/compiler context | `S3_NATIVE_SHAPE_ONLY` | `semantic_environment.s3`, `type_arena.s3`, `compiler_context.s3`; declarations and links are represented but no source compiler pass populates them. |
| Whole-program control plane | `S3_NATIVE_SHAPE_ONLY` | `whole_program_context.s3`, `program_registry.s3`, `phase_orchestrator.s3`; S3 source is representational. Hosted Python composition is executable but requires prepared artifacts for verification/output. |
| S3 `OutputSink` | `S3_NATIVE_SHAPE_ONLY` | `output_sink.s3` contains state/result records and an anchor only. |
| Hosted `OutputSink` | `HOSTED_GENERIC` | `bootstrap/s3/compiler_substrate.py`; bounded transactional byte output. `whole_program.py` only appends caller-prepared bytes. |
| S3 Assembly frontend | `S3_NATIVE_EXECUTABLE` | `selfhost/assembly/assembly_{tokenizer,parser,frontend}.s3`; consumes bounded text and summarizes parser events, not an emitter. |
| S3 Assembly emitter | `MISSING` | `selfhost/assembly/` and `examples/self_hosting/` contain parser and renderer experiments; renderer examples are fixture/event models, not a general verified-IR-to-text emitter. |
| Generic source-to-canonical-IR lowering in S3 | `MISSING` | `whole_program.py` explicitly skips lowering for prepared artifacts; real source fails closed at semantic analysis. No S3 path converts parsed source into IR. |
| Connected S3 source → IR → S3 verifier → emitted artifact | `MISSING` | `tests/test_whole_program_composition.py` asserts real source fails with `S3E_SEMANTIC_PHASE_UNAVAILABLE`; prepared-artifact success is marked `test_artifact_input=True`. |
| Current self-host docs at Gate Zero | `STALE_DOCUMENTATION` | At the recorded base, `docs/selfhost/STATUS.md` retained historical blocker labels and `docs/roadmap/ACTIVE_TRACK.md` said 1.12 was unmerged although PR #326 was merged. Current status is reconciled below; the dated Gate Zero findings remain historical. |

## Architectural finding

The prompt's gap is independently confirmed. The source parser and evaluator
are separate executable slices; the native verifier receives fixture-built
`NativeIR`; generic shape and hosted generic IR are separate representations;
the whole-program source path reaches hosted registration/type but fails at
semantic analysis. No complete equivalent Stage1 compiler pipeline exists in
this `main`, so `CAMPAIGN_PREMISE_SUPERSEDED=NO`.

## Canonical IR decision

`SELFHOST_CANONICAL_IR_DECISION=REUSE_NATIVE_IR`

`NativeIR` is selected because it is the only S3-side representation already
consumed by the independent S3 verifier. Extend that owner with the minimum
source/compiler data required by the frozen subset (value types, immediate
payloads, and function parameter/result metadata), then make the S3 lowerer,
verifier, and emitter consume the same record. `IRProgramShape` remains a
shape-only historical artifact and must not become an intermediate adapter or
a third model. Any needed schema extension must preserve direct monotonic i64
IDs and deterministic vector order.

## `STAGE1_SUBSET_V1` (frozen for this campaign)

- Top-level function declarations with `i64` parameters and `i64` result.
- Nonnegative i64 literals, identifier reads, parentheses, `+` and `*`.
- Immutable local bindings initialized from an expression.
- Calls with positional arguments to functions declared in the same program.
- A function body ending in exactly one `return` expression.
- Whitespace/comments supported by the existing scanner; no filesystem input.
- Explicitly excluded: f64, trit-valued source expressions, mutation,
  conditionals/match, loops, records, arrays, references, generics, imports,
  async, and extern declarations.

Resource limits: `MAX_SOURCE_BYTES=4096`, `MAX_TOKENS=1024`,
`MAX_SYNTAX_NODES=63` per expression while reusing the current packed
expression cursor/node codec (base 64, with one value reserved for failure),
`MAX_FUNCTIONS=16`, `MAX_BLOCKS=16`,
`MAX_IR_VALUES=512`, `MAX_IR_INSTRUCTIONS=512`, `MAX_OUTPUT_BYTES=16384`.
Every capacity failure is an explicit phase error; output is committed only
after verify and emit both succeed.

The subset exercises multiple functions, typed parameters, storage/value
identity, arithmetic, calls, and returns without pretending that the current
digest parser is already a reusable AST. No Stage1 implementation tests,
lowerer, or emitter are claimed by this Gate Zero artifact.

## Campaign delta: local S3 1.13 candidate (2026-09-28)

This section describes the unmerged campaign candidate, not `origin/main`.
It supersedes the Gate Zero classifications only for this local branch.

| Capability | Candidate classification | Evidence and boundary |
|---|---|---|
| S3-written source-to-artifact compiler | `S3_NATIVE_PIPELINE_CONNECTED` | `selfhost/compiler/stage1_compiler_v1.s3` scans and parses the frozen subset, lowers to `NativeIR`, invokes the S3 verifier, emits S3 Assembly and commits bounded output. |
| First real Stage1 artifact | `S3_NATIVE_EXECUTABLE` | Seven implementation cases and one post-freeze unseen source produced artifacts; the unseen artifact parsed and executed to the Python reference result. |
| Persisted Stage1 compiler artifact (2026-09-29 continuation) | `PROVEN_HOSTED_IR_ARTIFACT` | A trusted Python build persists verified S3 IR; a fresh Python process executes it through the generic IR emulator without importing the reference source compiler, compiles seven unseen supported sources, and emits verified Assembly. This is not a standalone native binary. |
| Bounded self-source / full self-hosting / Stage2 / Stage3 | `NOT_PROVEN` | AST inventory found 0/50 Stage1 functions with the current all-`i64` signature; the 95-byte original `stage1_emission_value_count` vector-reference helper is rejected at signature registration (phase 3/code 25), and `stage1_empty_ir` is rejected at its `NativeIR` result record. The full source is 139,740 bytes versus the 4,096-byte Stage1 input bound. Stage2/Stage3 were not attempted. |
| Production/default compiler replacement | `MISSING` | Python remains the reference and package default; the Stage1 compiler is experimental and unmerged. |
| Complete local suite for this candidate | `PASS_WINDOWS_FULL_SUITE` | `python -m pytest` on the complete local working tree based on `7bfb8edca51d238b7d6ecd245c635fd106790c0c`: 4,309 passed, 349 skipped, 572 subtests passed, exit 0. The unchanged canonical Stage1 source SHA-256 is `894a76a5c206b8e86b3149483b4bc2ad6904a4f6810aac62d1e235c1fd46a44c` (139,740 bytes). |
| Natural remote CI for the artifact candidate | `PASS_12_OF_12` | Implementation commit `1f89bfa043cb81b6b5da1ebfb19a031ecce74a17` passed all 12 PR checks, including Python 3.11/3.12/3.13 unit shards, renderer, benchmark smoke, differential, Docker, native x86-64, numeric-domain, package, security/supply-chain, and SSA verification. The prior `b7844b6fc77ae6e995992e9f032292bd693b26e6` result remains historical evidence. The exact local Linux full-suite command was not rerun. |

`FIRST_REAL_STAGE1_SOURCE_TO_ARTIFACT_COMPILER_PATH=YES` remains the precise
source compiler claim. The recovered S3 source receives bounded S3 source,
lowers to `NativeIR`, verifies, and emits S3 Assembly without Python semantic,
lowering, verifier, or emitter fallback. The continuation separately proves a
reproducible persisted-IR build and independent invocation from the reference
source compiler; the runtime still depends on Python and `ir_emulator`. This
does not prove a native Stage1 executable, bounded self-source compilation, or
full self-hosting. See `STAGE1_COMPOSITION_PROGRESS.md`,
`STAGE1_ARTIFACT_MANIFEST.json`, and
`STAGE1_STANDALONE_BOOTSTRAP_REPORT.md`.

## Current local continuation: typed Stage1 V2 (2026-09-30)

This is a local, unmerged continuation on
`feat/s3-1.13-selfhost-compiler-composition`, based on remote HEAD
`6be3ed1b4f2ba39e94e5da58b88373a2910a5f09`. The V1 source remains frozen at
SHA-256 `894a76a5c206b8e86b3149483b4bc2ad6904a4f6810aac62d1e235c1fd46a44c`
(139,740 bytes). The exact per-function inventory is
`STAGE1_REPRESENTABILITY_MATRIX_V2.json`; the V1 matrix above remains historical.

| Capability | Current V2 evidence | Boundary |
|---|---|---|
| Explicit supported parameter types | `i64` and immutable `&vector<i64>`; return type `i64` or `trit`; 14/50 canonical signatures fit after typed comparisons. | Mutable references, scalar references, records, and other result types are not represented by this V2 profile. |
| Typed vector calls | `vector_get<i64>` and `vector_len<i64>` lower to typed `i64_vector_get` / `i64_vector_len`; argument shape and local call signatures are checked. | No V2 `vector_set`, `vector_push`, mutable vector parameter, or vector return lowering. |
| Straight-line mutable scalar | A local declared `mut` may be rebound to a new i64 SSA value; the compiler tracks mutability and rejects rebinding immutable locals. | This is not a reference store, memory operation, loop-carried value, or CFG phi. |
| Real canonical Stage1 source functions | Five functions are body-representable, dependency-closed, and covered by the source-compilation test: `stage1_emission_value_count`, `stage1_emission_instruction_count`, `stage1_emission_value_id`, `stage1_emission_operand_id`, and `stage1_emission_instruction_field`. | This does not mean the full V1 source or a standalone compiler was self-compiled. |
| CFG and mutable storage | `NativeIR` has block and terminator records; typed `<` and `==` lower to `TREL` with a `trit` result and pass verifier plus hosted Assembly execution checks. | Conditional branch/jump construction, multi-block emission, CFG-carried mutation, `while`, and `switch`/match are not closed. |

The initial V2 baseline distinguished signature, body, dependency closure, and
tested self-compilation at `13/50`, `5/50`, `5/50`, and `5/50` respectively.
After typed comparisons, the current snapshot is `14/50` signatures supported,
with the same `5/50` bodies representable, dependency-closed, and tested through
Stage1. All 38 canonical
functions with reference parameters use vector targets (108 parameters total:
98 immutable, 10 mutable); 23 such functions use `vector_get`/`i64_vector_get`,
11 use vector length queries, and 12 use mutating vector builtins. The source
contains no scalar dereference or dereference-store function. This is why the
remaining reference frontier is specifically mutable vector operations and
control-flow propagation, not a generic scalar-pointer model.

`stage1_output_chunk` remains an informative next target: its signature and
vector reads fit, and `<`/`==` are now typed and executable through the hosted
Assembly Emulator. Its remaining direct body blockers are `while`, nested
ternary match, and mutation inside control flow. The typed-comparison increment
does not increase the canonical representable count. The next substantive
implementation boundary is general multi-block CFG construction, verification,
and emission, not another per-function helper.

Focused evidence for this local change: the representability tests passed (9
tests). The Stage1 compiler module completed with exit code 0 (36 collected,
35 passed, one platform skip). The four pre-existing dirty golden JSON files
were not edited. No full suite, final-head CI, commit, push, Ready transition,
merge, Stage2, or Stage3 is claimed for this local diff. Python remains the
default compiler; full self-hosting remains unproven.

## V5 target audit: mutable storage and control flow (2026-09-30)

This records the state before the V6 typed-comparison checkpoint below.

The V2-aware analyzer was regenerated against the frozen 50-function V1
source. It reports 13 supported signatures, 5 body-representable functions,
5 dependency-closed functions, and the same 5 self-compile-proven functions.
Those five cover 819 source bytes (0.586% of the 139,740-byte V1 source). The
regenerated matrix is `STAGE1_REPRESENTABILITY_MATRIX_V2.json` (236,067 bytes,
SHA-256 `95444ecc56611af4593c4614c59ba23840253ab1a151052896a6881b7b65e51b`).

`stage1_output_chunk` is signature-supported and has no local V1 callees. Its
external operations `vector_get<i64>` and `vector_len<i64>` are already
supported. Its exact remaining direct body blockers are integer `<` and `==`
lowering, mutation inside control flow, and `while` plus nested `match`
statement lowering. It remains not representable and not self-compiled.

The limiting boundary is the shared compiler substrate, not an isolated
statement-parser case. The self-host `NativeIR` record has block, target, and
memory arrays, and its verifier recognizes branch-shaped records when supplied
directly. However, the V2 construction API does not provide validated typed
append operations for comparison, conditional branch/jump, or memory
allocation/load/store. The V2 body compiler is a straight-line statement
scanner, and its Assembly emitter serializes one block and has no validated
multi-block/memory emission path. The Python `GenericIR` implementation has
these broader concepts, but the S3 V2 candidate does not consume that Python
representation; substituting it would not be self-hosted lowering.

Consequently, `MUTABLE_STORAGE_END_TO_END=NO`, `WHILE_END_TO_END=NO`,
`MATCH_END_TO_END=NO`, `STAGE1_OUTPUT_CHUNK_BODY_REPRESENTABLE=NO`, and
`STAGE1_OUTPUT_CHUNK_SELF_COMPILED=NO`. The next implementation unit is a
shared, typed multi-block/memory IR construction and emission path, including
verifier contracts, before V2 can correctly lower the target's loop-carried
state. No function-specific lowering or unsupported-syntax acceptance was
added. The V1 SHA remains unchanged. The four pre-existing golden JSON files
remain outside this campaign. Full suite, final-head CI, commit, push, PR
metadata changes, Stage2, and Stage3 remain unclaimed.

For this checkpoint, `tests/test_stage1_representability.py` passed 9 tests;
`tests/test_s3_1_13_stage1_compiler.py` completed with exit 0 (36 collected, 35
passed, one platform skip). Targeted `compileall`, JSON parsing plus
byte-for-byte regeneration comparison, and `git diff --check` passed. PR #327
is OPEN/DRAFT/MERGEABLE at remote HEAD `6be3ed1b4f2ba39e94e5da58b88373a2910a5f09`;
its 13/13 checks validate that published HEAD only and do not validate this
uncommitted local diff. No full suite or benchmark was run.

## V6 typed-comparison checkpoint (2026-09-30)

The initial V2 analyzer snapshot was `13/50` signature-supported and `5/50`
body-representable, dependency-closed, and self-compile-proven. After adding
typed scalar `==` and `<`, the deterministic current matrix reports `14/50`,
`5/50`, `5/50`, and `5/50`. The extra signature is a `trit` result; no
representable canonical function was added. The five proven functions and
their 819 source bytes (0.586%) are unchanged. V1 remains frozen at SHA-256
`894a76a5c206b8e86b3149483b4bc2ad6904a4f6810aac62d1e235c1fd46a44c`.

For both relations, Stage1 V2 checks compatible `i64` operands, emits NativeIR
relation opcode 11 with result type `trit`, passes the verifier, emits `TREL`,
and matches reference semantics in the hosted Assembly Emulator. Mixed scalar
types and relation codes outside 0..5 are rejected. The regenerated
`STAGE1_REPRESENTABILITY_MATRIX_V2.json` is the `AFTER_COMPARE` snapshot. No
multi-block branch/jump builder or emitter, CFG-carried mutation, memory
operation, native comparison qualification, `while`, or `match` lowering is
claimed. Existing remote CI applies to the published HEAD, not this local diff.

## V6 typed CFG and memory checkpoint (2026-10-01)

This section supersedes the preceding paragraph's CFG/memory status. The
current uncommitted NativeIR candidate now has typed branch and jump
construction, block-local terminator validation, target validation,
deterministic multi-block emission, typed memory declarations/load/store,
and hosted Assembly Emulator coverage. A three-way CFG fixture writes a
distinct value in each arm, jumps to a join, loads the selected value, and
returns it. CFG graph queries cover reachability and predecessor counts; a
cyclic backedge is accepted, an orphan block is reported unreachable, and a
cross-block direct SSA use is rejected with the value-scope diagnostic.

Cross-block SSA values are not currently a supported value-flow mechanism:
the verifier conservatively permits parameter values and same-block
definitions, while mutable values that must cross blocks use explicit memory
slots. This is not a dominator computation or phi/block-argument model.
`NativeIR` CFG/memory capability therefore must not be confused with
Stage1-source lowering: the V2 body compiler still scans a straight-line
function body and has no `while`, `switch`/match, nested-control mutation, or
loop-carried-storage lowering.

The freshly regenerated V2 matrix remains 50 functions: 14 signatures
supported, 5 bodies representable, 5 dependency-closed, and 5 self-compile
proven. The five functions and 819 self-compiled source bytes (0.586%) are
unchanged. `stage1_output_chunk` remains signature-supported, but not
body-representable, dependency-closed, or self-compiled; its current analyzer
blockers are `WhileStatement`, `SwitchStatement`, and
`mutable_assignment_in_control_flow`. Its local-call list remains empty.

Validation on the current local tree: the focused representability, NativeIR
verifier, and Stage1 compiler modules completed with exit 0; the separate SSA,
SSA-validation, memory-SSA, and memory-dominance test group completed with
exit 0; `python -m compileall bootstrap/s3`, matrix JSON parsing, and
`git diff --check` passed. The Linux x86-64 native test is platform-skipped on
this Windows host, so native CFG/memory execution is not claimed. No full
suite or benchmark was run. The four unrelated dirty golden JSON files remain
excluded. The V1 source hash remains unchanged. This local candidate is not
committed or pushed; remote CI still validates only the published PR #327
HEAD, not these changes.

## V6 loop-carried memory CFG fixture (2026-10-01)

The focused Stage1 compiler tests now construct a generic five-block CFG with
an `i64` memory slot: entry initializes the counter, the header loads it and
branches on typed `i < 3`, the body loads/increments/stores and jumps back to
the header, and the exit loads and returns the final value. A distinct neutral
dispatch block keeps all three `TBR3` targets valid and distinct. The V2
verified emitter produces the Assembly artifact; the Assembly Emulator returns
`3`. Two independently rebuilt artifacts compare byte-for-byte and by
SHA-256. This proves loop-carried mutable storage through explicit NativeIR,
verification, multi-block emission, and hosted execution. It does not prove
source-level `while` lowering or Stage1 compilation of `stage1_output_chunk`.

The focused local group passed all four tests covering this fixture, the
existing three-way CFG execution, CFG builder/verifier contracts, and typed
memory builder/verifier contracts. The corresponding Linux x86-64 native test
is present but has not yet been validated on this Windows host; native parity
remains pending current-head Linux CI. The V2 source-body scanner still passes
one block ID through recursive statement compilation, and mutable locals are
tracked as replacement SSA-like value IDs. It has no structured loop-body
boundary/continuation model or storage-backed source binding, so general
source-level `while` lowering remains a concrete implementation frontier.
The canonical V1 analyzer remains at 14 signatures, 5 representable bodies,
5 dependency-closed functions, and 5 proven self-compiled functions;
`stage1_output_chunk` remains blocked by `WhileStatement`, `SwitchStatement`,
and `mutable_assignment_in_control_flow`. No full suite or benchmark was run.
The four pre-existing golden JSON changes were not touched or staged, and the
Stage1 V1 hash remains unchanged.
