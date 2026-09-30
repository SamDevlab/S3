# S3 1.13 Stage1 Standalone Bootstrap and Self-Host Frontier

Date: 2026-09-29
Branch: `feat/s3-1.13-selfhost-compiler-composition`
PR: #327 (OPEN, DRAFT; not ready or merged)

## Result

The candidate reaches **Level 2: independently invoked hosted Stage1**. A
trusted Python build persists the canonical Stage1 S3 implementation as
verified S3 IR. A fresh process loads that IR, compiles unseen programs in the
implemented subset, emits S3 Assembly, and verifies the output without
importing the Python source compiler. Python remains required to build and run
the artifact. This is not a native executable and does not establish a
self-compiling Stage1.

The next frontier is a type-aware Stage1 compiler/NativeIR design. No complete
function from `stage1_compiler_v1.s3` has a signature in the current Stage1
input subset; the actual function-slice probe is rejected during signature
registration. Stage2 and Stage3 were not attempted.

## Pipeline and Commands

Canonical build:

```text
python -m bootstrap.s3.stage1_artifact build --output-dir build/selfhost/stage1
```

The `s3-stage1` package entry point exposes the same `build` and `compile`
commands. The build reads these canonical S3 modules:

```text
selfhost/substrate/generic_lexer_state.s3
selfhost/substrate/verifier_kernel.s3
selfhost/substrate/output_sink.s3
selfhost/compiler/stage1_compiler_v1.s3
```

It adds a deterministic inline S3 entry wrapper, then invokes
`bootstrap.s3.pipeline.compile_sources`. The trusted Stage0 pipeline parses and
resolves modules, performs semantics/lowering/optimization, and generates an
`IRProgram` and an in-memory `AssemblyProgram`. The build serializes and
round-trip verifies the IR, validates the Assembly structure, and writes the
IR, hashes, source manifest, and provenance. The build does not persist a
rendered `.s3asm` for the Stage1 implementation; it persists a 197-byte summary
containing the canonical serialized in-memory Assembly-structure size/hash.

Independent invocation:

```text
python -m bootstrap.s3.stage1_artifact compile build/selfhost/stage1 input.s3 -o output.s3asm
```

`compile_stage1_file` reads a bounded source file. `compile_stage1_bytes`
verifies/deserializes `stage1.ir.json`, invokes the compiled S3 entry through
`bootstrap.s3.ir_emulator.execute_ir`, decodes the result envelope, parses the
emitted Assembly, validates it with `AssemblyVerifier`, and atomically writes
the output. Runtime does not read the Stage1 source or call `compile_sources`.
The Stage1 S3 code performs its own source scanning, parsing, lowering,
verification, and Assembly emission for its supported subset.

## Artifacts and Trust Base

| Object | Exists / persisted | Reproducible evidence | Invocation and dependencies |
|---|---|---|---|
| Stage1 source | Yes; canonical S3 file | Raw SHA and bytes match recovery provenance | Source input to Stage0 build; not read during artifact invocation |
| Stage1-generated S3 Assembly | Yes for compiled inputs; written to the requested output path | Seven unseen supported inputs passed; output parsed and validated | S3 Assembly, not native code; execution in tests used the Python Assembly emulator |
| Runnable Stage1 representation | Yes; serialized `stage1.ir.json` | Cold-process A/B byte equality and SHA below | Python `ir_serialization`, generic IR emulator, dynamic-vector runtime, Assembly parser and verifier required |
| Standalone Stage1 compiler artifact | Yes; deterministic IR bundle plus manifest/provenance | IR and metadata files match across builds | Independently invocable in a fresh Python process; no Python reference source-compiler import; not a native standalone executable |

| Component | Build time | Post-build invocation | Role |
|---|---:|---:|---|
| Python | Required | Required | Trusted build and hosted runtime/CLI |
| Python source compiler (`pipeline`, lexer, parser, semantics, lowering, codegen, module/whole-program compiler) | Required | Not imported | Stage0 build only |
| Stage1 and substrate S3 source | Required | No source read | Compiled into the persisted IR |
| S3 IR deserializer/verifier | Required | Required | Trusted artifact validation |
| Generic S3 IR emulator and dynamic vectors | Required | Required | Executes Stage1's serialized IR |
| S3 Assembly parser/verifier | Required | Required | Validates Stage1 output |
| Native backend, assembler, linker, Zig | Not used | Not used | No native Stage1 executable was generated |
| OS filesystem | Required | Required | Input/output file boundary |

The fresh-process test installs an import blocker before process startup for
the Python source compiler modules and verifies that the Stage1 invocation
still succeeds. It does not remove Python or the generic IR runtime. Therefore:

```text
STANDALONE_PROCESS_ISOLATION=PASS_WITH_HOSTED_PYTHON_RUNTIME
POST_BUILD_PYTHON_DEPENDENCY=YES
POST_BUILD_REFERENCE_COMPILER_DEPENDENCY=NO
HOST_SEMANTIC_FALLBACK=NO
HOST_LOWERING_FALLBACK=NO
HOST_EMITTER_FALLBACK=NO
NATIVE_STAGE1_EXECUTABLE=NO
```

“No fallback” here refers to compiler semantics, lowering, and emission. The
runtime is still Python, including IR execution and independent Assembly
validation.

## Reproducibility and Input Evidence

Two separate build output directories produced the following identical
identities:

```text
SOURCE_SHA256_A=894a76a5c206b8e86b3149483b4bc2ad6904a4f6810aac62d1e235c1fd46a44c
SOURCE_SHA256_B=894a76a5c206b8e86b3149483b4bc2ad6904a4f6810aac62d1e235c1fd46a44c
SOURCE_BYTES=139740

ASSEMBLY_STRUCTURE_SHA256_A=35c03eb405e5e9bb3c7ec025d89a31cba2b961a5d3551bae43945aae6bbea4e2
ASSEMBLY_STRUCTURE_SHA256_B=35c03eb405e5e9bb3c7ec025d89a31cba2b961a5d3551bae43945aae6bbea4e2
ASSEMBLY_STRUCTURE_BYTES=25393812
ASSEMBLY_SUMMARY_FILE_SHA256_A=6b701b7436c8e0f1f4591f26c3690020249e3229bd4cb9318a3a5223c74593c5
ASSEMBLY_SUMMARY_FILE_SHA256_B=6b701b7436c8e0f1f4591f26c3690020249e3229bd4cb9318a3a5223c74593c5

STAGE1_IR_SHA256_A=17813e6a69d7429b25c97d66b98e74f16815ab8d0cf743f0221ee0f5b6f712a8
STAGE1_IR_SHA256_B=17813e6a69d7429b25c97d66b98e74f16815ab8d0cf743f0221ee0f5b6f712a8
STAGE1_IR_BYTES=25012499
MANIFEST_SHA256_A=9f8abe7ce75637859ff2508cf5c0bf41cc749be976f425723e7f6eb5f28494b1
MANIFEST_SHA256_B=9f8abe7ce75637859ff2508cf5c0bf41cc749be976f425723e7f6eb5f28494b1
HASHES_FILE_SHA256_A=25d1d4cf9b2690263db0a0ca218f8f4cb2a14b679255e1b96930488369a833c8
HASHES_FILE_SHA256_B=25d1d4cf9b2690263db0a0ca218f8f4cb2a14b679255e1b96930488369a833c8
```

The Assembly identity above is the canonical JSON serialization of the
in-memory `AssemblyProgram`, not a rendered `.s3asm` file. Accordingly,
Assembly-structure bit reproducibility is proven; a Stage1-build Assembly-text
artifact was not produced. The persisted final Stage1 artifact is the S3 IR
file. Historical binary reproducibility remains unresolved because no separate
original executable artifact survived recovery.

The existing unseen-input corpus contains seven supported programs. It covers
integer literals, arithmetic, immutable locals, multi-function calls,
forward references, nested calls, and positional arguments. A fresh process
compiled each, wrote Assembly, and the parent independently parsed/verified
and executed it; Stage1 and reference results agreed. A separate mixed-call
probe also agreed (`83`).

The expanded negative frontier corpus has seven programs accepted by the
reference compiler and rejected deterministically by Stage1: signed literal,
mutable local, comparison/trit result, match branch, while loop, vector
operations, and record construction/projection. The older invalid-input corpus
continues to cover unresolved symbols, duplicate bindings, call arity, missing
return, unreachable code, and malformed expressions. Rejection is not counted
as successful feature support.

## Stage1 Source Inventory and Representability

The S3 parser reports:

```text
STAGE1_SOURCE_LINES=2843
STAGE1_NONEMPTY_LINES=2783
STAGE1_FUNCTION_COUNT=50
STAGE1_RECORD_COUNT=9
STAGE1_RECORD_FIELDS=51
STAGE1_IMPORT_COUNT=41
STAGE1_CALL_COUNT=894
STAGE1_MATCH_COUNT=172
STAGE1_WHILE_COUNT=29
STAGE1_RECORD_CONSTRUCTOR_COUNT=30
STAGE1_FIELD_ACCESS_COUNT=174
STAGE1_REFERENCE_TYPE_NODES=108
STAGE1_ADDRESS_OF_NODES=304
```

| Construct | Stage1 source use | Current Stage1 source compiler input support |
|---|---:|---|
| `i64` | Yes | Supported in the bounded source subset |
| `trit` | One function result and many match conditions | Function result signatures outside current subset |
| Dynamic `vector<i64>` | Yes; 14 functions contain vector types | Unsupported in target signatures and value lowering |
| Records / aggregates | 9 records, 51 fields, 30 constructors | Unsupported in target source input |
| References / address-of | 108 reference type nodes, 304 address-of expressions | Unsupported in target signatures/expressions |
| `match` / structured branch | 172 match statements | Unsupported in target body subset |
| `while` | 29 loops | Unsupported in target body subset |
| Function calls | 894 call expressions; 41 imports | Calls among supported `i64` functions work; imported/builtin and aggregate calls are outside the subset |
| Mutation | 138 assignments | Unsupported in target body subset |
| Strings | No string-literal AST nodes; source/output text is byte vectors | Not needed as a string primitive by the current Stage1 source |
| Fixed arrays / indexing / slices | No fixed-array, index, or slice AST nodes in this file | Not used in this Stage1 source |
| Raw pointers / enums | None | Not used |
| File I/O | None in the S3 module | Supplied by the Python CLI boundary |
| Error handling | Status/phase/error fields and result records | Result-record model is outside the current target subset |
| Recursion | Used by parameter-name helper recursion | General recursive calls are not demonstrated by the Stage1 target |

The target parser accepts only `i64` parameter and result type codes. Measured
against all 50 complete function declarations:

```text
SELFHOST_FUNCTIONS_TOTAL=50
SELFHOST_FUNCTIONS_COMPILE_NOW=0
SELFHOST_FUNCTION_PERCENT=0%
SELFHOST_SOURCE_BYTES_TOTAL=139740
SELFHOST_SOURCE_BYTES_COMPILE_NOW=0
SELFHOST_SOURCE_PERCENT=0%
```

Function-attributed source spans total 135,088 bytes (from each function start
to the next function start, including separator whitespace); the remaining
4,652 bytes are module/import/record declarations and other prefix material.
All 50 function signatures are outside the current all-`i64` signature gate.

## First Self-Source Target and Blocker Graph

```text
FIRST_SELF_SOURCE_TARGET=stage1_emission_value_count
WHY_SELECTED=95-byte original helper; i64 result, one read-only vector parameter, one vector_get, no record result or control flow
SELF_SOURCE_PROBE_BYTES=127
SELF_SOURCE_PROBE_RESULT=REJECTED
SELF_SOURCE_DIAGNOSTIC=phase 3, error code 25 (function-header registration)
STAGE1_SELF_SOURCE_SLICE_COMPILED=NO
```

The helper was copied byte-for-byte into a bounded noncanonical program with a
trivial `main`. The probe reaches the existing function-header gate: parameters
are accepted only when `generic_native_parser_program_type_code_for_token`
returns the `i64` type code. This is independent evidence from
`stage1_empty_ir`, whose original `NativeIR` record result is also outside the
subset.

```text
FULL_STAGE1
├── type-aware target function/value model
│   ├── vector/reference parameter and result types
│   ├── per-value types in NativeIR and verifier contracts
│   └── typed call/ABI and Assembly emission
├── aggregate model
│   ├── 9 Stage1 record declarations / constructors
│   └── field projection and result-record propagation
├── body lowering and control flow
│   ├── 172 match statements / terminal and successor semantics
│   ├── 29 loops / CFG and backedges
│   └── mutable locals and memory effects
├── general call/module composition
│   ├── 894 call expressions / 41 imports
│   └── vector/runtime builtins and imported helper resolution
└── command/runtime boundary
    ├── already supplied by Python CLI for external file I/O
    └── must be replaced or retained explicitly for a native standalone build
```

Top blockers, ranked by dependency leverage:

1. **Type-aware Stage1 target IR and signatures.** All 50 functions (135,088
   attributed source bytes) have a non-`i64` signature. `NativeIR` records
   function result width and IDs but has no general per-parameter/per-value
   type table. This requires coordinated Stage1 parser, NativeIR, verifier,
   call, and emitter work. It unlocks meaningful typed slices; it is not a
   local parser tweak.
2. **Vector/reference ABI and operations.** 38 functions (100,002 attributed
   bytes) have reference-typed signatures; 19 functions (91,999 bytes) use
   address-of; 14 use vector types. The first target needs a vector parameter
   plus `vector_get`, including typed IR and call/emission semantics.
3. **Aggregate records.** Nine records with 51 fields, 30 constructors, and
   174 field accesses require first-class construction, projection, and typed
   result propagation. The smallest current record-result probe is rejected
   before lowering.
4. **Structured body lowering/CFG.** 32 functions (129,824 attributed bytes)
   contain `match`; 20 (50,967 bytes) contain `while`. These need general branch,
   loop, mutation, and terminator lowering with verifier-closed CFGs.
5. **General call and module contracts.** 46 functions (133,498 attributed
   bytes) contain calls; there are 41 imports. The Stage1 target supports
   calls among its scalar subset, but not this module's typed imported/runtime
   helper graph.

The highest-leverage next engineering design is a general, type-aware Stage1
NativeIR contract, beginning with the original
`stage1_emission_value_count` vector-read helper as an end-to-end acceptance
case. It must preserve `i64` behavior and add typed vector parameters/operations
through the verifier and emitted Assembly. The current target representation
does not carry enough type information to implement that safely as a narrow
source-parser extension; this is the present architectural boundary.

## CLI, Validation, and Release State

Final local validation for this continuation was run on the complete working
tree based on `7bfb8edca51d238b7d6ecd245c635fd106790c0c`. The canonical
Stage1 source remained byte-identical at SHA-256
`894a76a5c206b8e86b3149483b4bc2ad6904a4f6810aac62d1e235c1fd46a44c`
(139,740 bytes). The full local Windows suite completed once with exit code 0:

```text
FULL_SUITE_COMMAND=python -m pytest
FULL_SUITE_BASE_HEAD=7bfb8edca51d238b7d6ecd245c635fd106790c0c
FULL_SUITE_SCOPE=COMPLETE_LOCAL_WORKING_TREE
FULL_SUITE_EXIT=0
FULL_SUITE_PASSED=4309
FULL_SUITE_SKIPPED=349
FULL_SUITE_SUBTESTS_PASSED=572
FULL_SUITE_ELAPSED_SECONDS=5344.12
FOCUSED_STAGE1_AND_ADJACENT=43 passed
COMPILEALL_BOOTSTRAP=PASS
AI_CAPABILITIES_JSON=PASS
DIFF_CHECK=PASS
LOCAL_LINUX_FULL_SUITE=NOT_AVAILABLE
REMOTE_CI_FOR_THIS_LOCAL_CANDIDATE=PENDING_PUBLICATION
```

The prior all-green remote CI evidence at `b7844b6fc77ae6e995992e9f032292bd693b26e6`
is historical and does not cover this working-tree candidate. A natural CI run
for the published candidate is still required. The PR remains Draft.

The experimental CLI supports source-file input, Assembly-file output,
deterministic diagnostics for rejected input, artifact verification failures,
I/O errors, and process exit status. Syntax and unsupported-semantics reasons
are not yet split into a complete stable diagnostic taxonomy; phase 3/4 and
numeric error codes remain coarse.

```text
CLI_STAGE1_AVAILABLE=YES
FILE_INPUT_SUPPORTED=YES
FILE_OUTPUT_SUPPORTED=YES
DIAGNOSTICS_SUPPORTED=PARTIAL
BOUNDED_STAGE2_ATTEMPTED=NO
FULL_STAGE1_SELF_COMPILE=NO
FULL_STAGE2=NO
STAGE3=NO
FULL_SELFHOST=NO
DEFAULT_COMPILER=PYTHON
PRODUCTION_DEFAULT_CHANGED=NO
PR_MARKED_READY=NO
MERGED=NO
RELEASE_CREATED=NO
TAG_CREATED=NO
```

Validation and publication state is recorded in the final campaign handoff.
Historical recovery reports and their failure/provenance evidence are not
modified by this continuation.
