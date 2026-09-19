# Source Frontend Representability Matrix

| Structure | Status | Evidence / boundary |
| --- | --- | --- |
| SourceBundle | REPRESENTABLE_NOW | inherited deterministic normalized source transport |
| normalized UTF-8 byte positions | REPRESENTABLE_NOW | TokenArena span authority |
| TokenId | REPRESENTABLE_NOW | direct StableArena identity |
| TokenArena hosted | REPRESENTABLE_NOW | source_frontend.py |
| TokenArena ordinary S3 shape | REPRESENTABLE_NOW_FOR_SHAPE | token_arena.s3 |
| lexical decisions hosted | REPRESENTABLE_NOW | GenericLexer writes TokenArena directly |
| lexical differential oracle | AVAILABLE | production Python lexer |
| lexer state ordinary S3 | REPRESENTABLE_NOW_FOR_SHAPE | generic_lexer_state.s3 |
| bounded native lexer slice | QUALIFIED_FOR_BOUNDED_CASES | hosted differential digests 1509, 2101, 2285, 2375; Linux x86-64 native pass |
| complete lexer algorithm ordinary S3 | BLOCKED | hosted algorithm not yet projected/executed natively |
| parser cursor/state hosted | REPRESENTABLE_NOW | generic_parser.py |
| parser cursor/state ordinary S3 | REPRESENTABLE_NOW_FOR_SHAPE | generic_parser_state.s3 |
| bounded native function parser slice | QUALIFIED_FOR_MINIMAL_FUNCTION_AND_BINARY_RETURN | native token vectors -> function/return/integer and binary-expression structural digests; Linux x86-64 15-test pass |
| parser grammar decisions hosted | REPRESENTABLE_NOW_V0_6 | GenericParser consumes TokenArena directly |
| parser differential oracle | AVAILABLE | production Python parser |
| native binary integer-expression parser slice | QUALIFIED_FOR_BINARY_RETURN_SUBSET | `1 + 2` and `40 + 2` pass; missing-left and missing-right cases reject |
| complete parser algorithm ordinary S3 | BLOCKED | hosted algorithm not yet projected/executed natively; precedence/general expression coverage remains |
| parser-level SyntaxArena | REPRESENTABLE_NOW_HOSTED | direct GenericParser output |
| hosted AST dependency in independent path | NO | GenericLexer -> TokenArena -> GenericParser -> SyntaxArena |
| reference lexer dependency in independent path | NO | TokenArena.from_source_independent uses GenericLexer |
| multi-file symbol identity | REPRESENTABLE_NOW_HOSTED | shared SymbolInterner across SourceBundle |
| source syntax -> ProgramRegistry plan | REPRESENTABLE_NOW_HOSTED | frontend_registration.py |
| implicit module identity | REPRESENTABLE_NOW_HOSTED | existing logical-path ModuleId authority |
| import visibility | REPRESENTABLE_NOW_HOSTED | ProgramRegistry requires target export |
| module cycle rejection | REPRESENTABLE_NOW_HOSTED | deterministic registry graph validation |
| nominal field/variant ranges | REPRESENTABLE_NOW_HOSTED | per-nominal ranges, duplicate checks scoped to owner |
| unresolved nominal type syntax | REPRESENTABLE_NOW_HOSTED | FieldSpec/VariantSpec retain syntax IDs |
| frontend -> control-plane registration | REPRESENTABLE_NOW_HOSTED | INPUT/SYNTAX/REGISTRATION |
| frontend TYPE resolution | REPRESENTABLE_NOW_HOSTED | frontend_types.py resolves canonical TypeIds |
| function signatures from generic syntax | REPRESENTABLE_NOW_HOSTED | SemanticState signature arena populated transactionally |
| local/imported nominal type identity | REPRESENTABLE_NOW_HOSTED | module/import aware nominal lookup |
| owner-sensitive type parameters | REPRESENTABLE_NOW_HOSTED | function/nominal owner + ordinal identity |
| record/enum member type metadata | REPRESENTABLE_NOW_HOSTED | resolved field and variant payload rows |
| TYPE rollback | REPRESENTABLE_NOW_HOSTED | TypeArena + SemanticState checkpoints preserve registration |
| compile_program real-source ingestion | REPRESENTABLE_NOW_HOSTED_PARTIAL | commits through TYPE, fails closed at SEMANTIC |
| frontend diagnostics | PARTIAL | error codes enter phase diagnostics; complete source-span envelope pending |
| expression/declaration semantic phase | BLOCKED | no real expression/binding semantic analysis yet |
| source -> IR | BLOCKED | semantic passes/lowering absent |
| source -> output | BLOCKED | semantics/lowering/emitter absent |

## Position contract

Generic frontend spans are byte offsets into LF-normalized UTF-8 source.
Compatibility source positions are code-point indexes retained only for
reference differential behavior and diagnostics.

## Hosted frontend contract

The independent hosted path is:

```text
normalized source
  -> GenericLexer
  -> TokenArena
  -> GenericParser
  -> SyntaxArena
```

Neither lexical nor grammar decisions delegate to the Python reference
lexer/parser in this path.

## Complexity

- normalization: O(N);
- codepoint-to-byte table: O(N);
- independent lexing: O(N);
- token materialization: O(T);
- generic recursive-descent parse: O(T) for ordinary grammar paths, with bounded
  lookahead scans for generic-call/type disambiguation;
- direct token/node lookup: O(1);
- child traversal: O(children).

TokenIds and NodeIds are never reconstructed by source recount.

## Next blocker

`NATIVE_EXPRESSION_PRECEDENCE`: generalize the native expression parser beyond
the bounded integer-plus-integer return shape while preserving the existing
SourceView/TokenArena/SyntaxArena contracts.
