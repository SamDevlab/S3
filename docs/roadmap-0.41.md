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

## Generic Structural Renderer: `first` completed

The generic structural renderer at `examples/self_hosting/assembly_renderer_generic_text.s3`
replaces the legacy `assembly_renderer_first_text.s3` for the `first` fixture.

### Event model (`first`)

178 purely structural events produce 441 bytes (18 lines, SHA-256
`46ebd2aef715d7a7e9f7ada01ca844b8ae23494ff6a5333f78c75db2eaca2f67`).

| Kind | Name | Count |
|------|------|-------|
| 1 | Fragment | 27 |
| 2 | Symbol | 20 |
| 3 | Opcode | 7 |
| 4 | Decimal | 27 |
| 5 | Colon | 14 |
| 6 | Space | 51 |
| 7 | Comma | 13 |
| 9 | Arrow | 1 |
| 10 | Newline | 18 |

- Zero arbitrary-byte events (no `RAW_BYTE`)
- Zero complete lines stored as fragments
- Zero position-based events
- Source coordinates are decomposed as `DECIMAL`, `COLON`, `DECIMAL`, `COLON`, `DECIMAL`
- No fragment used by `first` contains a digit, `:`, or newline
- 9 unique fragments, 8 unique symbols, 5 unique opcodes
- 2.48 bytes per event average

---

## Generic Structural Renderer: `simple_call` completed

The same `assembly_renderer_generic_text.s3` now also renders the `simple_call`
fixture via entry `render_simple_call`, replacing the legacy
`assembly_renderer_simple_call_text.s3`.

### Event model (`simple_call`)

175 purely structural events produce 448 bytes (21 lines, SHA-256
`d6de00c8c50618bcc8f3a458267eb8590956a9451980084b1add2f59d3267c0f`).

| Kind | Code | Name | Count |
|------|------|------|-------|
| Fragment | 1 | Text fragments | 28 |
| Symbol | 2 | Symbol names | 21 |
| Opcode | 3 | Opcode mnemonics | 6 |
| Decimal | 4 | Decimal numbers | 20 |
| Colon | 5 | `:` separator | 12 |
| Space | 6 | Whitespace (variable arg0) | 52 |
| Comma | 7 | `,` separator | 13 |
| Arrow | 9 | `->` operator | 2 |
| Newline | 10 | Line breaks | 21 |

- Zero `RAW_BYTE` (kind 11 is not used)
- Zero complete lines stored as fragments
- Zero position-based events
- Fragments, symbols, opcodes tables shared with `render_first`
- 14 unique fragments (incl. `.end`, `.label`, `; source=`)
- 7 unique symbols (`add`, `main`, `entry`, `r0`–`r2`, `tryte`)
- 4 unique opcodes (`TADD`, `TRET`, `TCONST`, `TCALL`)
- 2.56 bytes per event average
- Last event is Newline

### Key symbols & opcodes verified

- Symbol `add` (function name)
- Opcode `TCALL` (call instruction)
- Colon `:` appears in source comments (`; source=2:14:50`)

---

## Generic Structural Renderer: `sign` completed

The same generic renderer now also renders the `sign` fixture via entry
`render_sign`, while the legacy `assembly_renderer_sign_text.s3` remains
independent.

### Event model (`sign`)

342 purely structural events produce 946 bytes (36 lines, SHA-256
`c077d2c49639b1a033505ec8c1ba1c60c78242e6e09c43f60a8aa5ed8b49e2d9`).

| Kind | Name | Count |
|------|------|-------|
| 1 | Fragment | 49 |
| 2 | Symbol | 40 |
| 3 | Opcode | 14 |
| 4 | Decimal | 51 |
| 5 | Colon | 28 |
| 6 | Space | 98 |
| 7 | Comma | 24 |
| 9 | Arrow | 2 |
| 10 | Newline | 36 |

- Zero `RAW_BYTE` events
- Zero complete lines stored as fragments
- Zero position-based events
- Source coordinates are decomposed as `DECIMAL`, `COLON`, `DECIMAL`, `COLON`, `DECIMAL`
- No fragment used by `sign` contains a digit, `:`, comma, arrow, or newline
- Four output buffers are used: 300, 300, 300, and 46 bytes
- 2.77 bytes per event average

### New shared table entries

- Fragment 21: `trit`
- Symbols 10-14: `sign`, `r6`, `switch_negative_0`,
  `switch_neutral_1`, `switch_positive_2`
- Opcodes 106-107: `TCMP`, `TBR3`

`sign_generic` preserves byte-for-byte equality with both the canonical golden
and the legacy `sign` renderer.

---

## Shared architecture

`render_first`, `render_simple_call`, and `render_sign` share the same:

- `event_length(kind, arg0)` / `event_byte(kind, arg0, idx)` dispatch loop
- `fragment_length` / `fragment_byte` tables
- `symbol_length` / `symbol_byte` tables
- `opcode_length` / `opcode_byte` tables
- `decimal_length` / `decimal_tens_byte` / `decimal_ones_byte` / `decimal_byte_at` functions
- 300-byte segmented output buffers; `render_sign` adds a 46-byte tail buffer
- `while`-based event iteration (no unrolled assignments)

Event-specific tables (`first_event_kind`/`first_event_arg0`/`first_event_count`
`simple_call_event_kind`/`simple_call_event_arg0`/`simple_call_event_count`, and
`sign_event_kind`/`sign_event_arg0`/`sign_event_count`)
are separate per entry.

---

## Decimal bug fix

The `decimal_byte_at` function originally had a bug in the `value > 10` branch:
it always returned ASCII `"10"` (bytes 49, 48) for any value > 10, because the
`match value <=> 100:` sub-check was missing.

**Root cause:** the `1:` branch of `match value <=> 10` unconditionally
returned the tens digit as `49` ('1') and the ones digit as `value - 10 + 48`.
For values 11–19 this happened to be correct, but for 20–99 the tens digit was
always `'1'` instead of `'2'`–`'9'`.

**Fix:** Added two helper functions:

- `decimal_tens_byte(n)`: recursive, base case `n ≤ 9` returns 48 (`'0'`),
  otherwise `decimal_tens_byte(n - 10) + 1`. Correctly computes tens digit for
  any positive value.
- `decimal_ones_byte(n)`: recursive, base case `n ≤ 9` returns digit via
  10-match lookup table, otherwise `decimal_ones_byte(n - 10)`.

**Additionally:** `decimal_byte_at` now correctly handles three-digit values
100-191 as `'1'`, `decimal_tens_byte(value - 100)`, and
`decimal_ones_byte(value - 100)`.

### Supported decimal domain

The decimal formatter intentionally supports **0-191 inclusive**:

- 0-9: single digit via `value + 48`
- 10: hardcoded `"10"`
- 11-99: two digits via `decimal_tens_byte`/`decimal_ones_byte`
- 100: hardcoded `"100"`
- 101-191: `'1'` + `decimal_tens_byte(value - 100)` + `decimal_ones_byte(value - 100)`

### Outside domain

- Values outside 0-191 return `-1` (sentinel value) for `decimal_length`.
- `decimal_byte_at` returns `0` for values outside 0-191.
- `decimal_byte_at` returns `0` for negative indices or indices greater than
  or equal to the decimal length.
- Invalid decimal inputs do not produce `/`, `:`, garbage, or partial strings.
- `decimal_length` is explicitly bounded; values 192 and above return `-1`.

### Recursion assessment

- `decimal_tens_byte`: max depth 10 (for value 99). Each call is one
  subtraction. **Recursion acceptable** — bounded, matches legacy pattern,
  S3 runtime has no hard stack limit.
- `decimal_ones_byte`: max depth 10 (for value 99). Base case uses 10-match
  lookup. **Recursion acceptable.**

---

## Performance

| Fixture | Entry | Min limit | Current limit | Duration (500K) |
|---------|-------|-----------|---------------|-----------------|
| `first_generic` | `render_first` | ~200K | 500K | ~110s |
| `simple_call_generic` | `render_simple_call` | ~250K | 500K | ~115s |
| `sign_generic` | `render_sign` | 850K | 1100K | 825K exceeds limit; 850K passes |

- `first_generic` now has a slightly larger event table than
  `simple_call_generic` (178 vs 175 events) because source coordinates are
  decomposed structurally instead of stored in numeric fragments.
- `simple_call_generic` keeps its canonical 175-event plan and 448-byte output.
- `sign_generic` uses a 342-event plan and four buffers for the 946-byte output.
- Instruction limit measurement for `sign_generic`: 250K, 350K, 500K, 750K,
  800K, and 825K fail; 850K passes. The selected metadata limit is 1100K to
  keep an operational margin instead of treating the measured threshold as an
  exact dynamic cost.
- The current 500K limit provides ~2x safety margin over the minimum.
- Default max_instructions for other programs remains at 100K; generic entries
  use per-fixture measured limits.

---

## Testing

- `tests/test_s3_renderer_generic_text.py`: separated `render_first`
  structure tests from execution tests; the structure class compiles IR and
  audits the event plan without running the VM.
- `tests/test_s3_renderer_generic_simple_call.py`: separated
  `render_simple_call` structure tests from execution tests; the structure
  class compiles IR and audits the event plan without running the VM.
- `tests/test_s3_renderer_generic_sign.py`: separated `render_sign` structure
  tests from execution tests; the structure class compiles IR and audits the
  event plan without running the VM.
- `tests/test_decimal_functions.py`: decimal boundary and byte tests for the
  shared 0-191 contract, including invalid values and invalid indices.
- `tests/test_s3_renderer_contract.py`: includes `simple_call_generic` and
  `sign_generic` in
  contract verification; real zero-byte capture test
- `tools/compare_assembly_renderer.py --check`: validates 8 comparisons
  (3 legacy, 3 generic, and generic-vs-legacy for `simple_call` and `sign`)
- Legacy tests remain independent:
  - `test_s3_renderer_first_text.py` → `assembly_renderer_first_text.s3`
  - `test_s3_renderer_simple_call_text.py` → `assembly_renderer_simple_call_text.s3`
  - `test_s3_renderer_sign_text.py` → `assembly_renderer_sign_text.s3`

The previous generated `sign_generic` attempt remains rejected and is not part
of this branch state.

## Remaining

- `break` / `continue` — not yet implemented
- `for` loop — not yet implemented
