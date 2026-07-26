# S3 0.48 — Compound Assignment (`+=`)

**Status**: Completed

## Summary
Implements compound assignment (`+=`) for scalar mutable variables and indexed mutable array elements in S3 source syntax V0.6.

## Syntax & Grammar
```ebnf
assignment-statement = identifier-target, ( "=" | "+=" ), initializer, newline ;
```

## Semantics
- Evaluates the target (and index, if indexed) **exactly once**.
- Requires the target variable or array element to be declared `mut`.
- Performs addition (`+`) with the RHS value and stores the result back to the target.
- Emits standard `ADD` IR instruction; no new IR opcodes or runtime routines introduced.
