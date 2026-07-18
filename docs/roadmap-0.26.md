# S3 0.26 Roadmap

Initial status: open for this PR.

Status: closed in this PR.

S3 0.26 adds a practical event stream model for the future S3 Assembly
renderer. It is an executable S3 artifact, not the real renderer.

## Objective

Model each current rendered Assembly line as one ordered renderer emission
event for the existing `first`, `simple_call`, and `sign` fixtures.

The model builds on the S3 0.23 blueprint IDs, S3 0.24 sequence coverage, and
S3 0.25 line content encodings. It adds event IDs, payload classes, event
payload validation, transition validation, fixture counts, negative probes, and
compact deterministic event/payload signatures without runtime strings or
arrays.

## Delivered

- Added `examples/self_hosting/assembly_renderer_event_stream.s3`.
- Registered it in `tools/s3_program_check.py` with hosted expected return `0`.
- Extended `tools/compare_assembly_renderer.py --candidate-run` to execute it.
- Extended the candidate readiness gate to require `s3 event stream model:
  passed`.
- Added `tests/test_s3_renderer_event_stream.py`.
- Updated comparison, self-hosting, program-check, and README documentation.

## Event Kinds

The model uses stable scalar IDs for:

- unknown event;
- header emission;
- function emission;
- param emission;
- register emission;
- memory emission;
- label emission;
- instruction emission;
- end emission;
- blank-line emission.

## Payload Classes

The model uses stable scalar IDs for:

- no payload;
- directive payload;
- symbol payload;
- register declaration payload;
- memory declaration payload;
- instruction payload without operands;
- instruction payload with registers;
- instruction payload with an immediate;
- instruction call payload;
- instruction branch payload;
- instruction memory payload;
- source metadata payload;
- blank payload.

## Current Metrics

| Fixture | Events | Transitions | Header | Function | Param | Register | Memory | Label | Instruction | End | Blank | Event sig | Payload sig |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `first` | 18 | 17 | 1 | 1 | 0 | 6 | 0 | 1 | 7 | 1 | 1 | 81 | 80 |
| `simple_call` | 21 | 20 | 1 | 2 | 2 | 4 | 0 | 2 | 6 | 2 | 2 | 94 | 93 |
| `sign` | 36 | 35 | 1 | 2 | 1 | 9 | 0 | 5 | 14 | 2 | 2 | 170 | 165 |
| Total | 75 | 72 | 3 | 5 | 3 | 19 | 0 | 8 | 27 | 5 | 5 | 345 | 338 |

## Coverage

The executable model validates expected event and payload class by fixture and
line index, blueprint-to-event mapping, encoding-to-payload mapping, event
payload permissions, source metadata flags, aggregate event counts, transition
counts, and deterministic fixture and total signatures.

The model also validates negative probes for unknown fixtures, out-of-range
indexes, unknown events, invalid payloads, and invalid event transitions. The
full fixture validators remain available as targeted entrypoints, while `main`
uses a bounded representative self-check that stays within the hosted execution
limit.

## Non Goals

S3 0.26 does not render text, does not add runtime strings, does not add arrays
to the model, does not update inspect goldens or candidate actual outputs, does
not alter `AssemblyProgram.render()` or `render_supported_program()`, and does
not mark the real S3 renderer implemented.

There is no 0.26-B scope. This roadmap is closed by the 0.26 delivery, and it
does not open or define 0.27.

A later phase should choose between evolving the event stream into a hosted
writer/collector, starting hosted textual representation, adding minimal
runtime text/string capability, or consolidating the repeated S3 models behind
shared structure when the language can express that safely. `compare --check`
remains blocked until a real textual S3 renderer exists.
