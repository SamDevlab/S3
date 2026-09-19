# S3 1.2 Source Frontend + Independent Generic Lexer/Parser

## Provenance

```text
BASE_MAIN_SHA=4c7aaf4ad59fdacdd83f230e11a0bd979081c80a
BRANCH=feat/s3-1.2-source-frontend
IMPLEMENTATION_SOURCE_HEAD=1b6f28596f504deb71822e417c8e7cff9296bf2b
SOURCE_CHANGED_AFTER_IMPLEMENTATION_HEAD=NO
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

FRONTEND_PROGRAM_REGISTRATION=YES_HOSTED
FRONTEND_CONTROL_PLANE_INGESTION=YES_INPUT_SYNTAX_REGISTRATION_TYPE
FRONTEND_TYPE_RESOLUTION=YES_HOSTED_CANONICAL_TRANSACTIONAL
COMPILE_PROGRAM_REAL_SOURCE=YES_STOPS_AT_SEMANTIC
PROGRAM_REGISTRY_IMPORT_VISIBILITY=ENFORCED
PROGRAM_REGISTRY_TYPE_IMPORT_ALIAS=REJECTED_PER_LANGUAGE_CONTRACT
PROGRAM_REGISTRY_MODULE_CYCLES=REJECTED
NOMINAL_FIELD_RANGES=PER_TYPE
NOMINAL_TYPE_SYNTAX_RETENTION=YES
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

The independent frontend is additionally bridged into the whole-program
control plane. A fresh context now consumes real source through INPUT, SYNTAX,
REGISTRATION, and canonical TYPE resolution. `compile_program` uses this path
when prepared test artifacts are absent and fails closed at SEMANTIC with
`S3E_SEMANTIC_PHASE_UNAVAILABLE`.

The registration bridge derives deterministic module/function/nominal/import/
export identities directly from generic syntax. Implicit module identity follows
the existing module-graph logical-path authority. ProgramRegistry also enforces
import visibility, rejects module import cycles, scopes field/variant ranges per
nominal type, and retains field/payload type-syntax IDs consumed by TYPE.

The TYPE bridge resolves primitives, closed collections, arrays,
references/slices, local/imported nominals, owner-sensitive type parameters,
and instantiated nominal generics into canonical TypeArena identities. It
publishes function signatures and node-type associations transactionally.
A TYPE failure rolls back new TypeArena/SemanticState changes while preserving
the committed ProgramRegistry.

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

## Bounded ordinary-S3 execution slice

The candidate now contains a small executable ordinary-S3 lexer slice in
`selfhost/substrate/generic_lexer_state.s3`. It scans bounded source shapes,
emits direct IDs/kinds/spans, and returns the independent hosted digests 1509
(`fn main`/`0`), 2101 (parentheses), 2285 (`entry`/`42`), and 2375
(`worker`/`7`). The latter cases exercise arbitrary identifier advancement
and multi-digit/single-digit integer scanning rather than the original
fixture literals. The focused regression computes the independent hosted
`GenericLexer` digest for each source and compares the results.

```text
ORDINARY_S3_LEXER_SLICE=PASS_HOSTED_AND_LINUX_NATIVE
ORDINARY_S3_NATIVE_FRONTEND_EXECUTION=PARTIALLY_PROVEN
S3_NATIVE_LEXER=PARTIAL
S3_NATIVE_PARSER=NO
```

The Windows run records the Linux-native marker as an expected platform skip.
The same test passed on the Linux x86-64 VM with `5 passed`, covering four
hosted cases and the native parametrized case. Remote Linux compileall also
passed.

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
- exported function flag preservation;
- private-import rejection, module-cycle rejection, and unsupported type-import
  alias rejection in the registration path;
- primitive/array/reference/collection type resolution;
- local/imported nominal identity resolution;
- owner-sensitive generic type parameters and nominal instantiation;
- function signature publication and record/enum member type metadata;
- TYPE rollback while preserving committed registration.
- bounded ordinary-S3 lexer slice parity with the independent hosted digest;
- parenthesis-token differential behavior;
- platform-gated native qualification for that slice.

Validation performed on the Windows checkout and Linux x86-64 VM:

- `tests/test_native_frontend_slice.py`: 4 hosted cases passed, 1 expected
  Windows platform skip;
- affected frontend tests: 55 passed;
- `python -m compileall -q bootstrap tools tests`: PASS;
- `git diff --check`: PASS.
- Linux VM `tests/test_native_frontend_slice.py`: 5 passed;
- Linux VM compileall: PASS.

The final full suite on
`1b6f28596f504deb71822e417c8e7cff9296bf2b` exited 0 after the arbitrary
identifier/integer slice. The subsequent report-only publication commit
changes no executable, compiler, or test logic.

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
COMPILE_PROGRAM_REAL_SOURCE_TO_TYPE=YES
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

The next remaining self-host frontend boundary after validation is:

```text
NEXT_SELFHOST_REPRESENTABILITY_BLOCKER=ORDINARY_S3_NATIVE_FRONTEND_EXECUTION
```

For the hosted compiler architecture, the next legal control-plane phase is
SEMANTIC. Canonical declaration type resolution is implemented; expression and
declaration semantic analysis, lowering and emission remain unimplemented. Ordinary-S3 token/lexer/parser state shapes
exist, but complete lexer/parser algorithms have not yet been executed as
ordinary S3/native code.

## Publication boundary

```text
READY_FOR_USER_TEST_ROUND=YES
READY_FOR_MAIN_MERGE=NO_REMOTE_CHECKS_PENDING

RELEASE=NO
TAG=NO
PYPI=NO

SHUTDOWN_SCHEDULED=NO
SHUTDOWN_EXECUTED=NO
```
