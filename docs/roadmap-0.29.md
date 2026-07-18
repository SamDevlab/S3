# S3 0.29 Roadmap

Status: closed

S3 0.29 adds the first executable scalar model of the complete bootstrap
renderer pipeline. It connects the existing event stream, event writer, and
output buffer models to a final pipeline result without emitting Assembly text.

## Objective

Validate the logical renderer flow for `first`, `simple_call`, and `sign`:

```text
event stream -> event writer -> output buffer -> pipeline result
```

The model uses numeric fixture, stage, state, result, counter, and signature
IDs only. It validates event/write/line consistency, writer and buffer final
states, cursor and capacity, fixture and total signatures, stage transitions,
and negative fixture, stage, result, count, signature, overflow, and final
state probes.

## Scope

- Add `examples/self_hosting/assembly_renderer_pipeline.s3`.
- Register its hosted return value of `0` in `s3_program_check`.
- Include it in `--candidate-run` and the candidate readiness gate.
- Keep `compare --check` blocked because no textual S3 renderer exists.

## Guardrails

This milestone does not add runtime strings, string literals, arrays, heap,
stdlib, I/O, or textual Assembly rendering. It does not change inspect goldens,
candidate actual outputs, `AssemblyProgram.render()`, or
`render_supported_program()`.

S3 0.30 is not opened by this roadmap.
