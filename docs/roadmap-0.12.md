# S3 0.12 Roadmap

Status: open

## Objective

Use the deterministic text foundation built in S3 0.11 to start the path toward
real actual output, beginning with the `first` fixture.

S3 0.12 should be practical implementation work, not another scaffolding
milestone. Each delivery should move the project closer to a real byte-stable
actual output that can eventually be compared against the existing Assembly
goldens.

## Principles

- Each PR should move toward real actual output.
- Avoid new isolated contracts.
- Use `StaticTextLineEmitter` to build deterministic textual output.
- Preserve LF and stable SHA-256 behavior on Windows and Linux.
- Keep renderer candidate readiness passing.
- Keep `python tools/compare_assembly_renderer.py --check` blocked until enough
  real comparison exists.
- Do not expand to `simple_call` or `sign` before `first` is stable.
- Do not broaden self-hosting before the first real output exists.

## Proposed 0.12 sequence

### 0.12-A: first fixture output investigation

Status: complete

Objective:

Investigate the Assembly golden for `first` and add the smallest technical layer
needed to produce, in memory, an equivalent or partial textual document using
`StaticTextLineEmitter`.

0.12-A adds an in-memory probe for the `first` fixture. The probe builds the
expected Assembly text with `StaticTextLineEmitter`, finalizes it as a
`StaticTextDocument`, and validates the LF-normalized bytes, line count, byte
count, and SHA-256 against the existing inspect golden.

It does not create a versioned actual output, alter actual-output contracts, or
implement the real S3 renderer.

Acceptance:

- no versioned actual output is created;
- a test demonstrates that the emitter can assemble the textual shape needed
  for `first`;
- comparison and actual-output contracts remain blocked.

### 0.12-B: first actual output draft

Status: complete

Objective:

Create the first controlled actual output for `first`, if 0.12-A confirms the
technical path.

0.12-B creates the first versioned candidate actual output:
`tests/golden/assembly_renderer_candidate_actual/first.assembly.txt`. The file
is generated from `build_first_fixture_assembly_text()`, keeps LF-stable bytes,
and records the same byte count, line count, and SHA-256 as the `first` inspect
golden.

The actual outputs contract now marks `first` as available with pending formal
comparison. `simple_call` and `sign` remain `not_implemented`, and
`python tools/compare_assembly_renderer.py --check` remains blocked because the
real S3 renderer is still not implemented.

Future acceptance:

- create the planned actual output file for `first`;
- update the actual-output contract only for `first`;
- keep `simple_call` and `sign` blocked;
- validate bytes, hash, and line count.

### 0.12-C: first byte-for-byte comparison

Status: complete

Objective:

Compare the `first` actual output against the expected Assembly golden.

0.12-C formalizes the byte-for-byte comparison for `first`. The expected
inspect golden and the versioned candidate actual output match after LF
normalization, so `first` moves from pending to passed comparison status.

The new partial comparison mode is:

`python tools/compare_assembly_renderer.py --candidate-compare-available`

It compares only available actual outputs. `simple_call` and `sign` remain
blocked and `not_implemented`, and `python tools/compare_assembly_renderer.py
--check` remains blocked because the complete S3 renderer is still unavailable.

Future acceptance:

- byte-for-byte comparison for `first` passes;
- `first` can advance to a partial or available status;
- the complete renderer may still be incomplete;
- `--check` changes only if the design requires it and tests cover the new
  behavior.

This sequence may change based on technical investigation.
