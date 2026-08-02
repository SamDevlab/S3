# Milestone 1.10 - Structured Result APIs

Status: Implementation complete locally in Draft PR #127; user validation pending.

Milestone 1.10 uses the aggregate-result machinery to support explicit,
nominal structured result APIs. S3 does not add exceptions, stack unwinding,
implicit propagation, a `?` operator, or a generic standard-library `Result`.

## Model

A structured result is an ordinary nominal enum with fixed payload layout:

```s3
record Error:
    code: tryte

enum Result:
    Ok(value: tryte)
    Err(error: Error)
```

Functions may return that enum as one logical value. Callers explicitly inspect
it with `match` and decide how to propagate or transform the error value.

## Guarantees

- Success and error variants use the same full-type width.
- The tag remains cell zero.
- Inactive payload cells are deterministic.
- Explicit propagation is ordinary source code, not hidden control flow.
- Imported result types preserve nominal identity.
- Copy-by-value semantics apply; no aliasing or borrowing is introduced.

## Non-Goals

- No exceptions.
- No implicit propagation.
- No generic result sugar.
- No heap allocation.
- No hidden references.

Tests for local, nested, imported, and returnable structured results were
authored. Tests added after the no-agent-testing policy change are not executed
by the agent and require user validation.
