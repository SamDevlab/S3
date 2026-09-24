# S3 1.x PR Stack Integration Closure

## Executive Decision

```text
STACK_ANALYSIS_CLOSED=YES
STACK_INTEGRATION_EXECUTED=NO
SELECTED_INTEGRATION_STRATEGY=CLEAN_P2_EXTRACTION
INTEGRATION_CANDIDATE_READY=NO
BLOCKER_PR_STACK=READY_FOR_INTEGRATION_ACTION
NEXT_CRITICAL_BLOCKER=HUMAN_INTEGRATION_APPROVAL
NEXT_CAMPAIGN=NONE_HUMAN_DECISION_REQUIRED
```

The selected P2 implementation does not functionally depend on selfhost PRs
#301-#309. Its exact implementation commits applied to current main without
source conflict, compileall passed, and the three implementation files match
the selected P2 tree. However, the one allowed focused extraction trial failed
an existing frozen-output expectation and skipped Linux-native coverage on
this Windows host. The cause of the byte mismatch was not established.

Do not silently rebaseline the test or claim a stable candidate. A human must
choose whether to retain the #309/e07 test baseline or authorize a test-only
baseline update for current main followed by Linux-focused validation. No
stable branch or PR was created. No implementation, benchmark, CI, merge,
release, tag, default change, or power action occurred.

## Live Stack Snapshot

Current `main` is `4c7aaf4ad59fdacdd83f230e11a0bd979081c80a`, unchanged from
#301's declared base. At the initial full snapshot (2026-09-24 15:03 UTC),
#301-#312 were all OPEN, Draft, unmerged, and reported MERGEABLE; all listed
check rollups failed before steps. A live head/state recheck at 15:25 UTC found
the same branches and heads, all OPEN and Draft. This campaign did not diagnose
or rerun CI. Full metadata is in `PR_STACK_GRAPH.json`.

The heads are: #301 `b82a94d9`; #302 `469578b8`; #303 `6231eb67`; #304
`bf79e618`; #305 `48f2551c`; #306 `889ad594`; #307 `86dccea0`; #308
`db0f6b15`; #309 `d064c17e`; #310 `b2178088`; #311 `e28bdf1e`; #312
`6a97b728`.

## Graph and Dependency Finding

Declared PR bases form #301→#302→#303→#304→#305→#306→#307→#308→#309. The
functional chain is real within the selfhost/scientific capability lane:
frontend substrate, identifiers, ordered statements, whole-program frontend,
semantic execution, typed values, indexed values, aggregate references, then
RMSD. #301 is an independent root relative to current main; #302-#309 consume
predecessor capabilities. The chain is a coherent selfhost milestone, not
proof that it is a P2 prerequisite.

There is ancestry drift after #309: #310-#312 declare #309 head
`d064c17...` as base, but their Git ancestry forks from #309 source commit
`e07d0b5...`, omitting two documentation-only commits. That is not a source
conflict. Current main is zero commits ahead of #301 base; #309 is 144 commits
ahead, merge base `4c7aaf4...`; changed-file overlap against current main is
classified `NONE`.

P2 itself uses the existing x86-64 backend and Assembly representation. No
P2 implementation dependency on #301-#309 symbols was found. The RMSD
performance workload used in historical P2 evidence does depend on #308/#309;
that distinction is recorded in `P2_DEPENDENCY_MATRIX.md`. Ancestry is not
implementation dependency.

Historical test evidence is uneven: #301/#302 have reported full-suite passes;
#303 has no final full-suite evidence recovered; #304's evidence is structural
rather than semantic; #306/#307 full-suite records are Windows-only with
Linux-native qualification deferred; #308 has targeted repair after three
stale-contract failures but no post-repair full-suite rerun. #309 reports a
full-suite pass at its source commit and a Linux native canary; its later two
commits are docs-only. Per-PR details are in
`PR_STACK_INTEGRATION_MATRIX.md`. This audit did not rerun historical gates.

## P2 Exact Delta

The selected candidate is `1a76e341098b54a639fec22eecea362cc243c46f`, from
control `e07d0b5464bf472b2ca18993f3e196a234ff0fc5`. Its exact delta is three
implementation files, one focused test file, and four experimental reports:
8 files, +1,326/-37. The implementation commits are `f4353c1b...` and
`1a76e341...`; `28c8148df8a30ec93b9ae3472bd9983532cfcee0` is
documentation/evidence only. Per-file hashes,
byte counts, surface/contracts, and trial facts are in `P2_EXACT_DELTA.md` and
`.json`.

`PER_INSTRUCTION` remains default. `EXACT_SEGMENT` is backend-configured and
not a stable end-user option. The accepted concurrency scope is serialized
same-artifact FFI plus qualified synchronous callback re-entry; concurrent
same-artifact host-thread entry is not supported or qualified. Path A was
human accepted; the complete Exact Segment Budget ADR remains `PROPOSED`.

## P2H Exclusion

P2H starts at `6f320242...`; current #310 head `b2178088...` includes it and
is not safe to merge as selected P2. The P2H delta rewrites the emitter,
adds 142 test lines, and updates/adds hardening reports. These executable and
test deltas are excluded; no P2H claim is substituted for P2. See
`P2H_EXCLUSION_MANIFEST.md`.

## #312 Semantic Test Bundle

Whole #312 is not a required integration PR. Commit
`c07b2c486b98e8408119f44ceedceb46c6d2549b` adds 217 test-only lines to
`tests/test_exact_segment_instruction_budget.py` for invalid input domains,
signed-boundary/U64 limits, execution parity, and maximum segment-weight
encoding. It is the required test delta for a complete P2 integration, subject
to the frozen-output oracle decision. The Linux evidence at c07 is 75 focused
passed and 4,390 full-suite passed, 1 skipped, 572 subtests, 0 failed, exit 0;
valid transcript SHA-256 is `6ebbbdc6...f3e8b0`. The full PR also contains
research reports/evidence and an invalid archive attempt; these are not
required product content. A file-list audit corrected the JSON inventory to
include `SEGMENT_PLANNER_AUDIT.md`.

See `P2_SEMANTIC_TEST_BUNDLE.md`.

## #311 Governance and Documentation Bundle

PR #311 is review/governance material, not executable dependency. Path A is
accepted for the narrow concurrency contract and should be represented in a
product-facing contract if/when P2 ships. Include the explicit scope and
limitation; do not imply concurrency support. The full proposed ADR, readiness
review, experimental reports, and temporary review artifacts are not
automatically part of the shipping bundle. The ADR remains `PROPOSED` absent
separate governance acceptance.

## Current Main Divergence

```text
CURRENT_MAIN=4c7aaf4ad59fdacdd83f230e11a0bd979081c80a
MAIN_AHEAD_OF_301_BASE=0
STACK_AHEAD_OF_MAIN_AT_309=144
MERGE_BASE=4c7aaf4ad59fdacdd83f230e11a0bd979081c80a
MERGE_CONFLICT_CLASSIFICATION=NONE
```

No current-main file overlap was found against #301-#309/P2. This does not
resolve the test baseline mismatch observed in the dry-run.

## Strategy A: Sequential Parent Chain

Classification: `A_FEASIBLE_HIGH_DEBT`. It preserves granular review and
functional lineage, but requires nine ordered merge operations, retains the
144-commit stack and stale failed CI, and delays P2 behind unrelated
selfhost/scientific capability delivery. Historical intermediate evidence
is uneven: #303 lacks final full-suite evidence and #308 has no post-repair
full-suite rerun. Merging is not authorized. It is not selected.

## Strategy B: Consolidated Selfhost Integration

Classification: `B_FEASIBLE_NOT_PREFERRED` based on the intact capability
chain and unchanged main base, but no replay dry-run was spent on this
strategy. Consolidation could reduce open-stack operational overhead, while
making a large review unit and weakening the existing meaningful boundaries.
It retains selfhost capability work on the P2 path without evidence that P2
needs it. It is not selected.

## Strategy C: Clean P2 Extraction

Selected strategy, currently blocked from candidate readiness. The one
throwaway attempt cherry-picked the exact P2 implementation commits and c07
test commit onto current main. Source cherry-picks were clean; P2 source bytes
match the selected SHA; compileall and diff-check passed. Focused test result:

```text
18 passed
1 failed
21 skipped
exit 1
```

The failure is `test_default_mode_matches_frozen_e07_native_assembly_bytes`:
expected 50,066, observed 49,947 for `linear`. Its cause is unknown. Linux
native tests skipped because the trial host was Windows. No retry or oracle
edit is allowed in this analysis cycle. Therefore clean source application is
proven, but clean qualification is not.

## Strategy D: Minimal Consolidated Integration

Classification: `BLOCKED_BY_CLEAN_P2_VALIDATION`. The minimum bundle is
current main + exact P2 implementation commits + the P2 test module + c07
boundary tests after resolving the baseline oracle + a concise product-facing
Path A contract. No selfhost PR is a P2 code prerequisite. Full #311/#312
review packages, invalid archive evidence, duplicated research reports, and
P2H are excluded. Because the minimum bundle inherits Strategy C's failing
oracle, no consolidated candidate was constructed.

## Selected Strategy and Minimal Bundle

```text
SELECTED_INTEGRATION_STRATEGY=CLEAN_P2_EXTRACTION
MINIMAL_REQUIRED_BASE=main@4c7aaf4ad59fdacdd83f230e11a0bd979081c80a
MINIMAL_REQUIRED_PRS=NONE
P2_IMPLEMENTATION=f4353c1b5bc3557dd05188d893f85de264300d5f,1a76e341098b54a639fec22eecea362cc243c46f
P2_TESTS=selected P2 test file plus c07b2c486b98e8408119f44ceedceb46c6d2549b, pending oracle decision
GOVERNANCE_DOC=accepted Path A concurrency clarification
FULL_ADR=PROPOSED_NOT_REQUIRED
```

This strategy separates the P2 product lane from selfhost delivery. Before a
stable Draft candidate exists, a human must choose: retain the #309/e07 base
for the frozen byte oracle, or authorize a test-only update to the main-based
oracle and then obtain Linux-focused proof. Do not silently adapt the
expectation or infer the mismatch's cause.

## PR Disposition Plan

- #301-#309: keep open and active as the separate selfhost/scientific chain.
- #310: keep historical; current P2H-based head must not merge as selected
  P2.
- #311: review-only archive role; carry only the accepted contract wording
  where product docs require it.
- #312: keep historical; extract only c07 tests after resolving their oracle
  compatibility. No PR is closed or retargeted by this audit.

## Dry-Run Results and Validation

The detached scratch worktree is clean at
`13c8427057bdf6135830b47bbb5b3be07ce418f7`; it is a failed trial, not a
stable candidate. No remote branch or PR was created.

```text
P2_IMPLEMENTATION_CONTENT_MATCH=YES
COMPILEALL=PASS
FOCUSED_VALIDATION=FAIL (18 passed, 1 failed, 21 skipped; exit 1)
LINUX_NATIVE=NOT_RUN (native cases skipped on Windows)
FULL_SUITE_RERUN=NO
FULL_SUITE=NOT_RUN
BENCHMARK_RERUN=NO
CI_RERUN=NO
DIFF_CHECK=PASS
PERFORMANCE_REQUALIFICATION_REQUIRED=NO_FOR_UNCHANGED_P2_SOURCE
```

Existing performance results remain limited to the measured P2/#309 workload
composition, including RMSD. They are not broadened to a different extracted
composition by this report.

## Remaining Risks and Next Blocker

The immediate blocker is a human integration decision about the frozen-byte
oracle; after that, a stable-base candidate needs Linux-native focused proof.
Separate remaining promotion blockers are S3 CI failing before job steps with
unknown cause, S3-Benchmarks Actions disabled/no checks, and product code-size
policy. The code-size policy remains open; no new policy or default was
chosen. The full ADR remains proposed.

```text
BLOCKER_PR_STACK=READY_FOR_INTEGRATION_ACTION
BLOCKER_CI=OPEN
BLOCKER_CODE_SIZE_POLICY=OPEN
OPEN_BLOCKERS=3
NEXT_CRITICAL_BLOCKER=HUMAN_INTEGRATION_APPROVAL
NEXT_CAMPAIGN=NONE_HUMAN_DECISION_REQUIRED
```

Analysis is closed. Integration is not executed. No performance research,
benchmark, CI repair, merge, default switch, tag, release, shutdown, reboot,
VM shutdown, or VM reboot was performed. Keep host, VM, and VirtualBox running.
