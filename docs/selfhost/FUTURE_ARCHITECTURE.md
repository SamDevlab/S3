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

## Source transport

The host may mechanically assemble opaque source bytes according to a frozen,
deterministic manifest. File identity and byte boundaries must remain explicit.
The compiler, not the host, owns tokenization and semantic interpretation.

The source abstraction must support deterministic file traversal, safe span
comparison, LF/CRLF-correct cursor movement, and chunk-boundary-transparent
reads.

## Stable compiler identities

Tokens, syntax nodes, functions, scopes, declarations, types, storage, blocks,
values, and instructions must use stable integer identities allocated directly
from compiler-owned arenas or equivalent indexed structures.

IDs are never reconstructed by rescanning source text.

## Generic syntax and semantics

The parser produces one generic structured representation capable of encoding
arbitrary programs in the agreed Stage1 subset. A compact indexed arena is
preferred over host-style object graphs.

Semantic state is built in explicit passes. Lexical shadowing, nominal type
identity, call targets, storage, mutability, and layouts are resolved once and
reused by lowering. Lowering must not repeatedly reparse or rescan source to
recover semantic state.

## Generic lowering

Lowering dispatches by generic syntax/HIR node kind, conceptually through
operations such as:

```text
lower_statement(NodeId)
lower_expression(NodeId)
```

Production lowering must never dispatch by fixture, milestone, source function
name, cursor position, or expected output.

Speculative lowering uses explicit checkpoint / commit / rollback semantics so
a failed or non-owning probe leaves zero committed state.

## IR and verifier

Before broad self-source claims, the required Stage1 language subset must have a
complete map from language/HIR operations to generic IR operations.

The verifier is independent of frontend trust. It must reject duplicate IDs or
producers, invalid operands/storage/blocks, malformed terminators, call metadata
errors, and aggregate metadata errors. Negative IR fixtures are required for
important invariant families.

## Emitter and output

Every required IR kind must have an explicit output encoding. The emitter
consumes verified generic IR, fails closed for unknown operations, emits
deterministic bytes, and does not depend on one giant fixed buffer.

`OutputSink` may be bounded or streamed, but chunk size must not alter semantic
output bytes. Capacity failure is explicit; truncation is forbidden.

## Composition root

`compile_program` is designed before implementation begins. Conceptually it:

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

No Python-side synthetic semantic entry belongs in that flow.

## Bootstrap boundary

A future proof distinguishes:

- **Stage0**: Python reference compiler creates the initial S3 compiler artifact;
- **Stage1 true self-compile**: that S3 compiler consumes its complete own source
  and performs lexing, parsing, semantics, lowering, verification, and emission;
- **next-stage artifact**: Stage1 output may be statically validated, while
  executing it is a separate Stage2 gate.

During true self-compilation the host may only perform mechanical source
transport, invocation, raw output capture, persistence, hashing, and resource
control.

## Complexity invariants

The architecture is rejected before implementation if it requires repeated
whole-function source scans, source recount for IDs, whole-program reparsing per
function, layout reconstruction per use, pathological compiler-state copying,
rescanning already-emitted output, or resource-budget increases as the primary
fix for structural complexity.

## Acceptance strategy

Vertical slices remain useful only as acceptance tests of the same generic path:

```text
source -> parse -> semantics -> lower -> IR -> verify -> emit
```

As feature coverage grows, production path count must remain tied to grammar,
node, and IR kinds rather than the number of fixtures.

Before full self-compile, an anti-specialization corpus must compose supported
features in previously unseen ways without requiring production changes.

## Re-entry rule

This blueprint is not authorization. A new implementation can be proposed only
after the representability and re-entry gates in
[`REENTRY_CRITERIA.md`](REENTRY_CRITERIA.md) are closed with repository evidence.
