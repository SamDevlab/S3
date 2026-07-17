# S3 0.15 Roadmap

Status: open

## Objective

Evaluate and define the correct renderer candidate check state now that
`first`, `simple_call`, and `sign` are available and passed.

S3 0.15 should be practical and decision-oriented. It should answer whether
`python tools/compare_assembly_renderer.py --check` must remain blocked because
the real S3 renderer is still absent, or whether it should evolve to a
controlled partial or success state for completed actual outputs.

## Principles

- Do not change `--check` without explicit investigation.
- Preserve `first`, `simple_call`, and `sign` as available and passed.
- Preserve deterministic LF for candidate actual outputs.
- Keep a clear distinction between passed actual outputs, the missing real S3
  renderer, and the blocked global renderer candidate check.
- Avoid isolated new contracts unless they are needed.
- Do not implement the complete renderer in one step.
- Do not migrate the full Python compiler to S3 in this milestone.
- Any `--check` behavior change should happen in its own PR with tests and
  documentation.

## Proposed 0.15 sequence

### 0.15-A: renderer candidate check state investigation

Status: planned

Objective:

Investigate whether `--check` should continue to be blocked even with
`first`, `simple_call`, and `sign` passed, or whether it should move to a
controlled partial or success state.

Acceptance:

- no behavior changes unless the investigation identifies a minimal safe
  change;
- current conditions are documented;
- remaining blockers for a real renderer are identified;
- an explicit technical decision is prepared for 0.15-B.

### 0.15-B: renderer candidate check state implementation

Status: planned

Objective:

Implement the 0.15-A decision.

Possible outcomes:

- keep `--check` blocked, with a more precise message;
- add a separate mode for actual-output completion;
- allow a partial success without declaring the real renderer implemented.

Acceptance:

- tests cover the decision;
- the readiness gate is coherent;
- docs keep "actual outputs passed" separate from "real renderer implemented".

### 0.15-C: close check-state milestone

Status: planned

Objective:

Close the check-state decision and prepare the next milestone.

Acceptance:

- documentation is clear;
- checkers and harness behavior are stable;
- the next focus is identified: generalize the renderer, begin the real S3
  renderer, or add another fixture.

The 0.15 sequence may be adjusted based on the 0.15-A investigation.
