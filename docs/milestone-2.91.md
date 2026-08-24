# Milestone 2.91: Assembly Emission Candidate

M2.91 adds a bounded Assembly emission candidate for verified linear canonical
IR. The Python renderer is the exact text reference; the S3 candidate
reproduces the deterministic emission-plan identity for the same subset.

## Supported Subset

- one function and one block;
- `CONST`, `ADD` and final `RETURN`;
- scalar `trit`, `tryte`, `i64` and `f64` register types;
- maximum four instructions.

The reference text is reparsed before the result is accepted. Verification is
performed before emission and invalid IR fails closed.

## Non-claims

M2.91 does not replace the production Assembly renderer, emit arbitrary IR,
provide a standalone driver, claim complete self-hosting, claim native
performance or run global T4. Assembly verification and driver boundaries are
later work.
