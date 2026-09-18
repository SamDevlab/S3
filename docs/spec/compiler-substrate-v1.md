# Compiler Substrate V1

This document specifies the bounded infrastructure substrate introduced for
future compiler-shaped components. It is an implementation contract, not an
authorization to replace the Python reference compiler or to begin Stage1 V4.

## Text-keyed map

`map<text, i64>` is specialized to the closed runtime type `text_i64_map` and
uses `text_i64_map_*` runtime operations. Keys are compared as their exact
UTF-8 byte sequences. No Unicode normalization, host pointer identity, or
Python hash participates in equality or ordering.

The map is insertion ordered and linearly searched. Capacity is explicit;
`put` never grows implicitly. A borrowed key is cloned before a new entry is
published, so later mutation of the source text cannot mutate the stored key.
Replacing a key updates only its value and preserves its position. `clone`
deep-copies keys, and `key_at` returns an owned clone. `remove` compacts later
entries in insertion order.

The hosted implementation and the Linux x86-64 runtime use the same logical
contract. Native storage is a bounded vector of `(owned-key-descriptor, i64)`
entries and uses deterministic linear byte comparison.

## Stable IDs and lexical state

`SymbolInterner` maps owned UTF-8 names to direct integer IDs and keeps the
reverse arena. `StableArena` appends values under direct integer IDs and uses
checkpoint lengths for bounded rollback without deep-copying the arena.
`SemanticEnvironment` owns explicit scope and declaration IDs, resolves the
nearest declaration, permits shadowing in nested scopes, and keeps function
scope boundaries explicit.

Declarations carry symbol, scope, kind, optional type and storage IDs,
mutability, and an optional source span. Type-name and function-name tables are
the same text-to-i64 map contract, not separate host dictionaries. Scope and
declaration changes are recorded in a bounded undo log so a checkpoint can
restore shadowing without copying the environment or reusing published IDs.

The reserved substrate ID domains are `File`, `Symbol`, `Scope`,
`Declaration`, `Type`, `Function`, `Storage`, `Node`, `Block`, `Value`, and
`Instruction`. These are representability contracts only; they are not yet a
semantic compiler IR.

The ordinary-S3 representability probe also defines flat `Span`, `Token`,
`Node`, `Value`, `Instruction`, and `Block` records. Composite vectors are
exercised as local arena-like values; aggregate context state stores integer
IDs, matching the current language rule that composite vectors are not fields
inside another aggregate.

## Source transport V1

`SourceBundle` sorts paths by UTF-8 bytes, rejects duplicates, and normalizes
CRLF/CR to LF before exposing a `SourceView` and bounded byte `SourceCursor`.
Reads and advances are O(1) per byte and reject cross-view or out-of-range
cursors. The bundle digest includes path and content lengths, paths, and
normalized bytes in canonical order.

V1 deliberately canonicalizes CRLF and CR to LF at bundle construction. This
is an explicit transport contract, so cursor offsets refer to the canonical
LF view rather than silently pretending to preserve original physical byte
positions. A future source-span contract that requires raw-file offsets must
carry the original bytes and an explicit offset map instead of changing this
rule implicitly.

## OutputSink V1 and transactions

`OutputSink` accepts UTF-8 text or bytes into an explicit bounded buffer. An
append that would exceed capacity fails without partial output. Checkpoints are
byte lengths; rollback truncates only output produced after that checkpoint.
`CompilerContext` combines source transport, symbol/environment state, the
reserved ID arenas, and the sink. Its checkpoint/rollback operation records
arena cursors, symbol state, environment undo-log position, name-table undo
positions, and sink length rather than copying whole compiler state. A
`CompileResult` exposes success, an optional diagnostic code, bounded error
text, optional source span, and output length metadata without implementing
compilation phases.

## Evidence boundaries

The substrate is hosted-first. The text map has an independently qualified
Linux x86-64 implementation; source transport, lexical state, arenas, and
output transactions remain ordinary representability models until their own
native execution gates are added. No compiler-only runtime intrinsic is part
of this contract, and no lexer, parser, semantic compiler, lowerer, verifier,
or emitter is implemented here.

## Non-goals

This increment does not implement an S3 lexer, parser, semantic analyzer,
lowerer, verifier, emitter, or self-hosted compiler pipeline. It does not
change the canonical source, the default Python toolchain, or the deferred
self-hosting policy.
