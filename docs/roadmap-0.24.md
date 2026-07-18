# S3 0.24 Roadmap

Status: closed in this PR.

S3 0.24 adds a practical line sequence model for the future S3 Assembly
renderer. It is an executable S3 artifact, not the real renderer.

## Objective

Model the current Assembly output as ordered sequences of numeric line
blueprint IDs for the existing `first`, `simple_call`, and `sign` fixtures.

The model builds on the S3 0.23 blueprint IDs and validates ordering, function
boundaries, transition rules, invalid probes, aggregate totals, and a compact
deterministic sequence signature without runtime strings or arrays.

## Delivered

- Added `examples/self_hosting/assembly_renderer_line_sequences.s3`.
- Registered it in `tools/s3_program_check.py` with hosted expected return `0`.
- Extended `tools/compare_assembly_renderer.py --candidate-run` to execute it.
- Extended the candidate readiness gate to require `s3 line sequence model:
  passed`.
- Added `tests/test_s3_renderer_line_sequences.py`.
- Updated comparison, self-hosting, program-check, and README documentation.

## Current Sequences

| Fixture | Lines | Transitions | Function boundaries | Instruction runs | Signature |
| --- | ---: | ---: | ---: | ---: | ---: |
| `first` | 18 | 17 | 2 | 1 | 72 |
| `simple_call` | 21 | 20 | 4 | 2 | 83 |
| `sign` | 36 | 35 | 4 | 5 | 152 |
| Total | 75 | 72 | 10 | 8 | 307 |

Blueprint IDs follow S3 0.23:

- `0`: `.s3asm` header;
- `1`: `.function` header;
- `2`: `.param`;
- `3`: `.register`;
- `4`: `.memory`;
- `5`: `.label`;
- `6`: instruction without source metadata;
- `7`: instruction with source metadata;
- `8`: `.end`;
- `9`: blank line.

## Transition Coverage

The executable model validates fixture transitions such as `.s3asm` to blank,
blank to `.function`, function headers to params/registers, params to
params/registers, registers to registers/labels, labels to instructions,
instructions to instructions/labels/ends, and `.end` to blank between
functions.

The model also validates negative transition probes, including blank to blank,
`.s3asm` to `.s3asm`, `.end` to instruction, label to register, function header
to `.end`, param to label, and unknown blueprint IDs.

## Non Goals

S3 0.24 does not render text, does not add runtime strings, does not add arrays
to the model, does not update inspect goldens or candidate actual outputs, and
does not mark the real S3 renderer implemented.

There is no 0.24-B scope. This roadmap is closed by the 0.24 delivery, and it
does not open or define the next roadmap.
