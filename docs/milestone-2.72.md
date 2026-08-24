# Milestone 2.72: Bounded Self-Hosted Name Resolution Candidate

M2.72 extends the semantic self-hosting train with bounded lexical name
resolution authored in S3.

## Scope

The candidate accepts up to eight canonical declarations across up to eight
lexical scopes. Each scope after the root references an earlier parent scope,
which makes the bounded scope graph acyclic by construction. Resolution starts
at the query scope and walks toward the root, returning the nearest visible
declaration.

Declarations are represented as canonical `(symbol_id, kind, scope_id)` values.
The observable result is the exact compact `(slot, kind)` scalar used by M2.71,
not a modulo hash or name fingerprint. The same symbol may appear in nested
scopes and therefore shadow an outer declaration, but duplicate declarations of
the same symbol inside one scope fail closed.

## Evidence Contract

- S3 source: `selfhost/semantic/name_resolution_candidate.s3`.
- Python adapter/reference: `bootstrap/s3/name_resolution_candidate.py`.
- Focused contract: `tests/test_m272_name_resolution_candidate.py`.
- Maximum scopes: 8.
- Maximum declarations: 8.
- Root parent: `-1`.
- Every non-root parent must reference an earlier scope.
- Duplicate `(symbol_id, scope_id)` declarations fail closed.
- Nested shadowing is supported and nearest-visible declaration wins.
- Sibling declarations are not visible across sibling scopes.
- Observable differential comparison is exact scalar equality.
- Python remains the reference/default compiler path.

## Non-claims

M2.72 does not claim source-text identifier interning, workspace import
resolution, overload resolution, type checking, lowering, native self-hosting,
production promotion, performance improvement, or full compiler self-hosting.

The local T0/T1/T2/T3 and impact gates pass on Python 3.11, 3.12 and 3.13.
The current GitHub Actions run is externally blocked before job steps by the
repository billing/spending-limit condition; that state is not treated as a
local test result or silently converted into a PASS. M2.72 remains a
**locally qualified candidate** until the integration decision records that
external limitation.
