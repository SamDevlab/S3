# Milestone 0.41 — `while` loop statement

Status: **open**

## Summary

Add a `while` loop statement to the S3 language, enabling iteration with a
ternary condition. The loop lowers directly to `JUMP`/`BRANCH3` IR opcodes
(no recursion, no new IR instructions).

## Contract

```s3
while condition:
    body
```

- `condition` must be a `trit` expression.
- The body executes while `condition` evaluates to `-1`.
- `0` and `1` terminate the loop immediately.
- The condition is re-evaluated before each iteration.
- The body executes in the same function frame (local variables and arrays
  are accessible and mutable).
- `break` and `continue` do not exist yet.

### Trit mapping (`BRANCH3`)

| Condition | Target   | Effect       |
|-----------|----------|--------------|
| `-1`      | body     | Executes body |
| `0`       | exit     | Terminates loop |
| `1`       | exit     | Terminates loop |

### Example

```s3
fn main() -> tryte:
    mut index: tryte = 0

    while index <=> 5:
        index = index + 1

    return index
```

## Implementation

### Files changed

| File | Change |
|------|--------|
| `bootstrap/s3/ast.py` | Added `WhileStatement(condition, body, location)` node; added to `Statement` union |
| `bootstrap/s3/lexer.py` | Added `WHILE` token kind and `"while"` keyword |
| `bootstrap/s3/parser.py` | Added `_parse_while_v0_6()` — parses condition, `:`, newline, indented block |
| `bootstrap/s3/semantic.py` | Added `_analyze_while()` — requires trit condition, analyzes body with `create_scope=True` |
| `bootstrap/s3/lowering.py` | Added `_lower_while()` — creates condition/body/exit blocks, BRANCH3 from condition, JUMP back from body |
| `bootstrap/s3/static_strings.py` | Added `WhileStatement` branch to static string visitor |

### IR structure

```
entry → JUMP → condition_block
condition_block → BRANCH3(condition, body, exit_0, exit_1)
body_block → ... → JUMP → condition_block
exit_0_block → JUMP → exit_block
exit_1_block → JUMP → exit_block
exit_block → ... (continuation)
```

Back edge: `body_block → condition_block` (JUMP). No recursion. No new
opcodes — reuses existing `JUMP` and `BRANCH3`.

### Backend compatibility

- Hosted emulator: already handles `TJMP` and `TBR3` with back edges.
- x86-64 native: already handles `TJMP` and `TBR3` with back edges.
- Optimizer: already handles cyclic CFGs (no change needed).
- Verifier: enforces 3 distinct BRANCH3 targets (exit uses two intermediate
  blocks, `exit_0` and `exit_1`, to satisfy this requirement).

### Tests added

| File | Tests |
|------|-------|
| `tests/test_s3_while_parser.py` | 11 tests (keyword, identifier, AST, condition, body, errors, nesting, match inside while) |
| `tests/test_s3_while_lowering.py` | 14 tests (trit condition, BRANCH3, back edge, terminators, targets, no recursion) |
| `tests/test_s3_while_execution.py` | 13 tests (iterations, accumulator, arrays, match, determinism) |
| `tests/test_s3_renderer_event_proof.py` | 18 tests (proof structure, while blocks, no unrolled assignments) |

## Proof

The proof in `examples/self_hosting/assembly_renderer_event_proof.s3` uses a
real `while` loop (8 iterations) to fill a local buffer, replacing the
previous unrolled `buffer[N] = ...` pattern.

## Remaining

- `break` / `continue` — not yet implemented
- `for` loop — not yet implemented
- Fixture consolidation (first, simple_call, sign) — separate milestone
