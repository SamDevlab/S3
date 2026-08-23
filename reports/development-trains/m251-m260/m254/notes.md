# M2.54 Recursive Compiler Data Substrate

## WHY_NOW

Compiler graphs and trees require nested relationships that remain bounded and
deterministic even when a graph contains a back edge. Python call-stack
recursion is not an acceptable lifetime or traversal boundary for this hosted
foundation.

## ARCHITECTURAL_DECISION

`RecursiveNodeStore` gives compiler data stable integer identities, bounded
node and edge counts, insertion-ordered children, and an iterative depth-first
walk. Cycles are representable, but traversal uses a visited set and a
configured path-depth limit, so recursive graphs terminate deterministically.
Unknown nodes and duplicate edges fail closed. No AST/IR integration, native
pointer contract, or unbounded graph storage is claimed.

## IMPLEMENTATION_SUMMARY

- Added bounded recursive node and edge storage for hosted compiler data.
- Added immutable node snapshots with deterministic child order.
- Added cycle-aware iterative traversal and depth enforcement.
- Added regressions for nested order, cycles, capacity, depth, and invalid
  edges.
- Added M2.54 impact and shard metadata.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`: PASS
- Focused M2.53/M2.54 regression matrix: 9 selected, 9 passed, 0 skipped,
  0 failed.
- M2.54 T2 at source HEAD
  `609b4c0f4fac6f00e91d7b1c266463619476f163`: 1 selected, 1 passed,
  0 failed, 0 timed out.
- M2.54 T3 shard at the same source HEAD: 1 selected, 1 passed,
  0 failed, 0 timed out.
- `git diff --check`: PASS.

## BENCHMARK_SCOPE

No benchmark was executed. This milestone validates bounded recursive data
semantics only; no performance claim is made.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

AST/IR parser integration, serialization, and language-level recursive syntax
remain later concerns. The current store is a safe hosted substrate for those
components.
