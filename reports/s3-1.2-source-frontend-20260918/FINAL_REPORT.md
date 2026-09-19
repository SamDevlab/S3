# S3 1.2 Source Frontend + Independent Generic Lexer/Parser

## Provenance

```text
BASE_MAIN_SHA=4c7aaf4ad59fdacdd83f230e11a0bd979081c80a
BRANCH=feat/s3-1.2-source-frontend
IMPLEMENTATION_SOURCE_HEAD=02a7b5ca2979c180b855b025c6bc75a0b1d72ef8
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

INDEPENDENT_GENERIC_LEXER=YES_HOSTED
REFERENCE_LEXER_DIFFERENTIAL_ORACLE=YES

INDEPENDENT_GENERIC_PARSER=YES_HOSTED_V0_6
REFERENCE_PARSER_DIFFERENTIAL_ORACLE=YES

GENERIC_SYNTAX_OUTPUT=YES_HOSTED
MULTI_FILE_SOURCE_BUNDLE=YES
SHARED_SYMBOL_NAMESPACE=YES

S3_TOKEN_ARENA_SHAPE=YES
S3_GENERIC_LEXER_STATE_SHAPE=YES
S3_GENERIC_PARSER_STATE_SHAPE=YES
```

The independent hosted source path is now:

```text
source
  -> GenericLexer
  -> direct-ID TokenArena
  -> GenericParser
  -> generic SyntaxArena
```

The compatibility/differential oracle remains:

```text
source
  -> production Python lexer
  -> TokenArena
  -> production Python parser
  -> transient hosted AST
  -> generic SyntaxArena
```

The independent path does not call the production `Lexer`/`tokenize`,
does not construct `bootstrap.s3.ast` values, and does not call
`bootstrap.s3.parser`.

The default production compiler/frontend remains unchanged.

## Generic lexer scope

The independent lexer mirrors the current token vocabulary and lexical contract:

- V0.6 indentation and dedentation;
- blank/comment lines;
- newline suppression inside parentheses/brackets;
- identifiers and keyword classification;
- integer and decimal float tokens;
- string literals with the existing escape-skipping behavior;
- three-character `<=>`;
- two-character operators `-> == != <= >= += *=`;
- punctuation/operator vocabulary;
- deterministic line/column and code-point compatibility positions;
- normalized UTF-8 byte spans;
- typed lexical and indentation diagnostics;
- V0.5 lexical compatibility for the legacy whitespace/comment mode.

The independent lexer shares only the stable `TokenKind` and `SyntaxMode`
vocabulary with the reference lexer. Lexical decisions are implemented in
`bootstrap/s3/generic_lexer.py`.

## Generic parser scope

The independent parser targets the default V0.6 grammar and directly handles:

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

## Tests authored

Focused tests now cover:

- TokenArena direct IDs and reference-token round trip;
- CRLF normalization and UTF-8 byte spans;
- generic lexer token-for-token parity against the reference lexer;
- keyword/operator/number/string/comment/indentation/delimiter behavior;
- lexical failure parity including diagnostic code/phase/location;
- V0.5 lexical parity;
- non-ASCII invalid-character parity;
- fully independent source -> TokenArena -> GenericParser -> SyntaxArena path;
- explicit monkeypatch guard that prevents both reference `tokenize` and
  `parse_tokens` from being called;
- independent parser output versus the reference projection on representative
  modules, records, enums, generics, calls, loops and match statements;
- malformed-source rejection;
- multi-file shared symbol identity;
- exported function flag preservation.

No local pytest/compileall/native result is claimed here because this ChatGPT
execution context has GitHub access but no shell access to the user's
Windows/Linux worktree. The branch is intentionally left ready for the user's
validation round.

## Architectural boundary

```text
PYTHON_REFERENCE_LEXER=YES_AS_ORACLE_AND_DEFAULT
PYTHON_REFERENCE_PARSER=YES_AS_ORACLE_AND_DEFAULT

INDEPENDENT_GENERIC_LEXER=YES_HOSTED
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

This PR must not be described as an S3-native frontend or self-hosted compiler.

## CI

Natural GitHub Actions for this branch continue to show the repository's known
pre-execution provisioning failure pattern with jobs reporting no steps.

```text
CI_STATE=INFRASTRUCTURE_BLOCKED_PRE_EXECUTION
CI_RERUN=NO
```

No test result is inferred from that infrastructure failure.

## Gate effect

```text
SELFHOST_GATE_2=IMPROVED_SOURCE_TOKEN_PARSER_STATE_REPRESENTATION
SELFHOST_GATE_3=HOSTED_GENERIC_LEXER_AND_PARSER_IMPLEMENTED_NATIVE_FRONTEND_PENDING
SELFHOST_GATE_4=UNCHANGED_CONTROL_PLANE_FROM_PR_300
SELFHOST_GATE_5=GENERIC_SYNTAX_DIRECT_FRONTEND_OUTPUT_SUPPORTED_HOSTED
SELFHOST_GATE_10=DIRECT_TOKEN_AND_NODE_IDS_PRESERVED
SELFHOST_GATE_11=FRONTEND_COMPLEXITY_DOCUMENTED
```

The next remaining frontend boundary after validation is:

```text
NEXT_SELFHOST_REPRESENTABILITY_BLOCKER=ORDINARY_S3_NATIVE_FRONTEND_EXECUTION
```

Ordinary-S3 token/lexer/parser state shapes now exist, but complete lexer/parser
algorithms have not yet been executed as ordinary S3/native code.

## Publication boundary

```text
READY_FOR_USER_TEST_ROUND=YES
READY_FOR_MAIN_MERGE=NO_VALIDATION_PENDING

RELEASE=NO
TAG=NO
PYPI=NO

SHUTDOWN_SCHEDULED=NO
SHUTDOWN_EXECUTED=NO
```
