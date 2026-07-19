# S3 Program Check Foundation

`tools/s3_program_check.py` is a small inventory and compile check for S3
programs that may become future helper, library, or experimental compiler
component candidates.

This is not self-hosting. It does not call the native backend or replace any
Python compiler component. It only records a few stable S3 programs and checks
that the current Python compiler can still compile them. Inventory entries may
also opt into hosted execution with an expected return value.

Current commands:

```text
python tools/s3_program_check.py list
python tools/s3_program_check.py check
```

Current checked programs:

- `examples/first.s3`
- `examples/simple_call.s3`
- `examples/sign.s3`
- `examples/self_hosting/assembly_renderer_stub.s3`
- `examples/self_hosting/assembly_renderer_bootstrap.s3`
- `examples/self_hosting/assembly_renderer_output_model.s3`
- `examples/self_hosting/assembly_renderer_text_segments.s3`
- `examples/self_hosting/assembly_renderer_line_blueprints.s3`
- `examples/self_hosting/assembly_renderer_line_sequences.s3`
- `examples/self_hosting/assembly_renderer_line_encodings.s3`
- `examples/self_hosting/assembly_renderer_event_stream.s3`
- `examples/self_hosting/assembly_renderer_event_writer.s3`
- `examples/self_hosting/assembly_renderer_output_buffer.s3`
- `examples/self_hosting/assembly_renderer_pipeline.s3`
- `examples/self_hosting/assembly_renderer_text_builder.s3`

Conceptual gap examples under `examples/gaps/` are intentionally excluded
because they may contain pseudocode and are not part of the compile-check
inventory.

Programs under `examples/self_hosting/` may be future component stubs. They must
compile, but they do not need to implement the final component yet.

The Assembly renderer candidate stub exposes `renderer_candidate_status()` as a
minimal status API; its stub value does not mean the renderer is implemented.
That status delegates to `renderer_candidate_capability_smoke()`, a hosted
assertion smoke that reaches scalar count, selected ID, range, and support
predicate functions while still returning `-1` for the stub state.
`tools/compare_assembly_renderer.py --candidate-run` executes that stub through
the hosted path and confirms that `main` still returns `-1`.
`tools/s3_program_check.py check` also executes that stub because its inventory
entry declares `hosted expected return: -1`. Other inventory entries remain
compile-only until they opt into hosted execution.

The renderer candidate manifest records the same inventory path and hosted
expected return, so the general S3 program check and the renderer candidate run
share one hosted coverage contract for the stub.

S3 0.20 adds the executable renderer bootstrap spike at
`examples/self_hosting/assembly_renderer_bootstrap.s3`. It is registered with
`hosted expected return: 0`, so `tools/s3_program_check.py check` compiles and
executes it through the hosted path. The spike validates scalar invariants for
the supported opcode/directive subset, fixture line counts, representative
operand shapes, and an unknown-opcode negative case. It is not a full textual
renderer.

S3 0.21 adds the executable renderer output model at
`examples/self_hosting/assembly_renderer_output_model.s3`. It is also
registered with `hosted expected return: 0`, so the program check compiles and
executes it through the hosted path. The model calculates structural metrics for
the `first`, `simple_call`, and `sign` Assembly outputs, including line,
function, parameter, register, memory, label, instruction, directive, and
distinct opcode counts, without using runtime strings or arrays.

S3 0.22 adds the executable renderer text segment model at
`examples/self_hosting/assembly_renderer_text_segments.s3`. It is registered
with `hosted expected return: 0`, so the program check compiles and executes it
through the hosted path. The model assigns scalar numeric IDs to Assembly text
segment kinds such as directives, instruction lines, blank lines, and source
metadata markers, then validates segment metrics for `first`, `simple_call`,
and `sign` without using runtime strings or arrays.

S3 0.23 adds the executable renderer line blueprint model at
`examples/self_hosting/assembly_renderer_line_blueprints.s3`. It is registered
with `hosted expected return: 0`, so the program check compiles and executes it
through the hosted path. The model assigns one primary scalar numeric blueprint
to each current Assembly output line for `first`, `simple_call`, and `sign`,
including an instruction-with-source variant for source metadata, without using
runtime strings or arrays.

S3 0.24 adds the executable renderer line sequence model at
`examples/self_hosting/assembly_renderer_line_sequences.s3`. It is registered
with `hosted expected return: 0`, so the program check compiles and executes it
through the hosted path. The model records ordered scalar blueprint IDs for the
same fixtures and validates expected IDs by index, valid and invalid blueprint
transitions, function boundaries, fixture totals, and a small deterministic
signature without using runtime strings or arrays.

S3 0.25 adds the executable renderer line content encoding model at
`examples/self_hosting/assembly_renderer_line_encodings.s3`. It is registered
with `hosted expected return: 0`, so the program check compiles and executes it
through the hosted path. The model records scalar category, directive, opcode,
register-arity, operand-flag, source-metadata, ordinal, total, and signature
encodings for the same fixtures without using runtime strings or arrays.

S3 0.26 adds the executable renderer event stream model at
`examples/self_hosting/assembly_renderer_event_stream.s3`. It is registered
with `hosted expected return: 0`, so the program check compiles and executes it
through the hosted path. The model records ordered scalar renderer events,
payload classes, event transitions, event counts, and deterministic signatures
for the same fixtures without using runtime strings or arrays.

S3 0.27 adds the executable renderer event writer state model at
`examples/self_hosting/assembly_renderer_event_writer.s3`. It is registered
with `hosted expected return: 0`, so the program check compiles and executes it
through the hosted path. The model consumes ordered scalar renderer events and
validates writer states, line advancement, emitted counts, opened/closed
function balance, final state, and deterministic signatures without using
runtime strings or arrays.

S3 0.28 adds the executable hosted renderer output buffer model at
`examples/self_hosting/assembly_renderer_output_buffer.s3`. It is registered
with `hosted expected return: 0`, so the program check compiles and executes it
through the hosted path. The model consumes numeric writer writes and validates
fixture capacities, cursors, buffer states, write counters, overflow behavior,
and deterministic final-buffer signatures without using runtime strings or
arrays.

S3 0.29 adds the executable renderer pipeline model at
`examples/self_hosting/assembly_renderer_pipeline.s3`. It is registered with
`hosted expected return: 0`, so the program check compiles and executes it
through the hosted path. The model connects numeric event stream, event writer,
output buffer, and final result IDs; it validates stage transitions, counts,
states, capacity, cursor, signatures, and negative probes without runtime
strings or arrays.

S3 0.30 adds the executable renderer text builder command model at
`examples/self_hosting/assembly_renderer_text_builder.s3`. It is registered
with `hosted expected return: 0`, and models numeric builder commands after the
output-buffer/pipeline stages. It validates command order, builder states,
logical byte pairs, counters, transitions, negative probes, and deterministic
signatures without runtime strings or arrays.

S3 0.31 adds the executable renderer static text fragment model at
`examples/self_hosting/assembly_renderer_text_fragments.s3`. It is registered
with `hosted expected return: 0`, expands the 0.30 command sequence into
numeric static fragment categories, and verifies deterministic fragment counts,
states, source metadata, newlines, blank lines, signatures, and normalized
base-300 byte pairs. `tools/s3_program_check.py check` now reports 16 programs
and 13 hosted executions. The model has no runtime strings or arrays.

The same stub is also included in golden inspect coverage as
`assembly_renderer_stub`, which records its current IR and Assembly outputs
without treating it as a real renderer.

The stub also exposes scalar capability functions for the renderer subset:
`renderer_supported_directive_count()` and
`renderer_supported_opcode_count()`. They report the current subset manifest
counts only; `compare_assembly_renderer.py --check` remains blocked.

It also exposes scalar ID functions for each supported directive and opcode.
Those IDs are deterministic constants that follow the subset manifest order;
they are not Assembly rendering.

The stub also declares scalar first/last ID ranges for directives and opcodes,
plus scalar support predicates for those ID ranges. These APIs are metadata for
the candidate stub and do not make the renderer implemented.
