# Milestone 2.59: Candidate Promotion Integration

M2.59 connects self-hosted candidate evidence to the shared fail-closed
promotion framework. It does not promote any candidate by default and does not
change the Compact EA or production execution paths.

## Contract

`CandidateMetadata` binds a candidate component and source lock to a canonical
provenance mapping and one `DifferentialResult`. The integration verifies the
canonical input bytes and digest, the canonical provenance bytes, and matching
component/source identifiers before constructing the existing
`PromotionContract`.

A matching differential result supplies `correctness_evidence=PASS`; a mismatch
is represented as a failed correctness gate and therefore selects the existing
fallback. Structural evidence, eligibility, fallback availability, and the
off-by-default rule remain governed by `PromotionContract`.

Promotion still requires both an exact observed source lock and explicit
opt-in. Invalid or tampered metadata fails closed before a promotion decision
is returned.

## Scope

This milestone adds hosted metadata validation and integration tests only. It
does not add native claims, benchmarks, a default activation, or a new runtime
backend.
