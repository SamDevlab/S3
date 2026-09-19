# Source Frontend Representability Matrix

| Structure | Status | Evidence / boundary |
| --- | --- | --- |
| SourceBundle | REPRESENTABLE_NOW | inherited deterministic normalized source transport |
| normalized UTF-8 byte positions | REPRESENTABLE_NOW | TokenArena span authority |
| TokenId | REPRESENTABLE_NOW | direct StableArena identity |
| TokenArena hosted | REPRESENTABLE_NOW | source_frontend.py |
| TokenArena ordinary S3 shape | REPRESENTABLE_NOW_FOR_SHAPE | token_arena.s3 parallel vectors |
| lexical decisions hosted | REFERENCE_BACKED | production Python lexer remains authority |
| lexical decisions ordinary S3 | BLOCKED | independent generic lexer not implemented |
| parser cursor/state hosted | REPRESENTABLE_NOW | generic_parser.py |
| parser cursor/state ordinary S3 | REPRESENTABLE_NOW_FOR_SHAPE | generic_parser_state.s3 |
| parser grammar decisions hosted | REPRESENTABLE_NOW_V0_6 | GenericParser consumes TokenArena directly |
| parser grammar decisions ordinary S3 | BLOCKED | no ordinary-S3 grammar execution yet |
| parser-level SyntaxArena | REPRESENTABLE_NOW_HOSTED | direct GenericParser output |
| hosted AST dependency in independent parser | NO | explicit direct TokenArena -> SyntaxArena path |
| multi-file symbol identity | REPRESENTABLE_NOW_HOSTED | shared SymbolInterner across SourceBundle |
| parser diagnostics | PARTIAL | existing ParseError/DiagnosticCode authority; no composition DiagnosticArena mapping yet |
| source -> IR | BLOCKED | semantic passes/lowering absent |
| source -> output | BLOCKED | semantics/lowering/emitter absent |

## Position contract

Generic frontend spans are byte offsets into LF-normalized UTF-8 source.
Reference parser compatibility positions remain code-point indexes internally
and are not the generic span identity.

## Parser contract

The hosted independent parser is V0.6-only. It consumes direct-ID TokenArena
records and constructs the existing generic SyntaxArena directly. The
production Python parser remains available only as a compatibility/differential
oracle for this increment.

## Complexity

- normalization: O(N);
- codepoint-to-byte table: O(N);
- token materialization: O(T);
- generic recursive-descent parse: O(T) for ordinary grammar paths, with bounded
  lookahead scans for generic-call/type disambiguation;
- direct token/node lookup: O(1);
- child traversal: O(children).

TokenIds and NodeIds are never reconstructed by source recount.

## Next blocker

`INDEPENDENT_GENERIC_LEXER_KERNEL`: populate the same TokenArena without
delegating lexical decisions to the Python lexer. Ordinary-S3/native parser
execution remains a later qualification boundary.
