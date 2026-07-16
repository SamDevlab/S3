# S3 0.11 Roadmap

Status: open

## Objective

Start incremental implementation work that makes deterministic textual output
possible in S3, beginning with the smallest path needed for a future S3
Assembly renderer.

0.11 should move beyond renderer-candidate-only scaffolding. Each delivery
should bring the project closer to producing real actual output that can be
compared byte-for-byte against existing Assembly goldens.

## Direction

Recommended direction for 0.11:

1. Unlock the minimum text or string capability needed by the renderer.
2. Produce the first controlled actual output for one fixture.
3. Compare that output byte-for-byte against the Assembly golden.
4. Expand to additional fixtures only after the first path is stable.

The first real implementation work will probably start in one of these areas:

- minimal deterministic text output or buffer capability;
- minimal static string literal runtime or lowering support;
- a simple internal format for assembling Assembly text lines;
- the first actual output for a single fixture;
- byte-for-byte comparison using the existing contracts.

## Principles

- Avoid new isolated contracts without implementation attached.
- Every PR should move toward real actual output.
- Preserve byte-for-byte determinism.
- Preserve Windows and Linux behavior.
- Keep `python tools/compare_assembly_renderer.py --check` blocked until enough
  real output exists for a correct comparison result.
- Keep the renderer candidate readiness gate passing.
- Do not broaden self-hosting before one renderer fixture works.

## Proposed 0.11 sequence

### 0.11-A: implementation decision and smallest text-output path

Status: started

Objective:

Choose and implement the smallest technical path that lets S3 represent or
produce deterministic text needed by the renderer.

This should not be documentation-only. It should produce a small, testable
technical change aligned with renderer output.

The first implementation slice adds deterministic static text helpers for
front-end string literals. It provides LF-normalized UTF-8 bytes and metadata
for static text, while string literals remain blocked in semantic/runtime use.
It does not implement the S3 Assembly renderer and does not create fixture
actual outputs.

Candidate paths:

- reduce the `StringLiteral` blocker for one narrow case;
- add a minimal static string runtime structure;
- add a deterministic text emission helper at the level S3 currently supports;
- implement the first safe mechanism that can prepare actual output.

Acceptance:

- at least one new test demonstrates real technical capability;
- no fixture actual output is required yet if text support is still too small.

### 0.11-B: static text builder

Objective:

Add deterministic composition for static text so future renderer work can build
byte-stable documents before creating fixture actual outputs.

This stage introduces a static text document/builder layer on top of the 0.11-A
encoding helpers. It keeps LF normalization, UTF-8 bytes, and metadata stable,
but it still does not implement the S3 Assembly renderer or create fixture
actual outputs.

Acceptance:

- builder starts empty;
- builder appends decoded text, static literals, and LF-terminated lines;
- finalized documents expose text, UTF-8 bytes, byte count, line count, and
  SHA-256;
- renderer candidate contracts remain unchanged;
- `--check` remains blocked.

### 0.11-C: structured static text line emitter

Objective:

Add a deterministic line-oriented emitter on top of the static text builder so
future renderer work can assemble structured text with LF-terminated lines,
blank lines, literal text, and controlled indentation.

This stage still does not render `AssemblyProgram`, does not implement the S3
Assembly renderer, and does not create fixture actual outputs.

Acceptance:

- emitter starts empty;
- emitter emits text lines and blank lines with LF;
- emitter can emit raw static literal lines through the existing decoder;
- finalized documents expose the same deterministic text, UTF-8 bytes, and
  metadata as the builder;
- renderer candidate contracts remain unchanged;
- `--check` remains blocked.

### 0.11-D: first actual output path for one fixture

Objective:

When text support provides enough capability, produce or prepare the first
actual output for a simple fixture.

Preferred initial fixture:

- `first`

Future acceptance:

- actual output exists for `first`;
- the comparison plan changes from blocked to partial for `first` only, if that
  is technically correct;
- byte-for-byte comparison is validated;
- remaining fixtures stay blocked.

### 0.11-E: expand fixture coverage

Objective:

Expand from `first` to `simple_call` and `sign` only after the first path is
stable.

This sequence may change based on what implementation investigation discovers.
