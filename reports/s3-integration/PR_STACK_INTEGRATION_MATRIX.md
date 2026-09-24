# PR Stack Integration Matrix

Live state rechecked 2026-09-24: #301-#312 remain OPEN, Draft and unmerged;
the earlier individual PR views reported MERGEABLE. Current #301 base/main is
`4c7aaf4...`. CI rollups remain failures before steps; this campaign did not
repair or rerun them.

| PR | Role | Declared base → head | Functional dependency | Required for P2? | Required for selfhost? | Tests/docs value | Current disposition / recommendation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| #301 | Source frontend root | main → `b82a94d` | Independent root; supplies source/token/syntax substrate for #302 | No | Yes, root | Frontend and whole-program specs/tests | OPEN Draft / `KEEP_OPEN_ACTIVE` |
| #302 | Native identifier expressions | #301 → `469578b` | Consumes #301 lexer/parser substrate | No | Yes | Extends frontend slice tests | OPEN Draft / `KEEP_OPEN_ACTIVE` |
| #303 | Native statement sequences | #302 → `6231eb6` | Consumes identifier-capable expression parser | No | Yes | Ordered statement coverage | OPEN Draft / `KEEP_OPEN_ACTIVE` |
| #304 | Native program frontend | #303 → `bf79e61` | Consumes statement/block representation | No | Yes | Program/function frontend coverage | OPEN Draft / `KEEP_OPEN_ACTIVE` |
| #305 | Native semantic execution | #304 → `48f2551` | Executes the whole-program representation | No | Yes | Semantic execution tests | OPEN Draft / `KEEP_OPEN_ACTIVE` |
| #306 | Typed native values | #305 → `889ad59` | Extends semantic evaluator to typed i64/f64 | No | Yes | Typed-value protocol tests | OPEN Draft / `KEEP_OPEN_ACTIVE` |
| #307 | Native indexed data | #306 → `86dccea` | Uses lexer, semantic and typed-value substrate | No | Yes | Indexed-data tests | OPEN Draft / `KEEP_OPEN_ACTIVE` |
| #308 | Native aggregate references | #307 → `db0f6b1` | Extends indexed value/call boundary with aggregate references | No | Yes for aggregate-reference capability | Cross-layer reference tests and Assembly contracts | OPEN Draft / `KEEP_OPEN_ACTIVE` |
| #309 | RMSD scientific kernel | #308 → `d064c17` | Uses borrowed f64 vector references and sqrt/runtime support | No for P2 code; yes for historical RMSD workload | Yes for RMSD capability | Native scientific workload evidence | OPEN Draft / `KEEP_OPEN_ACTIVE` |
| #310 | Exact segment budget experiment + later P2H | #309 declared → `b217808` | Current head contains selected P2 plus rejected post-P2 hardening | Selected P2 delta only; current head no | No | P2 history useful; current head is unsafe as selected P2 | OPEN Draft / `KEEP_OPEN_HISTORICAL`; do not merge current head |
| #311 | Readiness and governance review | #309 declared → `e28bdf1` | None executable | No | No | Accepted Path A record useful; whole readiness review is temporary | OPEN Draft / `REVIEW_ONLY_ARCHIVE`; extract accepted contract only |
| #312 | Semantic closure | #309 declared → `6a97b72` | Test delta exercises P2 and existing APIs | Test delta yes; whole PR no | No | c07 adds 217 boundary-test lines; reports/evidence remain historical | OPEN Draft / `KEEP_OPEN_HISTORICAL`; extract test commit after oracle decision |

Primary dependency classifications: #301 `INDEPENDENT_EXTRACTABLE`; #302-#309
`FUNCTIONALLY_REQUIRED` within the selfhost/scientific capability chain; #310
`SUPERSEDED` as a current P2 integration head because it contains rejected
P2H; #311 `REVIEW_ONLY`; #312 `EVIDENCE_ONLY` at whole-PR scope, with its
test-only delta independently valuable. No PR was closed or retargeted.

The dependency chain is real for the selfhost/scientific line, but does not
make that entire line a P2 implementation prerequisite. RMSD performance
evidence is specifically associated with the #308/#309 workload composition.

## Historical Validation Reconciliation

These are reported historical results, not newly executed gates. Where a
validation SHA differs from the current PR head, the table states whether the
later change was documented as docs-only or whether exact scope is not proven.
All current PR check rollups are failures before any job steps; this audit did
not attribute a cause.

| PR | Historical validation recovered | Validation/source relationship | Current known qualification gap |
| --- | --- | --- | --- |
| #301 | Windows focused 72 passed/2 expected skips; Linux focused 34 passed; compileall passed on both; full suite exit 0 | Functional validation at `5230f922...`; later head changes documented as docs-only | Current checks fail before steps |
| #302 | Linux focused 36 passed; full suite exit 0 | Functional validation at `0cceff...`; later head changes documented as docs-only | Current checks fail before steps |
| #303 | No final full-suite evidence recovered | Exact final validation-to-head relationship not established | Incremental frontend source/test delta; current checks fail before steps |
| #304 | Focused Windows/Linux and compileall/diff checks reported pass; native program structure only, not semantic closure | Final exact tested source SHA not established in recovered summary | Semantic execution arrives in #305; current checks fail before steps |
| #305 | Semantic focused group 14 passed, 1 Linux skip; adjacent matrix/compileall/diff passed; full suite passed | Full suite at `34a923...`; later changes described as docs-only | Current checks fail before steps |
| #306 | Full suite 4,021 passed, 312 skipped, 0 failed | Campaign ran on Windows; Linux qualification explicitly deferred | Linux native qualification not established; current checks fail before steps |
| #307 | Full suite 4,027 passed, 312 skipped, 0 failed; local indexed probes | Full suite at functional `91390...`; Linux native qualification deferred | Aggregate-reference boundary was intentionally left for #308; current checks fail before steps |
| #308 | Intermediate full suite had three stale exhaustive-opcode-contract failures; targeted repair passed | No final full-suite rerun after repair under the one-run policy | Current checks fail before steps; no final suite claim is made |
| #309 | Full suite passed at `e07d0b5...`; Linux x86-64 native canary passed | Later two #309 commits were documentation-only through `d064c17...` | Current checks fail before steps; RMSD workload needs #308/#309 capabilities |

The evidence is uneven. The chain is functionally meaningful, but this audit
does not certify every intermediate main state from current full-suite proof.
No historical suites were rerun.
