# Whole-Program Composition V1

This specification defines the whole-program control plane added after the
generic syntax, IR, and verifier substrate. It is a state and ownership
contract. The control plane can now ingest real source through the independent
hosted frontend, but it is not a semantic expression analyzer, generic lowerer,
emitter, Stage1 compiler, or self-hosting authorization.

## Boundary

V1 exposes two explicit composition paths.

The prepared-artifact path remains available for architecture, transaction, and
verifier tests:

```text
SourceBundle + SyntaxArena + registration view + optional semantic seed
    -> ProgramRegistry -> TypeArena -> SemanticState
    -> prebuilt IRProgram -> IndependentVerifier
    -> caller-owned OutputSink -> CompileResult
```

Prepared syntax, semantic, IR, and output values are labeled
`TEST_ARTIFACT_INPUT`.

The real-source path now performs:

```text
SourceBundle
    -> GenericLexer
    -> TokenArena
    -> GenericParser
    -> SyntaxArena
    -> registration view
    -> ProgramRegistry
    -> TYPE:FAILED(S3E_TYPE_PHASE_UNAVAILABLE)
```

The real-source path commits `INPUT`, `SYNTAX`, and `REGISTRATION`, then
fails closed at `TYPE`. It does not synthesize type resolution, expression
semantics, IR, verification, emission, or output. The independent hosted
frontend is an architecture candidate; the default production Python compiler
and parser remain unchanged.

## Identity and ownership

One `WholeProgramContext` owns exactly one `ProgramId` (`0`) and one isolated
compilation session. `ModuleId`, `FunctionId`, `NominalTypeId`, `TypeId`,
`ScopeId`, `DeclarationId`, and `StorageId` are direct integer identities
allocated by compiler-owned arenas. Existing `NodeId`, `BlockId`, `ValueId`,
and `InstructionId` remain owned by the syntax and IR arenas.

Modules are ordered by the explicit manifest ordinal, then canonical source
file ID, module symbol ID, and root node ID. Functions and nominal declarations
are ordered by explicit declaration ordinal and stable symbol/node identity.
Host filesystem enumeration and Python hash order do not select identities.

For real-source ingestion, an absent source `module` declaration uses the
existing module-graph authority: normalized relative path, minus the `.s3`
suffix, rendered as a dotted module id. The frontend does not define a parallel
anonymous-module naming scheme.

`ProgramRegistry` owns indexed module, function, parameter, nominal type,
field, variant, import, and export tables. Registration is declaration-only;
function bodies are not analyzed. Import targets must be registered and
exported, duplicate import aliases are rejected, direct/indirect module import
cycles fail closed, nominal field/variant ranges are scoped to each owner, and
unresolved source type syntax identities are retained for the later TYPE
phase.

## TypeArena

Primitive IDs use this fixed order:

```text
0 trit, 1 tryte, 2 i64, 3 f64, 4 string, 5 bytes, 6 text
```

Structural keys canonicalize vector/map/set, fixed array, reference, slice,
type parameter, and instantiated types. Nominal keys include defining module
and nominal declaration identity. Type parameters include owner identity and
ordinal. Equivalent keys return one `TypeId`; nominally distinct declarations
never merge. The arena has checkpoint/rollback with monotonic direct IDs and
does not recompute prior IDs.

Existing layout authority remains authoritative. V1 stores type identity and
metadata only; it does not introduce a second layout algorithm.

## SemanticState

Semantic state stores scopes, declarations, storage associations, function
signatures, node-to-type associations, call targets, and mutability metadata
explicitly. Association methods validate IDs at the point of publication.
No later query rescans source text to reconstruct identity.

## Diagnostics

`DiagnosticArena` is a bounded append-only arena. Diagnostics have direct IDs,
phase ownership, stable codes, fatality, notes, and optional verifier
function/block/instruction context. A fatal phase publishes its diagnostic,
preserves earlier committed state, and suppresses dependent phases.

V1 stops at the first fatal phase diagnostic. Independent diagnostics are not
implicitly accumulated across phases.

## Phase model

The deterministic phase order is:

```text
INPUT -> SYNTAX -> REGISTRATION -> TYPE -> SEMANTIC -> LOWERING
       -> VERIFICATION -> EMITTER -> OUTPUT -> FINALIZE
```

`LOWERING` and `EMITTER` are explicitly skipped for prepared-artifact tests.
They are never reported as executed. In the real-source path, INPUT, SYNTAX, and
REGISTRATION commit, TYPE fails with the current unavailable-phase diagnostic,
and every dependent phase is marked `SKIPPED`.

A phase can be `RUNNING`, `COMMITTED`, `FAILED`, or `SKIPPED`. Invalid
order, duplicate begin, and commit without a running phase are rejected. A
failed phase records one diagnostic and all dependent phases become
`SKIPPED`.

The current implementation uses cursor checkpoints rather than copying the
whole context. Rollback removes only post-checkpoint arena entries and restores
association maps through change logs. Earlier committed phases remain intact.

## Output and result

The caller owns the `OutputSink`. Output is appended transactionally only after
verification. Capacity failure rolls the sink back to its phase checkpoint and
publishes a structured diagnostic. V1 accepts only prepared output bytes; this
is transport testing, not emission.

`WholeProgramCompileResult` contains success, output bytes, ordered diagnostics,
phase trace, IR digest, and a structural digest. The structural digest covers
stable program/type/semantic/diagnostic/phase/IR/output state and excludes
paths, clocks, process IDs, and host object addresses.

## Integration and non-goals

The existing Python compiler and `CompilerContext` remain the default production
pipeline. `WholeProgramContext` is a clearly named architectural session and
does not replace that API. The independent hosted `GenericLexer` and
`GenericParser` feed the control plane only through the generic TokenArena /
SyntaxArena contract. The existing generic verifier is called directly in the
prepared-IR path; its invariants are not duplicated.

The S3 files under `selfhost/substrate/` are ordinary representability
projections for registration, type canonicalization, phases, diagnostics,
frontend state, and context state. They do not constitute a Stage1 candidate
and do not prove native lexer/parser execution.

Not implemented by V1: real TYPE/semantic resolution from generic syntax,
expression semantic passes, generic lowering, optimizer integration for this
pipeline, emitter, source-to-output compilation, ordinary-S3/native complete
frontend execution, Stage1 V4, Stage2, Stage3, release, or self-host re-entry.