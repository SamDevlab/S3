# S3 1.2 Source Frontend + Independent Generic Parser

## Provenance

```text
BASE_MAIN_SHA=4c7aaf4ad59fdacdd83f230e11a0bd979081c80a
BRANCH=feat/s3-1.2-source-frontend
IMPLEMENTATION_SOURCE_HEAD=fe07718ea9e1c4b2db26f36340d57ad191d4b4da
PR=301
PR_STATE=OPEN_DRAFT
PR_MERGED=NO
```

## Implemented

```text
REAL_SOURCE_INPUT=YES
SOURCE_POSITION_AUTHORITY=NORMALIZED_UTF8_BYTES
LINE_ENDING_AUTHORITY=NORMALIZED_LF
GENERIC_TOKEN_ARENA=YES_HOSTED
TOKEN_IDS=DIRECT_STABLE
GENERIC_SYNTAX_OUTPUT=YES_HOSTED
MULTI_FILE_SOURCE_BUNDLE=YES
SHARED_SYMBOL_NAMESPACE=YES
S3_TOKEN_ARENA_SHAPE=YES
INDEPENDENT_GENERIC_PARSER=YES_HOSTED_V0_6
REFERENCE_PARSER_DIFFERENTIAL_ORACLE=YES
S3_GENERIC_PARSER_STATE_SHAPE=YES
```

Two explicit hosted source paths now exist.

Reference/differential path:

```text
source
  -> production Python lexer
  -> direct-ID TokenArena
  -> reconstructed reference Token tuple
  -> production Python recursive-descent parser
  -> transient hosted AST
  -> generic SyntaxArena
```

Independent parser path:

```text
source
  -> production Python lexer
  -> direct-ID TokenArena
  -> GenericParser
  -> generic SyntaxArena
```

The independent `GenericParser` does not import or construct
`bootstrap.s3.ast` values and does not call `bootstrap.s3.parser`.

The default production compiler/parser is unchanged.

## Generic parser scope

The independent parser currently targets the default V0.6 grammar and directly
handles:

- module declarations and imports;
- functions and foreign functions;
- exported function/record/enum flags in generic syntax payloads;
- generic type parameters;
- record and enum declarations;
- parameters and parser-level type structure;
- arrays, references, slices and nominal/generic type syntax;
- variable declarations and assignments;
- compound `+=` assignments;
- return/discard/break/continue;
- while and range-for statements;
- match statements and match expressions;
- select statements;
- unary and binary precedence;
- calls and generic calls;
- record construction;
- field/index/slice postfix expressions;
- address-of and dereference.

V0.5 is intentionally not migrated by this kernel.

## Syntax-domain corrections

The generic SyntaxArena now has parser-level representation for source type
nodes, array literals, type parameters, record fields, enum variants, call
arguments, record field values, match cases/payload labels, select arms, and
assignment target forms.

Parser-level `FunctionPayload.return_type_id` may remain `-1` until semantic
resolution, while the declared type is structurally present as a function
child. `FunctionPayload.flags` now preserves declaration flags such as
`export`.

The earlier source bridge incorrectly referenced `SourceLocation.position`;
that was corrected to the canonical `SourceLocation.offset`.

## Multi-file behavior

Both reference-bridge and independent paths can consume canonical
`SourceBundle` ordering. One shared `SymbolInterner` is used across source
units, so equal symbol text receives one stable symbol identity throughout the
bundle.

## Tests authored

Focused tests now cover:

- TokenArena direct IDs and reference-token round trip;
- CRLF normalization and UTF-8 byte spans;
- real source -> generic SyntaxArena projection;
- parser-level unresolved TypeIds;
- array/type-parameter anti-specialization shapes;
- malformed reference parser inputs;
- canonical multi-file ordering and shared symbols;
- invalid file IDs and invalid UTF-8;
- independent parser output versus the reference bridge on representative
  modules, records, enums, generics, calls, loops and match statements;
- malformed-source rejection by the independent parser;
- multi-file independent parsing;
- an explicit monkeypatch guard proving the independent path does not call the
  reference `parse_tokens` bridge.

No local pytest result is claimed here because this ChatGPT execution context
has GitHub access but no shell access to the user's Windows/Linux worktree.

## CI

Natural PR CI has repeatedly exhibited the repository's known provisioning
failure pattern. The initial observed PR jobs returned no steps.

```text
CI_STATE=INFRASTRUCTURE_BLOCKED_PRE_EXECUTION
CI_RERUN=NO
```

No test result is inferred from infrastructure failure.

## Architectural boundary

```text
PYTHON_REFERENCE_LEXER=YES
PYTHON_REFERENCE_PARSER_BACKEND=YES_AS_ORACLE_COMPATIBILITY_PATH
INDEPENDENT_GENERIC_PARSER=YES_HOSTED_V0_6
S3_NATIVE_LEXER=NO
S3_NATIVE_PARSER=NO
SEMANTIC_EXPRESSION_ANALYZER=NO
GENERIC_LOWERING=NO
EMITTER=NO
TRUE_SOURCE_TO_OUTPUT_COMPILE_PROGRAM=NO
SELFHOST_REENTRY_AUTHORIZED=NO
STAGE1_V4=NOT_AUTHORIZED
STAGE1_V4_STARTED=NO
```

This PR must not be described as an S3-native parser or self-hosted compiler.

## Gate effect

```text
SELFHOST_GATE_2=IMPROVED_TOKEN_AND_PARSER_STATE_REPRESENTATION
SELFHOST_GATE_3=HOSTED_GENERIC_PARSER_IMPLEMENTED_BUT_LEXER_AND_NATIVE_FRONTEND_PENDING
SELFHOST_GATE_4=UNCHANGED_CONTROL_PLANE_FROM_PR_300
SELFHOST_GATE_5=GENERIC_SYNTAX_DOMAIN_EXTENDED_FOR_DIRECT_PARSER_OUTPUT
SELFHOST_GATE_10=DIRECT_TOKEN_AND_NODE_IDS_PRESERVED
SELFHOST_GATE_11=PARSER_COMPLEXITY_BOUNDED_BY_RECURSIVE_DESCENT_AND_ARENA_APPEND
```

The largest remaining source-frontend blocker is:

```text
NEXT_SELFHOST_REPRESENTABILITY_BLOCKER=INDEPENDENT_GENERIC_LEXER_KERNEL
```

The current independent parser no longer depends on the hosted AST/parser, but
real source tokenization still delegates lexical decisions to the production
Python lexer. A future lexer kernel must populate the same TokenArena contract
without Python lexical callbacks before ordinary-S3/native frontend execution
can be claimed.

## Publication boundary

```text
READY_FOR_MAIN_MERGE=NO_VALIDATION_PENDING
RELEASE=NO
TAG=NO
PYPI=NO
SHUTDOWN_SCHEDULED=NO
SHUTDOWN_EXECUTED=NO
```
