# M2.41 Workspace Semantic Graph

## WHY_NOW

RC2 establishes a stable compiler and tooling baseline. Workspace-level
identity is the next boundary needed before project-wide LSP and incremental
queries can share semantic results safely.

## CURRENT_GAP

The repository already had deterministic module topology and local tooling
indexes, but no single snapshot that represented exported symbols, nominal type
identity, imported aliases, and dependent invalidation together.

## ARCHITECTURAL_DECISION

Keep module topology in `module_graph` and add a semantic snapshot above it.
Symbols are identified by `(module, namespace, name)`, while nominal types keep
their provider module identity across imports and aliases. Source paths and
document-open order affect discovery only, never the semantic digest.

An incremental index rebuilds a validated snapshot after each document update
and reports the changed module plus its transitive dependents. This keeps the
initial implementation conservative while making invalidation explicit and
testable. Partial snapshots may contain unresolved imports while documents are
being opened; a complete graph remains fail-closed.

## IMPLEMENTATION_SUMMARY

- Added deterministic symbol and nominal type identities.
- Added export-aware import resolution and private/unknown/conflicting symbol
  diagnostics.
- Added source digest and semantic resolution digest coverage.
- Added an open-order-independent incremental index with transitive
  invalidation.

## ALTERNATIVES_CONSIDERED

- Replacing `module_graph` was rejected because its topology and diagnostics are
  already used by the compiler.
- Caching individual AST nodes was deferred until query profiling identifies a
  real need; the first contract is correctness of identities and invalidation.

## FAILED_APPROACHES

The first local implementation keyed duplicate checks by namespace, which would
have allowed a function and type with the same name to become ambiguous only at
import time. The check now rejects that conflict at module snapshot creation.

## SURPRISES

The existing module graph already provides deterministic topological ordering,
so the new layer only needs to preserve that ordering while adding semantic
namespaces.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`
- `python -m pytest -q tests/test_m241_workspace_semantic_graph.py tests/test_module_graph.py tests/test_cross_module_nominal_type_symbols.py tests/test_modules_pipeline.py`
- Result: 36 passed.

## BENCHMARK_RELEVANCE

None. This milestone changes semantic identity and invalidation contracts; no
performance claim is made.

## KNOWN_LIMITATIONS

The incremental index rebuilds the compact semantic snapshot after an update.
Persistent query-value caching and symbol-level dependency scheduling belong to
the later LSP/query milestones.

## TECHNICAL_DEBT_ADDED

None beyond the deliberately conservative rebuild strategy.

## TECHNICAL_DEBT_REDUCED

Removed the ambiguity between path-based discovery and nominal symbol identity
for workspace consumers.

## FOLLOW_UP_QUESTIONS

- Which LSP requests should consume the snapshot directly in M2.42?
- Should symbol references carry source spans in the next layer, or remain
  separate from the identity graph?
