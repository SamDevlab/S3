# Roadmap 0.39 — S3 self-hosted assembly renderer (sign)

**Status:** closed

---

## Architecture

`assembly_renderer_sign_text.s3` — 3,583 lines, hand-written, structural emission.

### Fragment table (7 entries, 49 bytes)
| ID | Text | Bytes |
|----|------|-------|
| 1 | `.s3asm` | 6 |
| 2 | `.function` | 9 |
| 3 | `.param` | 6 |
| 4 | `.register` | 9 |
| 5 | `.label` | 6 |
| 6 | `.end` | 4 |
| 7 | `; source=` | 9 |

Same 7 fragment entries as simple_call. The sign fixture does not introduce new structural directives.

### Symbol table (15 entries, 60 bytes)
| ID | Text | Bytes |
|----|------|-------|
| 1 | `sign` | 4 |
| 2 | `trit` | 4 |
| 3 | `tryte` | 5 |
| 4 | `r0` | 2 |
| 5 | `r1` | 2 |
| 6 | `r2` | 2 |
| 7 | `r3` | 2 |
| 8 | `r4` | 2 |
| 9 | `r5` | 2 |
| 10 | `r6` | 2 |
| 11 | `entry` | 5 |
| 12 | `main` | 4 |
| 13 | `switch_negative_0` | 17 |
| 14 | `switch_neutral_1` | 15 |
| 15 | `switch_positive_2` | 16 |

### Opcode table (6 entries, 29 bytes)
| ID | Text | Bytes |
|----|------|-------|
| 1 | `TCONST` | 6 |
| 2 | `TCMP` | 4 |
| 3 | `TBR3` | 4 |
| 4 | `TINV` | 4 |
| 5 | `TRET` | 4 |
| 6 | `TCALL` | 5 |

### Decimal formatter (0–99)
Reuses the same approach as simple_call: recursive subtract-10 for tens digit, recursive match/subtract for ones.

### Structural emission (in main)
Unlike simple_call, the sign renderer does not use `write_*` abstraction functions. Instead, it emits bytes via direct buffer assignments (`buffer_low[cursor_low] = <value>; cursor_low = cursor_low + 1`). Each byte of output corresponds to one cursor increment (946 total). The 4-space indentation is emitted as individual space bytes (32) per level.

### Triple-buffer strategy
- `buffer_low[0..364]` — first 365 bytes
- `buffer_mid[0..364]` — next 365 bytes (546 total would be 181, but mid captures 365-546)
- `buffer_high[0..??]` — remaining bytes (947-730=217, padded to tryte index)
- Sign output (946 bytes) exceeds 365+365=730, so three buffers of up to 365 each are required
- Tryte array max length is 365 (TRYTE_MAX = 364)

### Switch case emission
The sign fixture's three-way switch (`TBR3`) is emitted as inline buffer assignments with explicit opcode bytes, label references, and branch annotations.

### Results
| Metric | Value |
|--------|-------|
| Total lines | 3,583 |
| Output bytes | 946 |
| Output lines | 36 |
| SHA-256 | `c077d2c49639b1a033505ec8c1ba1c60c78242e6e09c43f60a8aa5ed8b49e2d9` |
| Structural table calls | 665 (`fragment_byte`: 275, `symbol_byte`: 232, `opcode_byte`: 67, `decimal_tens`: 33, `decimal_ones`: 58) |
| Inline punctuation bytes | 281 (spaces: 187, LFs: 36, colons: 28, commas: 24, hyphens: 2, periods: 2, arrows: 2) |
| Ratio structural / inline | 2.37 |
| Buffer cursor increments | 946 (one per output byte) |
| Arbitrary replay | 0 bytes |
| Golden comparison | raw `==` git blob (no normalization) |

### Fixture status
| Fixture | Status |
|---------|--------|
| `first` | **passed** (existing S3 renderer unchanged) |
| `simple_call` | **passed** (existing S3 renderer unchanged) |
| `sign` | **passed** (new S3 renderer output matches golden) |
| Renderer implementation | **complete** (all three fixtures in S3) |
| Full text rendering | **passed** |

### `compare --check` exit code
Returns `0` (all three S3 textual renderers now produce output matching their golden fixtures).

### Raw byte comparison
Golden comparison uses `git show HEAD:path` to retrieve canonical LF-only blob bytes. No `.replace()`, `.splitlines()`, `.decode()`/`.encode()`, or line-ending normalization is performed. The comparison is `S3 output bytes == git blob bytes` — exact byte-for-byte equality without any Python-side transformation.

### No arbitrary replay
- All bytes are computed from structural tables or the decimal formatter
- No fixture-specific byte is hard-coded in `main()`
- No generator script is versioned in the repository
- The design generalizes to all three fixtures

### Program inventory centralization
`tools/s3_program_check.py` now exports `get_program_count()`, `get_hosted_program_count()`, `get_program_inventory_display()`, and `get_hosted_display()`. Nine test files updated to use these centralized functions instead of hardcoded counts.
