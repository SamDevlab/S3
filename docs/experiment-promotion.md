# Experimental Component Promotion

S3 experimental components use a shared fail-closed promotion contract from
`bootstrap.s3.experiment_promotion`. The contract is a policy boundary, not a
default-path switch.

## Required Gates

- `default_enabled` must be false.
- Selection requires explicit `explicit_opt_in=True`.
- The observed source SHA must match the pinned `source_lock_sha`.
- Eligibility, correctness evidence, and structural evidence must all pass.
- A reference fallback must remain available.

Without explicit opt-in the decision is `OFF_BY_DEFAULT`. A source-lock
mismatch or failed gate produces `FALLBACK`; it never silently selects the
candidate. Only an explicitly opted-in candidate with every gate satisfied is
reported as `CANDIDATE_SELECTED`.

This contract does not promote any current component to the production
default, does not reopen the ABL V2.x decision, and does not provide a
performance claim.
