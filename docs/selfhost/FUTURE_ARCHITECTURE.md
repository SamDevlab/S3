# Future self-host architecture blueprint

Status: **design reference only**. This document does not authorize another
self-host implementation generation.

The purpose of this blueprint is to preserve the architecture we would require
before re-entering full compiler self-hosting. It is intentionally generic and
avoids fixture/slice-driven production design.

## Target pipeline

```text
SourceBundle
    |
    v
SourceView / Cursor
    |
    v
Lexer
    |
    v
TokenArena
    |
    v
Parser
    |
    v
SyntaxArena (AST/HIR)
    |
    v
Program registration
    |
    +--> FunctionTable
    +--> NominalTypeTable
    +--> ModuleTable
    |
    v
Semantic passes
    |
    +--> ScopeArena
    +--> DeclarationArena
    +--> TypeArena
    +--> StorageTable
    |
    v
Generic lowering
    |
    v
IR Program
    |
    +--> Function IR
    +--> BlockArena
    +--> InstructionArena
    +--> Value/Storage identities
    |
    v
Verifier
    |
    v
Emitter
    |
    v
OutputSink
```

One composition root owns this flow:

```text
compile_program(source_bundle, output_sink) -> CompileResult
```

The exact S3 signature is deliberately unspecified until the representability
review closes it.

## 1. SourceBundle and SourceView

The host may mechanically assemble opaque source bytes according to a frozen,
deterministic manifest. File identity and byte boundaries must remain explicit.

The compiler receives a source abstraction capable of:

- deterministic file traversal;
- bounded unit access;
- file-local and program-global coordinates;
- safe span comparison;
- LF/CRLF-correct cursor movement;
- chunk-boundary-transparent reads.

The compiler must not require the host to tokenize, parse, reorder declarations
semantically, or create compiler metadata.

## 2. TokenArena

Tokens have stable integer identity and live in a compiler-owned arena or
another explicitly S3-representable indexed structure.

Minimum conceptual token fields:

```text
TokenId
kind
file_id
start
end
literal/reference metadata when required
```

Chunking is a transport implementation detail. The same source must produce the
same token semantics regardless of chunk boundaries.

## 3. SyntaxArena

The parser produces one generic structured representation. A compact indexed
arena is preferred over host-style object graphs.

Conceptual fields may include:

```text
NodeId
node_kind
file_id
start
end
child_a
child_b
child_c
next
aux
```

Additional parallel arrays are acceptable when a node family requires them.
The representation must encode arbitrary programs in the agreed Stage1 subset,
not only known fixtures.

The parser must be grammar-driven. Test/slice identity is never a production
input.

## 4. Program registration

Before body semantics, the compiler should build deterministic program-level
identity for the constructs that require it.

Conceptually:

- `ModuleId`;
- `FunctionId`;
- `RecordTypeId`;
- `EnumTypeId`;
- other nominal type IDs required by the Stage1 subset.

IDs are direct deterministic allocations. They are never reconstructed by
rescanning earlier source text.

## 5. Semantic arenas

Semantic state is explicit and reusable.

### ScopeArena

Each scope has a stable `ScopeId`, parent relation, and declaration membership.
Lexical shadowing resolves to the nearest visible declaration. Scope exit
restores the outer binding; siblings and match arms do not leak.

### DeclarationArena

Each declaration has one stable `DeclarationId`. Type, value, storage, and
mutability queries for a use resolve through that identity rather than through
separate textual searches.

### TypeArena

Types have stable `TypeId` identity. Nominal records/enums remain nominal.
Layouts are computed once and reused rather than reconstructed on every access.

### StorageTable

Storage identity is associated with the declaration/semantic state once. It is
not rediscovered by source-prefix scanning.

## 6. Semantic pass structure

The exact pass count is a design decision, but a future architecture should
separate responsibilities rather than reparse syntax during lowering.

A plausible pass sequence is:

```text
1. program/type/function registration
2. lexical scope + declaration construction
3. name resolution
4. type checking/finalization
5. storage/semantic finalization
```

The important invariant is that lowering consumes semantic state already built
and verified.

## 7. Generic lowering

Lowering dispatches by generic syntax/HIR node kind.

Conceptually:

```text
lower_statement(NodeId)
lower_expression(NodeId)
```

not by fixture, milestone, source function name, source cursor, or expected
output.

Speculative lowering uses explicit transactions:

```text
checkpoint
probe
commit | rollback
```

A failed/non-owning probe leaves zero committed state.

## 8. Direct deterministic allocators

At minimum the architecture needs direct allocation for:

- `FunctionId`;
- `ScopeId`;
- `DeclarationId`;
- `TypeId`;
- `StorageId`;
- `BlockId`;
- `ValueId`;
- `InstructionId`.

Allocator state or arena length is the source of identity. Source recount is not
an allocator.

## 9. IR

The IR must be designed against the complete agreed Stage1 feature inventory
before broad self-source claims.

Create an explicit mapping:

```text
language/HIR operation -> generic IR operation(s)
```

The IR should remain minimal, typed where required, deterministic, and
self-host representable. It must cover the compiler's actual source needs,
including calls, control flow, storage, aggregates, nominal enums/records,
arrays/references, and other agreed Stage1 operations.

No fixture-specific pseudo-op is permitted.

## 10. Verifier

The verifier is independent of frontend trust. It must validate at least:

- unique instruction IDs;
- unique value producers;
- valid operand references;
- valid storage references;
- valid block references;
- valid terminators;
- no fallthrough after a terminator;
- call signature/arity metadata where represented;
- record/enum/aggregate metadata;
- other invariants introduced by the final IR design.

Negative IR fixtures are required for every important invariant family.

## 11. Emitter

Every required IR kind has an explicit output encoding before the compiler is
considered architecturally complete.

The emitter:

- consumes generic verified IR;
- never dispatches by test/slice identity;
- fails closed for unknown IR;
- emits deterministic bytes;
- does not add timestamps, host addresses, PIDs, or filesystem-order noise;
- supports bounded/streamed output rather than depending on one giant fixed
  buffer.

## 12. OutputSink

`OutputSink` is a bounded or streamed compiler-owned output abstraction. Chunk
size must not alter semantic output bytes. Capacity failure is deterministic
and explicit; truncation is forbidden.

## 13. Composition root

`compile_program` is designed before implementation begins. It owns compiler
phase order and state lifetime.

Conceptually it performs:

```text
validate input bundle
lex
parse
register program entities
run semantic passes
lower each function
verify IR
emit artifact
finalize output
return structured result
```

No Python-side synthetic semantic entry is part of this flow.

## 14. Bootstrap boundary

A future proof distinguishes:

### Stage0

Python reference compiler creates the initial executable/emulatable S3 compiler
artifact. Differential/reference use is allowed.

### Stage1 true self-compile

The produced S3 compiler receives its complete own source bundle and performs
lexing, parsing, semantic analysis, lowering, verification, and emission itself.
Host semantic compiler entry points are disabled for this phase.

The host may only perform mechanical source reading/packing, process or emulator
invocation, raw output capture, persistence, hashing, and resource control.

### Next-stage artifact

Stage1's output may be statically validated. Executing it is a separate Stage2
gate and must never be implied by successful production.

## 15. Complexity invariants

The architecture is rejected before implementation if it requires:

- repeated whole-function source scans for local resolution;
- ID reconstruction by recount;
- whole-program reparsing for each function;
- rebuilding layouts per field access;
- pathological aggregate/compiler-state copying;
- rescanning already-emitted output;
- raising resource budgets as the primary fix for structural complexity.

Logical-work scaling tests should accompany each subsystem.

## 16. Acceptance strategy

Vertical slices remain useful, but only as acceptance tests of the generic
pipeline. A new feature is considered self-host-ready only when it travels
through the same generic path:

```text
source -> parse -> semantics -> lower -> IR -> verify -> emit
```

As coverage grows, production path count should remain tied to grammar/node/IR
kinds, not to the number of fixtures.

Before full self-compile, an anti-specialization corpus must combine supported
features in previously unseen ways without requiring production changes.

## 17. Re-entry rule

This blueprint is not sufficient by itself. Before a new implementation is
authorized, the representability and re-entry gates in
[`REENTRY_CRITERIA.md`](REENTRY_CRITERIA.md) must be closed with repository
evidence.
