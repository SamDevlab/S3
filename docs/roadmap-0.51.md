# S3 0.51 — Explicit Discard (`discard expression`)

**Status**: Completed

## Summary
Implements explicit discard statements `discard expression` in S3 source syntax V0.6 for evaluating expressions with side-effects without binding or storing their results.

## Syntax & Grammar
```ebnf
discard-statement = "discard", expression, newline ;
```

## Semantics
- Evaluates `expression` (executing any function calls or side-effects).
- Discards the resulting value.
- Keyword `discard` is reserved in V0.6 and preserved as an identifier in V0.5.
