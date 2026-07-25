# S3 0.50 — Stepped Range (`range(start, end, step)`)

**Status**: Completed

## Summary
Implements stepped range expressions `range(start, end, step)` in `for-in-range` statements, supporting positive and negative constant steps.

## Syntax & Grammar
```ebnf
range-clause = "range", "(", [ expression, "," ], expression, [ ",", expression ], ")" ;
```

## Semantics
- `start`, `end`, and `step` are all evaluated **exactly once** before loop entry.
- `step` zero (`0`) is invalid and rejected during semantic analysis.
- Positive steps (`step > 0`) iterate while `current < end`.
- Negative steps (`step < 0`) iterate while `current > end`.
- No new IR opcodes or runtime routines introduced.
