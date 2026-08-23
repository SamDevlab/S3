# Milestone 2.63: Canonical AST Candidate

M2.63 adds a bounded S3-authored canonical-AST candidate for the frontend
self-hosting train. It validates the same small V0.6 grammar used by M2.62 and
emits a canonical fingerprint that excludes layout-only details.

## Scope

The candidate accepts one no-parameter function with a primitive return type
and one primitive literal return statement, within a 64-token bound. Its
canonical fields are the function node, function name, primitive return type,
and literal kind/value. Indentation and newline placement do not contribute to
the canonical result. The Python AST parser remains the reference and the
differential harness compares canonical fingerprints for identical input.

## Evidence Contract

- S3 source: `selfhost/frontend/ast_candidate.s3`.
- Python adapter: `bootstrap/s3/ast_candidate.py`.
- Focused contract: `tests/test_m263_canonical_ast_candidate.py`.
- Impact shard: `m263`.
- Unsupported AST shapes are rejected closed.
- No candidate activation, native claim, benchmark, or performance claim is
  made.
- Global T4 remains reserved for M3.00.
