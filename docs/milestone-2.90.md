# Milestone 2.90: IR and Lowering Self-Hosting Checkpoint

M2.90 consolidates the bounded IR verifier and lowering canaries into one
readable checkpoint. It records whether both experimental candidates were
selected under the same exact source lock and explicit opt-in.

## Contract

- verifier and lowering canaries retain independent decisions;
- default execution keeps both reference implementations;
- candidate selection requires explicit opt-in at both boundaries;
- source-lock drift falls back at both boundaries;
- the checkpoint reports only the qualified bounded subset.

## Non-claims

M2.90 does not claim complete compiler self-hosting, replace production
semantic/lowering/verification paths, enable candidates by default, claim
native execution, claim performance improvement or run global T4. Emission,
driver and bootstrap work remains in M2.91-M3.00.
