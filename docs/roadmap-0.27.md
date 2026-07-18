# S3 0.27 Roadmap

Initial status: open for this PR.

Status: closed in this PR.

S3 0.27 adds a practical event writer state model for the future S3 Assembly
renderer. It is an executable S3 artifact, not the real renderer.

## Objective

Model a deterministic writer state machine that consumes the ordered renderer
events from S3 0.26 for the existing `first`, `simple_call`, and `sign`
fixtures.

The model records state before and after each event, line advancement, emitted
event counts, directive/instruction/blank counts, opened and closed function
counts, last emitted event, legal writer transitions, expected final state, and
compact final-state signatures without runtime strings or arrays.

## Delivered

- Added `examples/self_hosting/assembly_renderer_event_writer.s3`.
- Registered it in `tools/s3_program_check.py` with hosted expected return `0`.
- Extended `tools/compare_assembly_renderer.py --candidate-run` to execute it.
- Extended the candidate readiness gate to require `s3 event writer model:
  passed`.
- Added `tests/test_s3_renderer_event_writer.py`.
- Updated comparison, self-hosting, program-check, and README documentation.

## Writer States

The model uses stable scalar IDs for:

- writer start;
- after header;
- in function;
- after label;
- after instruction;
- after end;
- after blank;
- done;
- error.

## Current Metrics

| Fixture | Events | Line advances | Directives | Instructions | Blanks | Functions | Ends | Final state | Signature |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `first` | 18 | 18 | 10 | 7 | 1 | 1 | 1 | done | 70 |
| `simple_call` | 21 | 21 | 13 | 6 | 2 | 2 | 2 | done | 81 |
| `sign` | 36 | 36 | 20 | 14 | 2 | 2 | 2 | done | 126 |
| Total | 75 | 75 | 43 | 27 | 5 | 5 | 5 | done | 277 |

## Coverage

The executable model validates writer state transitions for the renderer event
stream, including header, blank, function, param, register, memory, label,
instruction, and end events. It checks fixture state continuity, expected final
state, last event, line advancement, counters, opened/closed function balance,
and deterministic signatures.

The model also validates negative probes for unknown fixtures, out-of-range
indexes, unknown events, unknown writer states, and invalid writer transitions.
The full fixture validators remain available as targeted entrypoints, while
`main` uses a bounded representative self-check that stays within the hosted
execution limit.

## Non Goals

S3 0.27 does not render text, does not add runtime strings, does not add arrays
to the model, does not update inspect goldens or candidate actual outputs, does
not alter `AssemblyProgram.render()` or `render_supported_program()`, and does
not mark the real S3 renderer implemented.

This roadmap is closed by the 0.27 delivery, and it does not open or define
0.28. `compare --check` remains blocked until a real textual S3 renderer
exists.
