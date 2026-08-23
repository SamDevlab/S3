# Milestone 2.67: Incremental Invalidation Candidate

M2.67 adds a bounded S3-authored candidate for invalidating frontend modules
affected by changed workspace dependencies.

## Scope

The candidate accepts the M2.66 workspace graph, with up to eight modules and
sixteen import edges, plus a non-empty set of up to eight changed modules. A
changed module invalidates itself and every importer reachable through the
directed import graph. The S3 implementation uses a depth bound of eight, so
cycles terminate and every simple path in the bounded graph is covered. Module
and change ordering is canonicalized, unknown changes fail closed, and the
result is a deterministic fingerprint of the invalidated modules.

Incremental file discovery, cache storage, invalidation scheduling, and
production build activation remain out of scope.

## Evidence Contract

- S3 source: `selfhost/frontend/invalidation_candidate.s3`.
- Python adapter: `bootstrap/s3/invalidation_candidate.py`.
- Focused contract: `tests/test_m267_incremental_invalidation.py`.
- Impact shard: `m267`.
- Direct, transitive, canonical-order, unknown-change, and empty-change
  contracts are covered.
- No native, benchmark, or performance claim is made.
- Global T4 remains reserved for M3.00.
