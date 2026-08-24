# Milestone 3.00: Final Bounded Self-Hosting Checkpoint

M3.00 closes the M2.71–M2.99 train with an explicit Level-C bootstrap profile
covering the IR, lowering, Assembly, workspace, driver, handoff, admission,
reproducibility and readiness contracts in order.

## Contract

- `level-c-bootstrap` selects exactly the nineteen M2.81–M2.99 milestone
  contracts;
- every selection is `LEVEL-C`, never T4;
- native execution is not required by this profile;
- production promotion remains disabled;
- the full self-hosting claim remains disabled until an actual end-to-end
  bootstrap execution is available.

This is the final bounded checkpoint for the current train. It does not remove
Docker support, change the container backend policy, or claim that the S3
candidate has replaced the Python reference path.

## Validation Policy

The Level-C bootstrap profile is the milestone gate. Global T4 and benchmarks
are intentionally not part of this architectural preparation.
