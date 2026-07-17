# S3 0.15 Roadmap

Status: closed

## Objective

Evaluate and define the correct renderer candidate check state now that
`first`, `simple_call`, and `sign` are available and passed.

S3 0.15 was completed in one delivery: renderer candidate check state safe
decision.

The decision is to keep
`python tools/compare_assembly_renderer.py --check` blocked with exit code 1.
`first`, `simple_call`, and `sign` have available actual outputs and passed
byte-for-byte comparisons, but those versioned outputs do not prove that a real
S3 renderer exists. The real S3 renderer is still a stub/not implemented, so
returning success from the global check would create a false positive.

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

## Closed decision

`python tools/compare_assembly_renderer.py --candidate-compare-available` is
the correct passing mode for validating currently available actual outputs.
It reports `first`, `simple_call`, and `sign` as passed.

`python tools/compare_assembly_renderer.py --check` remains the global renderer
candidate check and stays blocked until a real S3 renderer implementation can
produce outputs and be compared against the Python reference.

The check output distinguishes:

- actual output completion: passed;
- available comparisons: passed;
- renderer implementation: not_implemented;
- global check: blocked.

There are no planned 0.15-B or 0.15-C follow-ups because the safe decision,
tests, readiness expectation, and documentation were completed in the same PR.

## Next focus

The next milestone should begin the real renderer/generalization work without
changing `--check` to success prematurely.
