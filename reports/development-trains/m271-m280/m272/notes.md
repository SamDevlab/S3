# M2.72 Bounded Name Resolution Candidate

## WHY_NOW

M2.70 closed the bounded frontend self-hosting checkpoint and M2.71 introduced
an exact S3-authored symbol-table primitive. The next semantic dependency is
scope-aware name resolution without reverting to lossy name fingerprints.

## ARCHITECTURAL_DECISION

M2.72 keeps canonical numeric symbol IDs and introduces a bounded lexical scope
tree. The root has parent `-1`; every non-root scope must reference an earlier
scope, so cycles are rejected by construction. Resolution walks from the query
scope to the root and returns the first matching declaration.

Nested declarations may shadow the same symbol ID in an outer scope. Duplicate
symbol IDs in the same scope are rejected. Exact slot/kind encodings are used as
the observable differential result.

## IMPLEMENTATION_SUMMARY

- Added `selfhost/semantic/name_resolution_candidate.s3`.
- Added `bootstrap/s3/name_resolution_candidate.py`.
- Added focused differential tests for root lookup, inheritance, shadowing,
  sibling invisibility, missing names, duplicate rejection and structural
  bounds.
- Preserved Python as reference/default.
- Avoided modulo fingerprints.

## TEST_EVIDENCE

Remote implementation only at this checkpoint.

- local T0/T1/T2/T3: NOT RUN
- GitHub CI: NOT YET OBSERVED
- impact metadata: PENDING
- benchmark: NOT RUN
- global T4: NOT RUN

No missing evidence is classified as PASS.

## KNOWN_LIMITATIONS

- Eight scopes and eight declarations.
- Canonical numeric symbol IDs are supplied to the candidate.
- No source-text interning.
- No module import/export resolution yet.
- No overloads or type identities.
- No production activation.

## STATUS

IMPLEMENTED_PENDING_QUALIFICATION
