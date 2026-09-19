# S3 1.2 Source Frontend Projection

## Provenance

```text
BASE_MAIN_SHA=4c7aaf4ad59fdacdd83f230e11a0bd979081c80a
BRANCH=feat/s3-1.2-source-frontend
IMPLEMENTATION_SOURCE_HEAD=785f67867c13392ff1b843d0b6baa6f97c24a88f
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
```

The hosted source path is:

```text
source
  -> production Python lexer
  -> direct-ID TokenArena
  -> reconstructed reference Token tuple
  -> production Python recursive-descent parser
  -> transient hosted AST
  -> generic SyntaxArena
```

The transient hosted AST is not the long-lived generic compiler model.

## Syntax-domain extension

The generic SyntaxArena now has parser-level representation for source type
nodes, array literals, type parameters, record fields, enum variants, call
arguments, record field values, match cases/payload labels, select arms, and
assignment target forms.

Parser-level function payloads may keep `return_type_id=-1` until semantic
resolution. The declared return type remains structurally present as a function
child node.

## Multi-file behavior

`parse_source_bundle` consumes the canonical `SourceBundle` ordering and uses
one shared `SymbolInterner` across all files. Equal symbol text therefore maps
to one symbol identity throughout the bundle.

## Validation state

A focused test file was added for:

- TokenArena direct IDs and reference-token round trip;
- CRLF normalization and UTF-8 byte spans;
- real source -> generic SyntaxArena projection;
- unresolved parser-level function TypeId handling;
- array/type-parameter anti-specialization shapes;
- reference parse failures;
- canonical SourceBundle order and shared symbols;
- invalid file IDs and invalid UTF-8.

ChatGPT does not have the user's local Windows/Linux worktree or shell in this
execution context, so no local pytest/compileall/native execution is claimed.

Natural PR CI ran and failed before any workflow steps:

```text
CI_RUNS=35416890549,35416890546,35416890567
CI_STATE=INFRASTRUCTURE_BLOCKED_PRE_EXECUTION
CI_JOB_STEPS=NULL_FOR_ALL_OBSERVED_JOBS
CI_RERUN=NO
```

No test result is inferred from that infrastructure failure.

## Architectural boundary

```text
PYTHON_REFERENCE_LEXER=YES
PYTHON_REFERENCE_PARSER_BACKEND=YES
INDEPENDENT_GENERIC_PARSER=NO
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
SELFHOST_GATE_2=IMPROVED_TOKEN_AND_SOURCE_FRONTEND_REPRESENTATION
SELFHOST_GATE_3=IMPROVED_BUT_PARSER_STILL_REFERENCE_BACKED
SELFHOST_GATE_4=UNCHANGED_CONTROL_PLANE_FROM_PR_300
SELFHOST_GATE_5=GENERIC_SYNTAX_DOMAIN_EXTENDED_FOR_PARSER_LEVEL_STRUCTURE
SELFHOST_GATE_10=NO_REGRESSION_EXPECTED
SELFHOST_GATE_11=SOURCE_PROJECTION_COMPLEXITY_DOCUMENTED
```

The largest remaining frontend blocker is:

```text
NEXT_SELFHOST_REPRESENTABILITY_BLOCKER=INDEPENDENT_GENERIC_PARSER_KERNEL
```

That blocker requires a parser that consumes TokenArena directly and builds the
same SyntaxArena without delegating grammar decisions to the hosted AST/parser.

## Publication boundary

```text
READY_FOR_MAIN_MERGE=NO_VALIDATION_PENDING
RELEASE=NO
TAG=NO
PYPI=NO
SHUTDOWN_SCHEDULED=NO
SHUTDOWN_EXECUTED=NO
```
