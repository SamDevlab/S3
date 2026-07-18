# S3 0.25 Roadmap

Initial status: open for this PR.

Status: closed in this PR.

S3 0.25 adds a practical line content encoding model for the future S3
Assembly renderer. It is an executable S3 artifact, not the real renderer.

## Objective

Model each current rendered Assembly line as scalar content metadata for the
existing `first`, `simple_call`, and `sign` fixtures.

The model builds on the S3 0.23 blueprint IDs and S3 0.24 sequence coverage. It
adds directive IDs, opcode IDs, line categories, register operand arity,
immediate/callee/label/memory/source flags, function/block ordinal probes,
fixture totals, and compact deterministic line encoding signatures without
runtime strings or arrays.

## Delivered

- Added `examples/self_hosting/assembly_renderer_line_encodings.s3`.
- Registered it in `tools/s3_program_check.py` with hosted expected return `0`.
- Extended `tools/compare_assembly_renderer.py --candidate-run` to execute it.
- Extended the candidate readiness gate to require `s3 line content encoding
  model: passed`.
- Added `tests/test_s3_renderer_line_encodings.py`.
- Updated comparison, self-hosting, program-check, and README documentation.

## Current Encodings

| Fixture | Lines | Instructions | Directives | Blanks | Signature |
| --- | ---: | ---: | ---: | ---: | ---: |
| `first` | 18 | 7 | 10 | 1 | 61 |
| `simple_call` | 21 | 6 | 13 | 2 | 73 |
| `sign` | 36 | 14 | 20 | 2 | 156 |
| Total | 75 | 27 | 43 | 5 | 290 |

Directive IDs:

- `0`: no directive;
- `1`: `.s3asm`;
- `2`: `.function`;
- `3`: `.param`;
- `4`: `.register`;
- `5`: `.memory`;
- `6`: `.label`;
- `7`: `.end`;
- `8`: blank line.

Opcode IDs:

- `0`: no opcode;
- `1`: `TCONST`;
- `2`: `TMOV`;
- `3`: `TINV`;
- `4`: `TADD`;
- `5`: `TMIN`;
- `6`: `TMAX`;
- `7`: `TCMP`;
- `8`: `TCALL`;
- `9`: `TLOAD`;
- `10`: `TSTORE`;
- `11`: `TRET`;
- `12`: `TJMP`;
- `13`: `TBR3`.

## Coverage

The executable model validates representative directive, blank, instruction,
call, branch, source-metadata, unknown-fixture, and unknown-line probes. The
full fixture validators remain available as targeted entrypoints, while `main`
uses a bounded representative self-check that stays within the hosted execution
limit.

The model also validates aggregate encoded line counts, instruction/directive
counts, opcode counts, register-bearing line counts, immediate/callee/label/
memory/source flags, and deterministic fixture signatures.

## Non Goals

S3 0.25 does not render text, does not add runtime strings, does not add arrays
to the model, does not update inspect goldens or candidate actual outputs, and
does not mark the real S3 renderer implemented.

There is no 0.25-B scope. This roadmap is closed by the 0.25 delivery, and it
does not open or define the next roadmap.
