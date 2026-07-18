# S3 0.28 Roadmap

Status: closed

S3 0.28 introduces an executable hosted output buffer model for the future S3
Assembly renderer. It is a scalar S3 model, not a textual renderer.

## Objective

Model the logical buffer which accepts the writer's numeric write IDs for the
`first`, `simple_call`, and `sign` fixtures. The buffer records fixture
capacity, cursor progress, write categories, legal transitions, final state,
overflow, counters, and a deterministic signature without retaining text.

## Scope

- Add `examples/self_hosting/assembly_renderer_output_buffer.s3`.
- Register its hosted return value of `0` in `s3_program_check`.
- Include it in `--candidate-run` and the candidate readiness gate.
- Validate capacities, cursor movement, writes, final states, counters,
  signatures, invalid fixtures and indexes, unknown writes and states, and an
  overflow probe.

## Guardrails

This milestone does not add runtime strings, string literals, arrays, heap,
stdlib, I/O, or textual Assembly rendering. It does not change inspect goldens,
candidate actual outputs, `AssemblyProgram.render()`, or
`render_supported_program()`.

`compare --check` remains blocked until a real textual S3 renderer exists.
S3 0.29 is not opened by this roadmap.
