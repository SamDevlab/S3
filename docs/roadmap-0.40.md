# S3 0.40 — Consolidation of structural renderer contracts and reduction of duplication

**Status:** closed

## Duplication found

The three S3 textual renderers (`first`, `simple_call`, `sign`) contain significant structural duplication:

| Item | first | simple_call | sign |
|------|-------|-------------|------|
| Lines | 3208 | 1933 | 3583 |
| Output bytes | 441 | 448 | 946 |
| Output lines | 18 | 21 | 36 |
| Fragment tables | 11 | 7 | 7 |
| Symbol tables | 7 | 7 | 15 |
| Opcode tables | 5 | 4 | 6 |
| Decimal formatter | 3 functions | 3 functions | 3 functions |
| Buffer strategy | dual (300,300) | dual (300,300) | triple (364,364,218) |
| Fragment IDs shared with simple_call/sign | 1,2,5,6 | 1,2,3,4,5,6,7 | 1,2,3,4,5,6,7 |

Total lines across all three: 3208 + 1933 + 3583 = **8724 lines**.

Functions that are structurally identical (duplicated across files):
- `decimal_tens_byte` — identical algorithm in all three (recursive subtraction, ASCII tens digit)
- `decimal_ones_byte` — identical algorithm in all three (recursive subtraction, ASCII ones digit)
- `decimal_length` — identical algorithm in all three (1 if n <= 9 else 2)
- Fragment byte/length table structure — same pattern in all three (match on id, then match on index)
- Symbol byte/length table structure — same pattern in all three
- Opcode byte/length table structure — same pattern in all three
- Buffer write pattern — same inline `buffer_X[cursor_X] = value / cursor_X = cursor_X + 1` in all three

Functions that are nearly identical:
- `fragment_byte` / `fragment_length` — differ only in which fragment IDs and text values are defined
- `symbol_byte` / `symbol_length` — differ only in which symbols are defined
- `opcode_byte` / `opcode_length` — differ only in which opcodes are defined

Tables that could be shared if the language supported it:
- Fragment ID/name mapping for IDs 1-7 (used in simple_call and sign)
- Symbol "r0", "r1", "r2", "tryte", "entry" (used in all three, though with different IDs)
- Opcode "TRET" (used in all three), "TCONST" (used in all three)

Differences specific to each fixture:
- **first:** uses a flat ID space (fragments 1-11, symbols 12-155 mixed); has its own `text_byte_at` and `text_length` functions; decimal formatter uses `text_byte_at`/`text_length` functions not `fragment_byte`/`fragment_length`
- **simple_call:** uses separate tables (fragments 1-7, symbols 1-7, opcodes 1-4); decimal formatter is standalone
- **sign:** uses separate tables (fragments 1-7, symbols 1-15, opcodes 1-6); three-buffer output

## Language limitations

S3 has **no** module, import, include, library, or linking mechanism. The only code-reuse facility is defining and calling functions within a single `.s3` file. All three `.s3` files are standalone programs with their own `main()` entry point. Cross-file function sharing is impossible.

At milestone 0.40, S3 had no loops. Milestone 0.41 added `while` — see
`roadmap-0.41.md`.

Additionally, S3 still has no:

- References or pointers
- Structs or records
- Enums or sum types
- Dynamic strings or heap
- Arrays passed by reference
- Multiple return values

## Strategy chosen

**Strategy C — conceptual consolidation without physical sharing.**

Given the language limitations, physical code extraction is not possible. The milestone focuses on:
1. Centralizing all contract metadata in a Python source of truth
2. Standardizing naming and structure documentation
3. Removing Python-level duplication in tests and tools
4. Creating a generic buffer capture function usable by all fixtures
5. Adding contract consistency tests
6. Documenting the duplication honestly

## Contracts centralized

Created `tools/s3_renderer_contract.py` as the central source of truth for:
- Fixture metadata (paths, expected SHA-256, byte counts, line counts)
- Fragment ID/name tables per fixture
- Symbol ID/name tables per fixture
- Opcode ID/name tables per fixture
- Common fragment name mapping
- Buffer layout descriptions for each fixture
- Generic `_capture_fixture_output()` function
- `_git_blob_bytes()` helper for canonical raw bytes
- `verify_fixture_metadata()` function
- `audit_duplication()` function

## Writer standardization

The three S3 renderers continue to use inline buffer write patterns (`buffer_X[cursor_X] = value` followed by `cursor_X = cursor_X + 1`). No `write_*` abstraction functions are present in any of the three renderers — the S3 language lacks the expressiveness to abstract them without overhead.

Key naming conventions documented:
- Fragment byte lookup: `fragment_byte(id, index)` — same in all three
- Fragment length lookup: `fragment_length(id)` — same in all three
- Symbol byte lookup: `symbol_byte(id, index)` — same in all three
- Symbol length lookup: `symbol_length(id)` — same in all three
- Opcode byte lookup: `opcode_byte(id, index)` — same in all three
- Opcode length lookup: `opcode_length(id)` — same in all three
- Decimal tens: `decimal_tens_byte(n)` — same in all three
- Decimal ones: `decimal_ones_byte(n)` — same in all three
- Decimal length: `decimal_length(n)` — same in all three

## Fragment common IDs

Fragments with consistent IDs across simple_call and sign:
- ID 1: `.s3asm`
- ID 2: `.function`
- ID 3: `.param`
- ID 4: `.register`
- ID 5: `.label`
- ID 6: `.end`
- ID 7: `; source=`

The `first` renderer uses a different ID scheme developed before the convention was established:
- ID 1: `.s3asm`, ID 2: `.function`, ID 3: `.register`, ID 4: `.label`, ID 5: `.end`, ID 6: `->`, ID 7: ` ` (space), ID 8: `,`, ID 9: `; source=`, ID 10: `\n`, ID 11: `\r`

## Symbol common IDs

Symbol name overlap across fixtures (different IDs in first vs simple_call/sign):
- `tryte`: ID 12 in first, ID 7 in simple_call, ID 3 in sign
- `r0`: ID 130 in first, ID 4 in simple_call/sign
- `r1`: ID 131 in first, ID 5 in simple_call/sign
- `r2`: ID 132 in first, ID 6 in simple_call/sign
- `entry`: ID 101 in first, ID 3 in simple_call, ID 11 in sign
- `main`: ID 100 in first, ID 2 in simple_call, ID 12 in sign

IDs are consistent between simple_call and sign for r0-r2 but differ for tryte, entry, and main.

## Opcode common IDs

Opcode overlap:
- `TRET`: ID 124 in first, ID 2 in simple_call, ID 5 in sign
- `TCONST`: ID 120 in first, ID 3 in simple_call, ID 1 in sign
- `TCALL`: absent in first, ID 4 in simple_call, ID 6 in sign

## Formatter contract

All three renderers implement the same decimal formatter algorithm:

```
decimal_tens_byte(n): recursive, returns ASCII tens digit
decimal_ones_byte(n): recursive, returns ASCII ones digit
decimal_length(n): returns 1 if n <= 9 else 2
```

Supported values: 0, 1, 2, 4, 5, 9, 10, 12, 13, 14, 16, 17, 18, 19, 20, 21, 24, 35, 41, 42, 45, 47, 48, 49, 50, 51, 52, 53, 55, 56, 57, 58, 59, 78, 79, 85, 86, 90, 91, 94 (all within 0-99 range).

## Buffer layouts

| Fixture | Buffers | Capacities | Total capacity |
|---------|---------|------------|----------------|
| first | buffer_low, buffer_high | 300, 300 | 600 |
| simple_call | buffer_low, buffer_high | 300, 300 | 600 |
| sign | buffer_low, buffer_mid, buffer_high | 364, 364, 218 | 946 |

## Python generic layer

Created `_capture_fixture_output(source, buffer_count)` in `tools/s3_renderer_contract.py`:
- Loads S3 program, executes via `run_source_with_buffer_capture`
- Iterates buffer indices 0..buffer_count-1
- Concatenates non-zero bytes in buffer order
- Returns raw bytes
- Does NOT read golden files
- Does NOT normalize newlines
- Does NOT compare or format output

Used by:
- `compare_assembly_renderer.py` — `_render_s3_fixture()` now delegates to `_capture_fixture_output()`
- All three test files — `run_and_capture()` uses `_capture_fixture_output()`
- Contract tests — `test_capture_*` tests

## Metrics after/before

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Total S3 lines | 8724 | 8724 | 0 (no S3 files changed) |
| Python duplication | High (3x `_git_blob`, 3x `run_and_capture`, repeated constants) | Minimal (all centralized) | Significant reduction |
| Constant definitions | Scattered across 3 test files + tool | Centralized in contract | All in one place |
| Buffer capture code | 3 separate implementations | 1 generic function | -2 implementations |
| Fragment/symbol/opcode tables | Documented only inline in S3 files | Also documented in Python contract | Added documentation |

## Residual duplication

- All three S3 renderers remain physically separate files (language limitation)
- Fragment byte/length function structure is duplicated across all three files
- Symbol byte/length function structure is duplicated across all three files
- Opcode byte/length function structure is duplicated across all three files
- Decimal formatter is duplicated across all three files
- Buffer write pattern is duplicated within and across all three files
- First renderer uses incompatible ID scheme (pre-standardization artifact)

## Renderer state

- first: passed
- simple_call: passed
- sign: passed
- renderer implementation: complete
- full text rendering: passed
- compare --check: exit 0

## Recommendation for next milestone

1. Implement S3 module/import system (P1 in language gaps) to enable physical code sharing
2. If modules are available, extract common fragment, symbol, and opcode tables into a shared module
3. Standardize the first renderer's ID scheme to match simple_call/sign
4. Consider adding `write_*` helper functions if the language gains function call efficiency for small helpers
5. Evaluate whether decimal formatter can be shared across fixtures via modules
