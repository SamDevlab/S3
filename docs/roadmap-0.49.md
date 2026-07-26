# S3 0.49 — Single-Bound Range (`range(end)`)

**Status**: Completed

## Summary
Implements single-bound range expressions `range(end)` in `for-in-range` statements, defaulting the start bound to `0`.

## Syntax & Grammar
```ebnf
range-clause = "range", "(", [ expression, "," ], expression, ")" ;
```

## Semantics
- `range(end)` is normatively equivalent to `range(0, end)`.
- Start bound is synthesized as a `0` constant.
- End bound is evaluated exactly once.
