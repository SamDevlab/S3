# Source Frontend Representability Matrix

| Structure | Status | Evidence / boundary |
| --- | --- | --- |
| SourceBundle | REPRESENTABLE_NOW | inherited deterministic normalized source transport |
| normalized UTF-8 byte positions | REPRESENTABLE_NOW | TokenArena span authority |
| TokenId | REPRESENTABLE_NOW | direct StableArena identity |
| TokenArena hosted | REPRESENTABLE_NOW | source_frontend.py |
| TokenArena ordinary S3 shape | REPRESENTABLE_NOW_FOR_SHAPE | token_arena.s3 parallel vectors |
| lexical decisions in ordinary S3 | BLOCKED | production Python lexer remains authority |
| parser cursor/state | PARTIALLY_REPRESENTABLE | reference parser compatibility path only |
| parser grammar decisions in ordinary S3 | BLOCKED | independent parser kernel not implemented |
| parser-level SyntaxArena | REPRESENTABLE_NOW_HOSTED | AST compatibility projection |
| multi-file symbol identity | REPRESENTABLE_NOW_HOSTED | shared SymbolInterner across SourceBundle |
| parser diagnostics | PARTIAL | existing LexError/ParseError authority; no composition DiagnosticArena mapping yet |
| source -> IR | BLOCKED | semantic passes/lowering absent |
| source -> output | BLOCKED | semantics/lowering/emitter absent |

## Position contract

Generic frontend spans are byte offsets into LF-normalized UTF-8 source.
Reference parser compatibility positions remain code-point indexes internally
and are not the generic span identity.

## Complexity

- normalization: O(N);
- codepoint-to-byte table: O(N);
- token materialization: O(T);
- AST compatibility projection: O(A);
- direct token/node lookup: O(1);
- child traversal: O(children).

The bridge does not reconstruct TokenIds or NodeIds through source rescans.

## Next blocker

`INDEPENDENT_GENERIC_PARSER_KERNEL`: consume TokenArena directly and emit the
same SyntaxArena without Python AST/parser semantic decisions.
