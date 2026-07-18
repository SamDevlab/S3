# S3 0.30 Roadmap

Status: closed

S3 0.30 adds an executable scalar command model for the next renderer stage:

```text
output buffer -> text builder commands -> text builder result
```

## Scope

`examples/self_hosting/assembly_renderer_text_builder.s3` models numeric
document, line, metadata, and finish commands for `first`, `simple_call`, and
`sign`. It validates builder transitions, line/command/newline/indentation/
token/metadata counters, final state, logical byte totals, and signatures.

The logical byte values use a base-300 block and remainder representation so
the 946-byte `sign` fixture remains exact within the scalar tryte subset.

## Guardrails

This milestone does not add runtime strings, string literals, arrays, heap,
stdlib, I/O, or a textual renderer. It does not change inspect goldens,
candidate actual outputs, `AssemblyProgram.render()`, or
`render_supported_program()`.

`compare --check` remains blocked. S3 0.31 is not opened by this roadmap.
