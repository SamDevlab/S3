# Milestone 2.62: Self-Hosted Parser Candidate

M2.62 adds a bounded S3-authored parser candidate for the first frontend
self-hosting grammar slice. The candidate consumes the V0.6 token stream and
is compared with the Python parser on identical source and token-width data.

## Scope

The candidate accepts at most 64 tokens and recognizes one function with an
identifier, no parameters, a primitive return type, and one literal return
statement in indentation-based V0.6 syntax. It validates the complete token
sequence, including `NEWLINE`, `INDENT`, `DEDENT`, and `EOF`, before producing a
deterministic token fingerprint. Valid syntax outside this bounded grammar is
rejected closed and is not promoted as a parser implementation.

## Evidence Contract

- S3 source: `selfhost/frontend/parser_candidate.s3`.
- Python adapter: `bootstrap/s3/parser_candidate.py`.
- Focused contract: `tests/test_m262_parser_candidate.py`.
- Impact shard: `m262`.
- The Python parser remains the reference implementation.
- No activation, fallback change, native claim, benchmark, or performance claim
  is made.
- Global T4 remains reserved for M3.00.
