# M2.42 LSP Project Intelligence

## WHY_NOW

M2.41 established deterministic workspace symbols, imports, nominal identities,
and invalidation. The next boundary is to make LSP project queries consume that
identity instead of guessing from document-local names.

## CURRENT_GAP

The existing LSP facade could index documents and perform local queries, but
cross-file definition, references, rename, alias handling, workspace symbols,
stale-document rejection, and ambiguous-import failure had no single semantic
contract.

## ARCHITECTURAL_DECISION

Keep the LSP document store as the protocol-facing layer and feed each valid
document into `WorkspaceSemanticIndex`. Definition, references, and rename use
the canonical `SemanticSymbol` identity, so imported aliases resolve to the
provider declaration and provider queries find all consumer aliases. An
incomplete or rejected workspace snapshot remains fail-closed. Transport
cancellation is represented as a bounded request-id set and is consumed before
dispatching the matching request.

## IMPLEMENTATION_SUMMARY

- Added URI-to-logical-path normalization for workspace indexing.
- Added cross-file semantic definition, reference, and rename resolution,
  including aliases in either query direction.
- Added workspace semantic diagnostics for rejected snapshots and preserved
  monotonically increasing document versions.
- Added workspace-symbol capability backed by all open documents.
- Added one-shot JSON-RPC cancellation handling for request ids.

## TEST_EVIDENCE

- `python -m compileall -q bootstrap/s3`
- `python -m pytest -q tests/test_m242_lsp_project_intelligence.py tests/test_m241_workspace_semantic_graph.py tests/test_m158_lsp.py tests/test_m236_tooling_stability.py tests/test_m213_lsp_transport.py`
- Result: 22 passed.
- `git diff --check`: PASS.

## BENCHMARK_RELEVANCE

None. This milestone changes project semantic query correctness and protocol
behavior; no performance claim is made.

## T4_STATUS

Not run. The train policy reserves full T4 for M3.00.

## KNOWN_LIMITATIONS

The index rebuilds a compact semantic snapshot after each accepted document
update. Persistent query caching and cancellation of already-running expensive
queries remain later concerns.

## FOLLOW_UP

M2.43 can use the same train after this PR is merged. It must preserve the
semantic identity and fail-closed query contracts established here.
