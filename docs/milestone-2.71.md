# Milestone 2.71: Self-Hosted Symbol Table Candidate

M2.71 begins the semantic self-hosting train with a bounded S3-authored symbol
table kernel.

## Scope

The candidate accepts up to eight canonical numeric symbol IDs paired with one
of four bounded symbol kinds. It rejects duplicate IDs and invalid kinds,
preserves insertion order as the canonical slot order, and performs exact
lookup by returning a compact scalar encoding of `(slot, kind)`. A missing
symbol returns zero.

The Python reference uses the deterministic `DynamicMap` collection contract
introduced earlier in the roadmap. The S3 candidate operates directly on fixed
`tryte[8]` arrays so the lookup behavior can be compared exactly without a
lossy text-name hash.

This milestone does not yet resolve source identifiers across scopes, modules,
or workspaces. Those name-resolution semantics remain for M2.72 and later
milestones.

## Evidence Contract

- S3 source: `selfhost/semantic/symbol_table_candidate.s3`.
- Python adapter: `bootstrap/s3/symbol_table_candidate.py`.
- Focused contract: `tests/test_m271_symbol_table_candidate.py`.
- Capacity: eight symbols.
- Symbol kinds: canonical IDs 1 through 4.
- Duplicate symbols and invalid kinds fail closed.
- Lookup comparison is exact scalar equality, not a modulo fingerprint.
- Python remains the reference/default compiler path.
- No native, benchmark, performance, promotion, or global T4 claim is made.
