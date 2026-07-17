# S3 0.14 Roadmap

Status: open

## Objective

Advance to the `sign` fixture, completing the third required fixture on the
candidate actual-output path.

S3 0.14 should remain practical rather than scaffolding-only. It should answer
how the project completes the third required fixture and prepares the separate
decision about the future state of `python tools/compare_assembly_renderer.py
--check`.

## Principles

- Each PR should move `sign` closer to real actual output.
- Preserve `first` as available and passed.
- Preserve `simple_call` as available and passed.
- Keep `python tools/compare_assembly_renderer.py --check` blocked while
  `sign` is not passed.
- Do not migrate the full compiler to S3.
- Do not implement the complete renderer in one step.
- Use the pattern already validated by `first` and `simple_call`.
- Preserve deterministic LF, byte count, line count, and SHA-256 metadata.
- Avoid isolated new contracts without real output work.

## Proposed 0.14 sequence

### 0.14-A: sign output investigation and in-memory probe

Status: complete

Objective:

Investigate `examples/sign.s3` and `tests/golden/inspect/sign.assembly.txt`,
then create an in-memory probe for the expected `sign` output using
`StaticTextLineEmitter`.

Acceptance:

- no versioned actual output is created yet;
- the in-memory probe compares against the LF-normalized golden;
- `sign` remains `not_implemented` and blocked in the contracts;
- `--check` remains blocked.

Notes:

0.14-A adds an in-memory `sign` fixture probe using `StaticTextLineEmitter`.
The probe builds the expected Assembly text explicitly and validates
byte-for-byte output, byte count, line count, and SHA-256 against the
LF-normalized inspect golden. It does not create a versioned actual output,
change the actual-output contracts, or implement the S3 renderer. `first` and
`simple_call` remain available and passed, while `sign` remains blocked and
`not_implemented`. This prepares 0.14-B to create the versioned `sign` actual
output if the path remains stable.

### 0.14-B: sign actual output

Status: planned

Objective:

Create the versioned candidate actual output for `sign`, if 0.14-A confirms the
path.

Acceptance:

- `sign` advances to available;
- `sign` has `comparison_status: pending`;
- `first` and `simple_call` remain passed;
- `--check` remains blocked.

### 0.14-C: sign byte-for-byte comparison

Status: planned

Objective:

Formalize byte-for-byte comparison for `sign`.

Acceptance:

- `sign` advances to `comparison_status: passed`;
- `first` and `simple_call` remain passed;
- `--candidate-compare-available` covers `first`, `simple_call`, and `sign`;
- after that, evaluate separately whether `--check` should remain blocked or
  can change state.

S3 0.14 can close after A/B/C if `sign` is stable.
