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
so reference tokens can be reconstructed without source rescans. The
independent generic lexer publishes the same compatibility position while
computing generic spans from the normalized UTF-8 byte-offset table. The
compatibility position is not the generic span authority.

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

The ordinary-S3 projections are
`selfhost/substrate/token_arena.s3` and
`selfhost/substrate/generic_lexer_state.s3`. They demonstrate the flat
parallel-vector token/state representation and deterministic cursor/classifier
shape. The latter now also contains a bounded executable slice for the
`fn main`/`return 0` source shape; it is a vertical-slice proof, not a claim
of an ordinary-S3 complete lexer.

### Bounded ordinary-S3 lexer slice

`generic_lexer_native_case` is compiled through the normal S3 compiler path.
It scans a small source buffer using ordinary S3 control flow, emits token
IDs, token-kind codes, and normalized source spans into bounded vectors, then
computes a deterministic digest. The focused regression derives the expected
digest from the independent hosted `GenericLexer` and asserts equality. The
qualification cases yield `1509` for the original shape, `2101` after adding
real `(` and `)` classification, `2285` for `entry`/`42`, and `2375` for
`worker`/`7`. The latter two cases prove cursor advancement and integer
scanning are not coupled to the earlier `main`/`0` literals. This keeps the
hosted generic frontend as the semantic vocabulary oracle while proving that
real S3 code can execute small lexer-shaped slices.

The slice intentionally does not cover indentation, comments, strings,
operators, parser state, semantic analysis, lowering, or output generation.
Linux x86-64 native qualification is platform-gated. The current Windows host
skips that local marker, while the same focused test passes on the project
Linux x86-64 VM.

### Bounded native function parser slice

`generic_native_parser_digest` consumes the token IDs, kinds, and spans emitted
by the native lexer vectors. It recognizes the bounded
`fn <identifier>() -> i64:` shape with an indented `return <integer>` body,
checks the final newline and EOF, and derives a structural digest from the
name bytes, spans, integer value, and token count. The hosted independent
`GenericParser` supplies the differential oracle; the native implementation
does not call `GenericLexer`, `GenericParser`, `tokenize`, or `parse_tokens`.

The valid `entry`/`42` and `worker`/`7` cases produce `1063349395` and
`38641705493`, respectively. Missing integer and trailing source are rejected
with `-1`. The Linux x86-64 focused qualification passed 11 tests, including
the parser positives and negatives, while the Windows run records the native
Linux marker as an expected platform skip.

## Parser boundary

V1 now provides two explicit hosted paths.

The compatibility/reference bridge remains available:

```text
normalized source
    -> production Python lexer
    -> generic TokenArena
    -> reconstructed reference Token tuple
    -> production Python recursive-descent parser
    -> hosted AST (transient)
    -> generic SyntaxArena
```

The fully independent hosted frontend path is:

```text
normalized source
    -> GenericLexer
    -> generic TokenArena
    -> GenericParser
    -> generic SyntaxArena
```

`GenericLexer` does not call `bootstrap.s3.lexer.Lexer` or
`bootstrap.s3.lexer.tokenize`; it shares only the stable
`TokenKind`/`SyntaxMode` vocabulary. `GenericParser` consumes
`TokenArena` directly, does not import or construct `bootstrap.s3.ast`
values, and does not call `bootstrap.s3.parser`.

The reference lexer/parser bridge remains available solely as a
differential/compatibility oracle.

Therefore:

```text
REAL_SOURCE_INPUT=YES
GENERIC_TOKEN_ARENA=YES
GENERIC_SYNTAX_ARENA_OUTPUT=YES
INDEPENDENT_GENERIC_LEXER=YES_HOSTED
INDEPENDENT_GENERIC_PARSER=YES_HOSTED_V0_6
REFERENCE_LEXER_DIFFERENTIAL_ORACLE=YES
REFERENCE_PARSER_DIFFERENTIAL_ORACLE=YES
S3_NATIVE_LEXER=PARTIAL_GENERALIZED_SUBSET
S3_NATIVE_PARSER=PARTIAL_MINIMAL_FUNCTION
NATIVE_SOURCE_TO_SYNTAX_END_TO_END=PROVEN_FOR_MINIMAL_FUNCTION_SUBSET
STAGE1_V4=NOT_AUTHORIZED
```

V1 independent parsing intentionally targets the current default V0.6 grammar.
V0.5 remains reference-backed until separately migrated. The independent parser
must continue to produce the same generic SyntaxArena contract and must not
create a second AST model.

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


## Registration integration

The hosted independent frontend now has an explicit bridge from generic syntax
to the whole-program `ProgramRegistry`.

`build_registration_plan(frontend)` derives deterministic `ModuleSpec`,
`FunctionSpec`, `NominalTypeSpec`, `ImportSpec`, and `ExportSpec` values
from `SyntaxArena` nodes. Registration does not invoke semantic expression
analysis.

For source units without an explicit `module` declaration, module identity
follows the existing module-graph authority: normalized relative path with the
`.s3` suffix removed and path components converted to the canonical dotted
module id. The frontend does not invent a second anonymous-module naming rule.

The bridge preserves unresolved declaration-type syntax IDs where registration
precedes type resolution. Record/enum type identities and field/variant names
are registered, while semantic `TypeId` assignment remains a later phase.

`ingest_source_frontend(context)` advances a fresh `WholeProgramContext`
through exactly:

```text
INPUT -> SYNTAX -> REGISTRATION
```

and stops with `TYPE` as the next legal phase. It does not mark TYPE,
SEMANTIC, LOWERING, VERIFICATION, EMITTER, OUTPUT, or FINALIZE as successful.
Frontend or registration failure is converted into the existing structured
phase failure path and dependent later phases are suppressed.

## Registration and TYPE bridge

The independent frontend now connects to the whole-program control plane
without returning to the hosted AST.

```text
SourceBundle
    -> GenericLexer
    -> TokenArena
    -> GenericParser
    -> SyntaxArena
    -> FrontendRegistrationPlan
    -> ProgramRegistry
    -> frontend TYPE resolution
    -> TypeArena + FunctionSignature/node-type associations
```

Registration retains unresolved source type syntax as whole-program NodeIds.
The TYPE bridge resolves those nodes into canonical compiler-owned TypeIds for:

- scalar/core primitive types;
- closed vector/map/set spellings;
- fixed arrays;
- shared/mutable references and slices;
- local and imported nominal records/enums;
- owner-sensitive type parameters;
- instantiated nominal generic types;
- function parameter/result signatures;
- record-field and enum-payload type metadata.

TYPE resolution is transactional. On failure, post-checkpoint TypeIds and
semantic signature/node-type associations are rolled back while the previously
committed ProgramRegistry remains intact.

This still does **not** perform expression/declaration semantic analysis. The
real-source `compile_program` path therefore fails closed at SEMANTIC after a
successful TYPE commit.

## Diagnostics

Lexical and parse failures remain the existing typed Python
`LexError`/`ParseError` diagnostics and retain their current
`DiagnosticCode` authority. This increment does not invent a parallel
diagnostic code family.

Frontend ingestion maps lexical/parse/registration failure codes into the
whole-program phase diagnostic path. The composition DiagnosticArena still
does not retain the complete source-span envelope, so full diagnostic
source-location preservation remains a later integration item.

## Complexity

For a source unit of length N characters and T tokens:

- normalization: O(N);
- UTF-8 byte-offset table construction: O(N);
- independent lexing: O(N);
- token materialization: O(T);
- independent recursive-descent parsing: O(T) for ordinary grammar paths,
  plus bounded lookahead scans used to disambiguate generic calls/qualifiers;
- reference parsing remains available only as a differential oracle;
- AST-to-SyntaxArena compatibility projection: O(number of AST values);
- direct node/token lookup: O(1);
- child traversal: O(child count).

No generic token or syntax identity is reconstructed by rescanning source.

## Non-goals

V1 does not:

- replace the default production Python compiler/parser path;
- replace the default production Python lexer path;
- implement a complete S3-native lexer;
- implement a complete S3-native parser;
- execute semantic expression passes;
- lower generic syntax to IR;
- emit artifacts;
- turn `compile_program` into source-to-output compilation;
- authorize self-host re-entry or Stage1 V4.

The hosted source frontend is now independent from both reference lexer and
reference parser decisions. A bounded ordinary-S3/native lexer and minimal
function parser slice is proven over the same token-vector and syntax
contracts. The next frontend frontier is broader native statement and
expression parsing; native semantic analysis, lowering, and emission remain
unclaimed.
