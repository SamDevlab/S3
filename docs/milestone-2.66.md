# Milestone 2.66: Workspace Graph Candidate

M2.66 adds a bounded S3-authored workspace graph candidate for the frontend
self-hosting train.

## Scope

The candidate accepts up to eight named modules and sixteen import edges. It
canonicalizes module and edge order, verifies that every import target exists,
and emits a deterministic graph fingerprint. The Python adapter is the
reference for graph normalization and fail-closed validation. File discovery,
incremental builds, and production build-graph activation remain out of scope.

## Evidence Contract

- S3 source: `selfhost/frontend/workspace_candidate.s3`.
- Python adapter: `bootstrap/s3/workspace_candidate.py`.
- Focused contract: `tests/test_m266_workspace_candidate.py`.
- Impact shard: `m266`.
- Unknown import targets and empty workspaces fail closed.
- No native, benchmark, or performance claim is made.
- Global T4 remains reserved for M3.00.
