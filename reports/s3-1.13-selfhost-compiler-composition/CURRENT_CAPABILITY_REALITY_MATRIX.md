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
| Full self-hosting / Stage2 / Stage3 | `MISSING` | Self-source exceeds the Stage1 source bound and includes unsupported constructs; self-emission was deferred, and Stage2/Stage3 were not attempted. |
| Production/default compiler replacement | `MISSING` | Python remains the reference and package default; the Stage1 compiler is experimental and unmerged. |
| Repository-wide final regression gate | `PASS_REMOTE_CI` | The Windows full suite passed with 4,284 passed, 349 skipped, 0 failed. After verifier compatibility and Zig cache fixes, code HEAD `b7844b6fc77ae6e995992e9f032292bd693b26e6` passed every GitHub Actions job, including unit jobs on Python 3.11/3.12/3.13 and native x86-64. The exact local Linux full-suite command was not rerun after the fixes, so that historical transcript remains separate. |

`FIRST_REAL_STAGE1_SOURCE_TO_ARTIFACT_COMPILER_PATH=YES` is the precise
candidate capability claim. The recovered S3 source receives bounded S3 source,
lowers to `NativeIR`, verifies, and emits S3 Assembly without Python semantic,
lowering, verifier, or emitter fallback. A separately built standalone Stage1
executable artifact and its bit-reproducible build recipe were not recovered,
so `STANDALONE_STAGE1_EXECUTABLE_ARTIFACT=NOT_PROVEN` and `FULL_SELFHOST=NO`. See `STAGE1_COMPOSITION_PROGRESS.md` and
`STAGE1_ARTIFACT_MANIFEST.json` for the bounded scope and evidence.
