# Milestone 2.79: Semantic Candidate Canary

M2.79 adds explicit opt-in routing for the M2.78 composed semantic candidate.
The Python semantic path remains the default and shared fallback.

## Selection Rules

The canary is `OFF_BY_DEFAULT`. Selection requires:

- explicit opt-in;
- exact source-lock match;
- canonical differential input and output;
- no reference or candidate execution error;
- a retained reference fallback.

The canary reports `CANDIDATE_SELECTED` only after the complete differential
has passed. Any source-lock mismatch, candidate error, reference error or
canonical output mismatch produces `FALLBACK` with a visible reason and
returns the reference output when it was safely observed. No fallback is
silent.

## Evidence Contract

- Routing: `bootstrap/s3/semantic_canary.py`.
- Candidate: `bootstrap/s3/semantic_closure_candidate.py`.
- Focused contract: `tests/test_m279_semantic_canary.py`.
- Shared promotion policy: `bootstrap/s3/experiment_promotion.py`.
- Shared canonical differential harness:
  `bootstrap/s3/differential.py`.

## Non-claims

M2.79 does not enable the candidate by default, replace the compiler's
production semantic path, claim native self-hosting, claim complete semantic
coverage or claim full compiler self-hosting. M2.80 remains the bounded
semantic self-hosting checkpoint.
