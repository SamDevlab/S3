# S3 0.14 Roadmap

Status: closed

## Objective

Advance to the `sign` fixture, completing the third required fixture on the
candidate actual-output path.

S3 0.14 remained practical rather than scaffolding-only. It answered
how the project completes the third required fixture and prepares the separate
decision about the future state of `python tools/compare_assembly_renderer.py
--check`.

S3 0.14 is complete after three deliveries:

- 0.14-A: sign in-memory output probe;
- 0.14-B: sign versioned actual output;
- 0.14-C: sign byte-for-byte comparison.

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

Status: complete

Objective:

Create the versioned candidate actual output for `sign`, if 0.14-A confirms the
path.

Acceptance:

- `sign` advances to available;
- `sign` has `comparison_status: pending`;
- `first` and `simple_call` remain passed;
- `--check` remains blocked.

Notes:

0.14-B creates
`tests/golden/assembly_renderer_candidate_actual/sign.assembly.txt` from
`build_sign_fixture_assembly_text()`. The actual-output contract now marks
`sign` as available with `comparison_status: pending`; `first` and
`simple_call` remain available and passed. The S3 renderer is still not
implemented, and `--check` remains blocked. 0.14-C should formalize the
byte-for-byte `sign` comparison before any separate reassessment of the global
check state.

### 0.14-C: sign byte-for-byte comparison

Status: complete

Objective:

Formalize byte-for-byte comparison for `sign`.

Acceptance:

- `sign` advances to `comparison_status: passed`;
- `first` and `simple_call` remain passed;
- `--candidate-compare-available` covers `first`, `simple_call`, and `sign`;
- after that, evaluate separately whether `--check` should remain blocked or
  can change state.

Notes:

0.14-C formalizes the byte-for-byte comparison for `sign`: the expected inspect
golden and the versioned candidate actual output match with deterministic LF
bytes, so `sign` advances from `comparison_status: pending` to
`comparison_status: passed`. `first` and `simple_call` remain passed, and
`--candidate-compare-available` now covers `first`, `simple_call`, and `sign`
as passed. The S3 renderer is still not implemented, so `--check` remains
blocked; the next delivery should evaluate that global state separately and/or
close 0.14.

## Delivered scope

S3 0.14 delivered:

- an in-memory probe for `sign`;
- the versioned candidate actual output for `sign`;
- formal byte-for-byte comparison for `sign`;
- `sign` advanced to `comparison_status: passed`;
- `first` remained `comparison_status: passed`;
- `simple_call` remained `comparison_status: passed`;
- `--candidate-compare-available` now covers `first`, `simple_call`, and
  `sign` as passed;
- candidate actual outputs are preserved with LF through `.gitattributes`.

S3 0.14 did not:

- implement a real S3 renderer;
- make `python tools/compare_assembly_renderer.py --check` pass;
- alter inspect goldens;
- alter parser, lexer, semantic analysis, lowering, IR, backend, or emulator;
- migrate the whole Python compiler to S3.

0.14 is complete after 0.14-C. There is no 0.14-D planned. The next milestone
evaluates the renderer candidate check state.
