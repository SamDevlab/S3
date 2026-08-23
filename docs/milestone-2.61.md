# Milestone 2.61: Self-Hosted Lexer Candidate

M2.61 introduces a bounded S3-authored lexer candidate and compares its token
fingerprint with the existing Python lexer on identical source input.

## Scope

The candidate is intentionally a bounded subset for the first frontend
self-hosting step. It accepts ASCII source up to 96 code units and recognizes
whitespace, line comments, identifiers, the M2.61 keyword subset, integers,
decimal numbers, delimiters, separators, single-character operators, and the
two-character operators used by the focused contracts. Unsupported input is
rejected rather than silently promoted.

The candidate runs through the existing S3 compiler and hosted emulator. The
Python lexer remains the reference implementation, and the differential
harness compares the exact source, mode, provenance, and deterministic token
fingerprint. No candidate activation, fallback change, native claim, or
performance claim is made.

## Evidence Contract

- S3 source: `selfhost/frontend/lexer_candidate.s3`.
- Python adapter: `bootstrap/s3/lexer_candidate.py`.
- Focused contract: `tests/test_m261_lexer_candidate.py`.
- Impact shard: `m261`.
- Global T4 is not run for this milestone; it remains reserved for M3.00.
