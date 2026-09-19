# Source Frontend Projection V1

Status: architecture increment for S3 1.2. This contract connects real source
text to the generic token and syntax data models. It does **not** authorize
Stage1 V4 and does not claim an S3-native parser.

## Source position authority

The frontend normalizes CRLF and bare CR to LF before tokenization. Generic
token and syntax spans are measured as byte offsets into that normalized UTF-8
source.

```text
SOURCE_POSITION_AUTHORITY=NORMALIZED_UTF8_BYTES
LINE_ENDING_AUTHORITY=NORMALIZED_LF
```

The Python reference lexer continues to expose its historical code-point
`position` for compatibility. `TokenArena` stores that compatibility value
only so a direct-ID token can be reconstructed for the reference parser without
rescanning source. It is not the generic span authority.

## TokenArena

`TokenArena` owns tokens by direct integer ID in lexical order. Every token
record contains:

- direct `TokenId`;
- the existing `TokenKind`;
- token text;
- normalized UTF-8 byte span;
- line and column;
- a compatibility source position for the Python parser bridge.

IDs are allocated once and are never reconstructed from source text. The
structural digest excludes host object identity, wall clock, filesystem paths,
and randomized hashes.

The ordinary-S3 projection is
`selfhost/substrate/token_arena.s3`. It demonstrates the flat parallel-vector
shape and direct-ID ordering without claiming to implement lexing.

## Parser boundary

V1 deliberately uses the existing production Python recursive-descent parser as
the grammar oracle:

```text
normalized source
    -> production Python lexer
    -> generic TokenArena
    -> reconstructed reference Token tuple
    -> production Python recursive-descent parser
    -> hosted AST (transient)
    -> generic SyntaxArena
```

The hosted AST is a transient compatibility artifact. It is not the long-lived
compiler representation and is not consumed by the generic verifier or
whole-program IR control plane.

Therefore:

```text
REAL_SOURCE_INPUT=YES
GENERIC_TOKEN_ARENA=YES
GENERIC_SYNTAX_ARENA_OUTPUT=YES
PYTHON_REFERENCE_PARSER_BACKEND=YES
S3_NATIVE_PARSER=NO
STAGE1_V4=NOT_AUTHORIZED
```

A future independent generic parser must consume `TokenArena` directly and
produce the same `SyntaxArena` contract. That replacement must not create a
second AST model.

## Syntax projection

The generic syntax domain is extended with parser-level shapes that were absent
from the original representability-only arena:

- array literals;
- explicit source type nodes;
- type parameters and type-parameter references;
- record fields and enum variants;
- call arguments and record field values;
- match cases and payload labels;
- select arms;
- assignment target forms.

Existing semantic TypeIds remain optional at parse time. A parser-level
`FunctionPayload.return_type_id` may be `-1`; the declared return type is
instead represented structurally as a function child until semantic resolution
publishes a TypeId.

Primitive `TypeName` values in the legacy hosted AST do not carry a
`SourceLocation`. Their parser projection therefore uses a deterministic
zero-width placeholder span. Structural type wrappers and declarations retain
their available source locations. Exact primitive-type token spans remain a
frontend follow-up and must not be inferred from unrelated source rescans.

## Multi-file source bundles

`parse_source_bundle` consumes the existing deterministic `SourceBundle`.
Files retain the bundle's canonical path ordering and normalized bytes. One
shared `SymbolInterner` is used across all source units so equal symbol text has
one stable symbol identity throughout the bundle.

Every file still receives an independent `SyntaxArena` and file ID. The bundle
result records the canonical units plus the shared symbol table and produces a
deterministic structural digest.

## Diagnostics

Lexical and parse failures remain the existing typed Python
`LexError`/`ParseError` diagnostics and retain their current
`DiagnosticCode` authority. This increment does not invent a parallel
diagnostic code family.

Mapping those diagnostics directly into the whole-program `DiagnosticArena`
belongs to composition integration after the independent parser contract is
settled.

## Complexity

For a source unit of length N characters and T tokens:

- normalization: O(N);
- UTF-8 byte-offset table construction: O(N);
- token materialization: O(T);
- reference parsing: governed by the existing recursive-descent parser;
- AST-to-SyntaxArena projection: O(number of AST values);
- direct node/token lookup: O(1);
- child traversal: O(child count).

No generic token or syntax identity is reconstructed by rescanning source.

## Non-goals

V1 does not:

- replace the production lexer or parser;
- implement an S3-native lexer;
- implement an S3-native parser;
- execute semantic expression passes;
- lower generic syntax to IR;
- emit artifacts;
- turn `compile_program` into source-to-output compilation;
- authorize self-host re-entry or Stage1 V4.

The next parser-specific frontier after this bridge is an independent generic
parser kernel over `TokenArena`, followed by ordinary-S3/native qualification.
