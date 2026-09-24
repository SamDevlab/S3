# Exact P2 Delta

Selected candidate: `1a76e341098b54a639fec22eecea362cc243c46f`

Control/fork base: `e07d0b5464bf472b2ca18993f3e196a234ff0fc5`
Original #309 head: `d064c17ea811ab926df515cb90884e8c6efffb3d`

## Commit Lineage

| Commit | Classification | Effect |
| --- | --- | --- |
| `f4353c1b5bc3557dd05188d893f85de264300d5f` | P2 implementation and tests | Adds exact segment planning/emission and focused tests |
| `28c8148df8a30ec93b9ae3472bd9983532cfcee0` | Documentation/evidence only | Records experimental validation; no executable change |
| `1a76e341098b54a639fec22eecea362cc243c46f` | P2 implementation correction and regression | Preserves failure context in the fast path |

The full hashes for the first and last implementation commits are the
extraction identity. The documentation commit is historical provenance, not
an executable prerequisite.

## File Delta: `e07d0b5...` to `1a76e34...`

Eight files changed: three implementation files, one focused test file, and
four experiment/design reports (1,326 insertions, 37 deletions).

| File | P2 SHA-256 | Bytes | Role |
| --- | --- | ---: | --- |
| `bootstrap/s3/backends/x86_64/backend.py` | `236c36df0b528b2edb88b124a0b36b9da34ea77c8d69a3a793bc3173dd133ea9` | 9005 | Backend mode/configuration |
| `bootstrap/s3/backends/x86_64/emitter.py` | `bcfb7f36728219d3b0e5847979b625574681be0007c8181ae3dfe52556ca52dc` | 91155 | Exact fast path and scalar fallback |
| `bootstrap/s3/backends/x86_64/instruction_budget.py` | `ee124fb48caa9e6f7eff95ad6187141b1d5cc6f3a72eef0c7533471db1716015` | 6158 | Deterministic segment plan and diagnostics |
| `tests/test_exact_segment_instruction_budget.py` | `588241bb60da005c5b082a6f63c4ba67f914b54e7c47f5578f1082490584d408` | 23582 | P2 focused structural/native regressions |
| `reports/s3-exact-segment-budget/E0_BUDGET_EQUIVALENCE.md` | `d44309519b340e42c1f81a37f335959c4818e01d81f7c7d3c0d9bdb161ddf232` | 1921 | E0 contract/evidence mapping |
| `reports/s3-exact-segment-budget/EXACT_SEGMENT_BUDGET_DESIGN.md` | `b95cd16422d72721d9c613d4e9c216454fa5805091def47ad81248c8640416f0` | 2806 | Planner/emitter design |
| `reports/s3-exact-segment-budget/EXPERIMENTAL_VALIDATION.md` | `eebaa87b90c9ab9bc8791efb285403a98c448d5c0dc2d2e1c4b75474b83db0b5` | 2131 | Historical experiment record |
| `reports/s3-exact-segment-budget/SEGMENT_PLANNER_AUDIT.md` | `1ea5959d6bde2f234b87334e6fed833bec2c32b862b638eb3422f5cc21c41283` | 2456 | Planner invariants/audit |

The four reports are research/provenance material. A product-facing feature
contract should separately state the accepted Path A concurrency scope. The
complete proposed ADR remains `PROPOSED`.

## Contracts and Surface

- `PER_INSTRUCTION` remains the default; `EXACT_SEGMENT` is backend-configured
  and is not a stable CLI/API option.
- Segment admission precharges only when the complete logical segment fits;
  otherwise the exact per-instruction fallback runs.
- Calls and control flow split segments. Existing frame, bounds,
  initialization, and memory checks remain in emitted instruction paths.
- Instruction limits are positive unsigned 64-bit values; zero, negative,
  non-integer, and overflow inputs are rejected.
- Qualified concurrency is serialized calls to one loaded artifact and the
  qualified synchronous callback re-entry. Concurrent host-thread entry into
  one artifact is unsupported and unqualified.
- No source syntax, Assembly/IR format, native ABI, FFI signature, or default
  behavior is intentionally changed by P2.

## Stable-Base Trial

The one allowed extraction trial applied the exact P2 implementation commits
to current `main` (`4c7aaf4...`) and then applied #312 test-only commit
`c07b2c4...`. Cherry-picks applied without source conflicts. The three P2
implementation files remained byte-identical to the selected P2 tree and
`compileall` passed. Focused validation did not pass on this composition:
`test_default_mode_matches_frozen_e07_native_assembly_bytes` expected 50,066
bytes and observed 49,947 for case `linear`. Aggregate result: 18 passed,
1 failed, 21 skipped. Linux-native cases were skipped on the Windows host.
`git diff --check` passed.

This proves a frozen-output baseline mismatch, not its cause and not a P2
semantic defect. It prevents declaring the extraction candidate qualified.
No retry, oracle edit, Linux run, full suite, CI, benchmark, or remote
candidate was performed. The detached, clean trial worktree is not a stable
integration candidate.

## Decision

P2 has no demonstrated functional dependency on #301-#309 implementation
symbols. Clean extraction is the selected lineage strategy, but its test
composition requires an explicit human decision: retain #309 ancestry to
preserve the `e07`-frozen output baseline, or authorize a test-only baseline
update for current `main` followed by Linux-focused validation. This audit
does not change the oracle.
