# Post-1.50 Canonical Baseline

## Identity

- Research base: `0c4b83853f8ec091d5cf41d3f2071fc1ae06c481` (`origin/main` on 2026-08-17).
- Post-1.50 correctness branch: `06430710d05df925912603bd0a788022439079d5`.
- Research worktree: `C:\Users\samue\Downloads\S3-post150-research-20260817`.
- Primary checkout and archived worktrees were not modified.

## Verification Consumed

The supplied Windows evidence is accepted as historical evidence, not rerun as
a replacement certification campaign:

- post-1.50 focused correctness: 27/27 passed;
- direct text-find and clone probes passed;
- static native contracts for limits, clone semantics, and UTF-8 passed;
- shard A had four pre-existing/unrelated runner failures and no fix-only regression;
- shard C passed 151 tests;
- shard B aggregate and one adapter file timed out on both fix and main;
- Linux x86-64 native certification remains environment-deferred.

The fix sanity set was rerun locally on the fix worktree and passed 27 tests:
`tests/test_post150_runtime_correctness.py`,
`tests/test_m139_dynamic_buffers.py`, and
`tests/test_m140_ordered_collections.py`.

## Source-First Findings

- `bootstrap/s3/dynamic.py` implements bounded owned bytes/text and closed
  specialized vectors, maps, and sets with explicit borrow/move/clone/drop
  behavior.
- `bootstrap/s3/semantic.py` remains the largest compiler module (3,909
  lines); its fixed-value layout and ownership checks are authoritative.
- `bootstrap/s3/ir.py` has dynamic signatures, but vector/map/set families use
  a common `IRType.VECTOR` representation with specialized names.
- `bootstrap/s3/build_graph.py` and the lockfile specs already define stable
  dependency order and content identity without absolute paths or timestamps.
- `bootstrap/s3/test_runner.py` is a deterministic manifest runner; the new
  `tools/s3test.py` adds impact selection, fingerprints, resumable state,
  explainability, and outer per-file timeout.
- `bootstrap/s3/wasm_target.py` is a deterministic structural WASI encoder;
  it explicitly does not claim Wasmtime runtime certification.

## Documentation Drift

- `docs/ai-capabilities.json` correctly describes the bootstrap Python
  implementation, closed scalar/fixed aggregate surface, O0/O1, and Linux-only
  native boundary, but its unsupported-feature section is broad and does not
  express newer specialized dynamic families in enough detail.
- `docs/ai-agent-guide.md` still says no dynamic allocation while later
  milestone source/specs implement bounded owned bytes/text and collections.
- `docs/milestone-1.39.md` is more precise: dynamic owners are not yet allowed
  inside records, static arrays, or enums.
- `pyproject.toml` and README state MIT while `LICENSE` is Apache-2.0.
  `LICENSE_INTENT_REQUIRES_USER_DECISION`.

## Baseline Conclusion

The implementation baseline is a deterministic Python-authoritative compiler
with substantial bounded runtime capability, specialized collection families,
and structural Linux/WASI/ABI work. The next architectural bottleneck is the
absence of a first-class aggregate ownership model. M1.51 should close that
boundary before general generics, package tooling, LSP, or self-hosting.
