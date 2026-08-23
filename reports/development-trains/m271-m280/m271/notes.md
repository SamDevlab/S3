# M2.71 Self-Hosted Symbol Table Candidate

## WHY_NOW

M2.70 closed the bounded frontend self-hosting checkpoint. The next train begins
semantic self-hosting with the smallest deterministic stateful semantic
primitive: symbol insertion order and exact lookup.

## CURRENT_GAP

The frontend can tokenize, parse, canonicalize bounded AST/module/workspace
facts, but semantic identity is still entirely represented by the Python
compiler. There is no S3-authored symbol table candidate that can reject
duplicates and reproduce deterministic lookup slots.

## ARCHITECTURAL_DECISION

M2.71 uses canonical numeric symbol IDs rather than source-name hashing. The S3
kernel accepts at most eight `(symbol_id, kind)` entries, rejects duplicate IDs
or kinds outside 1..4, preserves insertion order as slot identity, and returns
an exact compact `(slot, kind)` scalar for one query. The Python reference uses
`DynamicMap` so the candidate is checked against the existing deterministic
collection semantics.

## IMPLEMENTATION_SUMMARY

- Added `selfhost/semantic/symbol_table_candidate.s3`.
- Added a Python reference/candidate adapter using exact lookup results.
- Added focused tests for present/missing lookup, insertion order, empty tables,
  duplicate rejection, kind rejection, and capacity bounds.
- Avoided modulo fingerprints for the observable lookup result.

## ALTERNATIVES_CONSIDERED

A source-name hash table was considered but rejected for this milestone because
small modulo hashes can collide and weaken differential evidence. Canonical
numeric IDs keep the bounded kernel exact while M2.72 owns source-level name
resolution.

## FAILED_APPROACHES

None recorded yet.

## SURPRISES

None recorded yet.

## TEST_EVIDENCE

GitHub-hosted CI is the available execution environment for this remote-only
implementation. Local T0/T1/T2/T3 evidence is not claimed until CI or a later
hosted/local qualification run reports it.

## BENCHMARK_RELEVANCE

Correctness only. No benchmark or performance claim.

## KNOWN_LIMITATIONS

- Eight-symbol bound.
- Four numeric symbol kinds.
- No lexical scopes, shadowing, modules, imports, overloads, or type identities.
- Canonical numeric IDs are supplied to the kernel; M2.72 will own name
  resolution semantics.

## TECHNICAL_DEBT_ADDED

None intentionally beyond the explicit bounded candidate scope.

## TECHNICAL_DEBT_REDUCED

The candidate avoids the weak modulo-name fingerprint pattern for its observable
lookup result by comparing exact scalar lookup encodings.

## FOLLOW_UP_QUESTIONS

- How should M2.72 represent lexical/module scopes without prematurely coupling
  the candidate to Python AST objects?
- Should later semantic candidates migrate from numeric symbol IDs to canonical
  serialized symbol keys once the representation layer is ready?

## STATUS

IMPLEMENTED_PENDING_GITHUB_CI_AND_IMPACT_METADATA
