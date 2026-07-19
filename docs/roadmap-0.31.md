# S3 0.31 Roadmap

Status: closed

S3 0.31 adds the executable static text fragment stage for the renderer
bootstrap:

```text
text builder commands -> static numeric text fragments -> logical document
```

## Scope

`examples/self_hosting/assembly_renderer_text_fragments.s3` expands the same
numeric command order used by the 0.30 text builder into numeric fragment IDs.
The IDs cover the document marker, directives, opcodes, symbols, type and
register names, immediates, separators, spaces, indentation, source metadata,
newlines, blank lines, and document end. The model contains no rendered text.

The `first`, `simple_call`, and `sign` inspect goldens are decomposed into 137,
145, and 266 fragments respectively. Their final logical byte pairs are
`(1, 141)`, `(1, 148)`, and `(3, 46)` in base 300, representing 441, 448,
and 946 bytes. The same model validates line counts of 18, 21, and 36.

Fixed category widths are derived from the current static renderer grammar:
document marker 6, directive/opcode 6, type 4, register 2, separator/space/
newline 1, indentation 4, source prefix 10, source-value base 6, and document
end 4. Numeric fixture adjustments account for the variable spelling widths of
real directives, symbols, types, immediates, separators, and source values.
The pair accumulator normalizes its low component below 300 and has negative
probes for invalid pairs, invalid carries, and mismatched totals.

## Integration and guardrails

There are now twelve executable S3 renderer bootstrap artifacts.
`tools/s3_program_check.py check` registers the fragment model with hosted
expected return `0`, and `--candidate-run` reports `s3 text fragment model:
passed`.

This milestone does not add runtime strings, string literals, arrays, heap,
stdlib, I/O, or a complete textual S3 renderer. It does not change inspect
goldens, candidate actual outputs, `AssemblyProgram.render()`, or
`render_supported_program()`.

`compare --check` remains blocked with exit code 1. S3 0.32 is not opened by
this roadmap.
