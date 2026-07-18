# S3 0.23 Roadmap

Status: closed in this PR.

S3 0.23 adds a practical line blueprint model for the future S3 Assembly
renderer. It is an executable S3 artifact, not the real renderer.

## Objective

Model the current Assembly output as one primary numeric blueprint per rendered
line for the existing `first`, `simple_call`, and `sign` fixtures.

Source metadata is not a separate blueprint. Instruction lines that include
`source=` use the `instruction_with_source` blueprint variant.

## Delivered

- Added `examples/self_hosting/assembly_renderer_line_blueprints.s3`.
- Registered it in `tools/s3_program_check.py` with hosted expected return `0`.
- Extended `tools/compare_assembly_renderer.py --candidate-run` to execute it.
- Extended the candidate readiness gate to require `s3 line blueprint model:
  passed`.
- Added `tests/test_s3_renderer_line_blueprints.py`.
- Updated comparison, self-hosting, program-check, and README documentation.

## Blueprint Kinds

The model uses stable scalar IDs for:

- `.s3asm` header lines;
- `.function` header lines;
- `.param` lines;
- `.register` lines;
- `.memory` lines;
- `.label` lines;
- instruction lines without source metadata;
- instruction lines with source metadata;
- `.end` lines;
- blank lines.

## Current Metrics

| Fixture | Lines | Blueprints | Directives | Instructions | With source | Without source | Blank |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `first` | 18 | 18 | 10 | 7 | 7 | 0 | 1 |
| `simple_call` | 21 | 21 | 13 | 6 | 6 | 0 | 2 |
| `sign` | 36 | 36 | 20 | 14 | 14 | 0 | 2 |
| Total | 75 | 75 | 43 | 27 | 27 | 0 | 5 |

## Non Goals

S3 0.23 does not render text, does not add runtime strings, does not add arrays
to the model, does not update inspect goldens or candidate actual outputs, and
does not mark the real S3 renderer implemented.

A later phase should choose whether to evolve these blueprints into a
layout/order representation or expand string/text runtime support enough for
real S3 text rendering. `compare --check` remains blocked until a real textual
S3 renderer exists.

There is no 0.23-B scope. This roadmap is closed by the 0.23 delivery, and it
does not open or define the next roadmap.
