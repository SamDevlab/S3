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
