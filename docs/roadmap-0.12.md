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

Objective:

Investigate the Assembly golden for `first` and add the smallest technical layer
needed to produce, in memory, an equivalent or partial textual document using
`StaticTextLineEmitter`.

Acceptance:

- no versioned actual output is required yet;
- a test demonstrates that the emitter can assemble the textual shape needed
  for `first`;
- comparison and actual-output contracts remain blocked.

### 0.12-B: first actual output draft

Objective:

Create the first controlled actual output for `first`, if 0.12-A confirms the
technical path.

Future acceptance:

- create the planned actual output file for `first`;
- update the actual-output contract only for `first`;
- keep `simple_call` and `sign` blocked;
- validate bytes, hash, and line count.

### 0.12-C: first byte-for-byte comparison

Objective:

Compare the `first` actual output against the expected Assembly golden.

Future acceptance:

- byte-for-byte comparison for `first` passes;
- `first` can advance to a partial or available status;
- the complete renderer may still be incomplete;
- `--check` changes only if the design requires it and tests cover the new
  behavior.

This sequence may change based on technical investigation.
