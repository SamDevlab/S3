# Milestone 2.86: IR Verifier Canary

M2.86 adds an explicit canary boundary around the S3-authored canonical IR
verifier from M2.84. The existing Python verifier remains the default path.

## Selection Rules

The canary requires explicit opt-in, an exact source-lock match, and a
canonical differential result matching the reference verifier. A candidate
error, source-lock mismatch, input mismatch, or output drift returns a visible
fallback decision and preserves the reference result.

## Contract

- verifier candidate: `selfhost/verifier/canonical_ir_verifier_candidate.s3`;
- routing adapter: `bootstrap/s3/ir_verifier_canary.py`;
- default execution: Python reference verifier;
- candidate execution: explicit opt-in only;
- fallback: visible and fail-closed;
- native emission and production promotion: out of scope.

## Non-claims

M2.86 does not enable the candidate by default, replace production IR
verification, add CFG or multi-function verifier coverage, claim native
self-hosting, or run global T4. Those boundaries remain owned by later
milestones.
