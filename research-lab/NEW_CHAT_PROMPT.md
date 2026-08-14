# New Chat Bootstrap Prompt

Copy/paste the block below into a new ChatGPT/Codex conversation when the previous conversation reaches its context limit.

```text
We are continuing the S3 compiler research project.

Production repository:
https://github.com/SamDevlab/S3

Durable research branch:
research/zettelkasten-lab-20260812

Durable locator:
GitHub issue #171 — [Research] S3 Zettelkasten compiler research lab

Before proposing or implementing anything:

1. Fetch/read these files from that research branch, in this order:
   - research-lab/HANDOFF.md
   - research-lab/STATE.json
   - research-lab/RESEARCH_PROTOCOL.md
   - research-lab/reconciliations/P4_20260812.md
   - research-lab/zettelkasten/INDEX.md
   - research-lab/sources/REGISTRY.md
   - research-lab/sources/README.md
   - research-lab/sources/WISHLIST.md
   - research-lab/experiments/README.md
   - research-lab/hypotheses/TERNARY_VIRTUALIZATION.md
   - research-lab/prototypes/README.md

2. Treat them as durable context for prior decisions, P1-P4 performance history, literature bridges,
   canonical source/deduplication state, Zettelkasten conventions, experiments, testing policy
   and safety constraints.

3. Inspect CURRENT origin/main independently. SHAs in the handoff are historical anchors only.

4. Never merge research/zettelkasten-lab-20260812 directly to main.
   Proven mechanisms must be ported to a fresh production branch from current main.

5. Production state recorded at the latest durable reconciliation:
   P1=COMPLETE
   P2=COMPLETE
   P3=COMPLETE
   P4=COMPLETE
   P4_PR=170
   P4_IMPLEMENTATION_HEAD=59df1d0f9ab9147b8d7f71a1db395c5fab560171
   P4_MERGE_COMMIT=a0b694fadc985c0b8e0944fb7844e14f72a838d8
   P5_STARTED=NO

   P5-AUDIT=COMPLETE (research only; no production P5 selected)

   P5-AUDIT found that the lexical P4 byte-frame metric `5638` decomposes
   into `4589` register-initialization accesses, `837` memory-initialization
   accesses and `212` trit payload accesses. The exact JSMN corpus has `34`
   backedges but `0` phis, `0` phi-edge copies and `0` critical edges. Do not
   treat SSA as dominant without a separate phi-heavy corpus. Dynamic
   weighting and semantic required/avoidable shares remain open.

6. Critical P4 causal result:
   - the existing whole-function liveness/interference allocator was already capable;
   - X8664Backend.register_allocation defaulted false;
   - native default RA_OFF caused emitter frame canonicalization;
   - making existing RA the native default reduced direct frame loads 1549->491 and stores 1520->471;
   - RA algorithm quality was NOT established as the primary cause;
   - total frame accesses 9282->7175, but metadata accesses remained 5638->5638;
   - residual primary bottleneck is REPEATED_MEMORY_STATE_MATERIALIZATION;
   - next recommended area is SSA_DESTRUCTION_AND_MEMORY_STATE_METADATA_STAGING.

7. Metric nuance from P4:
   GCC-relative geomean worsened 34.708x->38.976x because the comparator denominator varied,
   while absolute S3 runtime improved 8890.414->8405.053 ns/parse (-5.46%).
   Keep direct causal structural metrics, absolute S3 runtime and comparator-relative ratios distinct.

8. Preserve the methodology:
   - one Zettel = one atomic idea;
   - distinguish source-established fact vs S3 inference vs measurement;
   - negative results/counterexamples are permanent knowledge;
   - mathematical models compete by evidence;
   - exact expensive algorithms may be bounded research oracles;
   - distinguish RA enablement, RA input quality, allocator quality and true spill behavior;
   - do not assume S3 trit semantics equal any named many-valued logic without exact truth-table comparison;
   - treat quantum/DNA ternary literature as representation/architecture inspiration, not as a required backend;
   - information-theoretic quantities require a defined probability model; otherwise use deterministic information/precision measures;
   - deduplicate literature by work+authors+edition using sources/REGISTRY.md;
   - focused tests during implementation, full suite only for a coherent production candidate.

9. Current research has three connected flexibility dimensions:
   LOCATION_FLEXIBILITY
   REPRESENTATION_FLEXIBILITY
   PROOF_KNOWLEDGE_FLEXIBILITY

10. Highest-priority unresolved experiments after P4:
   - S3-EXP-0014 memory-state metadata provenance;
   - S3-EXP-0015 SSA destruction vs metadata staging;
   - S3-EXP-0013 compiler information-loss boundary audit, refocused after P4.

11. Parallel ternary research remains:
   - S3-EXP-0009 exact current S3 trit semantics/lowering map;
   - S3-EXP-0010 ternary primitive-basis exact oracle;
   - S3-EXP-0011 ternary/finite-state minimization;
   - S3-EXP-0012 ternary representation conversion graph.

12. Do NOT start or define production P5 from the post-P4 recommendation alone.
    P5-AUDIT has separated physical origin for the P4 JSMN corpus, but dynamic
    weighting and semantic necessity remain promotion gates. The current
    evidence recommends proof-preserving initialization-state propagation with
    lazy native materialization, not a generic RA rewrite or SSA-only pass.

13. If I provide new books/files, first normalize title/authors/edition and classify each as NEW,
    EXACT_WORK_REUPLOAD, EDITION_VARIANT or TOPIC_OVERLAP in sources/REGISTRY.md.

14. If I provide new FINAL_P*_REPORT.md or *_RESULT.json files, reconcile them with STATE.json
    and update HANDOFF.md/STATE.json before selecting the next production milestone.

Start by returning:
CURRENT_ORIGIN_MAIN=
RESEARCH_BRANCH_HEAD=
DURABLE_CONTEXT_LOADED=YES/NO
SOURCE_REGISTRY_LOADED=YES/NO
PRODUCTION_STATE_FROM_HANDOFF=
P4_CAUSAL_RESULT=
POST_P4_RESIDUAL_QUESTION=
TERNARY_RESEARCH_QUESTION=
NEXT_UNRESOLVED_EXPERIMENTS=
P5_PRODUCTION_TARGET_SELECTED=YES/NO

Then continue from evidence, not assumptions.

CURRENT_P5_PREWORK_CHECKPOINT=COMPLETE
P5_PREWORK_BASE=a0b694fadc985c0b8e0944fb7844e14f72a838d8
STATIC_DIRECTLY_PROVEN=324/5426
JSMN_DYNAMIC_DIRECTLY_PROVEN=356/21221
P5_PROMOTION_DECISION=MORE_RESEARCH_REQUIRED
P5_STARTED=NO
P6_STARTED=NO
FULL_SUITE_RUN=NO
SHUTDOWN_AUTHORIZED=NO
The unclassified remainder is UNKNOWN/UNMEASURED, not conditional. Do not
start production P5 or P6 until observer, reset/store-deadness, failure-path
and hosted TADDR differential proofs are closed.

P5-RESEARCH-CLOSURE CHECKPOINT (2026-08-12):

```text
BASE=a0b694fadc985c0b8e0944fb7844e14f72a838d8
INITIALIZATION_STATIC_TOTAL=5426
JSMN_DYNAMIC_INITIALIZATION=21221
ALLOCATED_MEMORY_RESET_EVENTS=14367
RESET_SEMANTIC_CLASSIFICATION_COVERAGE=UNAVAILABLE
TEMP_TADDR_DIFFERENTIAL=PASS_FOR_SIX_O0_CORPORA
PRODUCTION_TADDR_SUPPORT=UNCHANGED_UNSUPPORTED
O1_SLICE_OPTIMIZER_LIMITATION=YES
PROMOTION_DECISION=MORE_RESEARCH_REQUIRED
P5_STARTED=NO
P6_STARTED=NO
FULL_SUITE_RUN=NO
SHUTDOWN_AUTHORIZED=NO
```

Read the external numbered closure reports before selecting any production
change. Do not turn the temporary TADDR experiment into a production patch.

## CI/P5 autonomous campaign checkpoint - 2026-08-13

The current campaign has completed the Actions audit, pytest collection audit,
O1 slice root-cause correction and eight-workload post-P4 reprofile. Read
`research-lab/reconciliations/CI_P5_AUTONOMOUS_CAMPAIGN_20260812.md` and the
external campaign reports before acting.

```text
O1_SLICE_FIX_PR=172
O1_SLICE_FIX_HEAD=19b39c71fb644d2f4d923d1695eb3ac43e7e49e7
O1_SLICE_FIX_MERGE=229811359948cf8e12848036882edaa89108a9fa
CI_OPTIMIZATION_PR=173
CI_OPTIMIZATION_HEAD=ae278bfdec2c9b957a1d885c2076d37f58f97df2
CI_OPTIMIZATION_STATUS=MERGED
CI_OPTIMIZATION_MERGE=1a775ba79f3abb6d3b33bb7d710ab67d0f808e18
ORIGIN_MAIN_END=1a775ba79f3abb6d3b33bb7d710ab67d0f808e18
P5_SELECTION=NO_VALID_TARGET_YET
P5_STARTED=NO
P6_STARTED=NO
```

The #173 renderer passed and the PR is merged. The subsequent P5 target
selection v2 is complete: PR #174 implemented the bounded x86-64 immediate
instruction-limit guard and merged as
`a08ee420e9bd0734a28363d60fc0f5f3e1169fb4`. Read
`research-lab/reconciliations/P5_TARGET_SELECTION_V2_20260813.md` and the
external P5 report. P6 remains forbidden, and shutdown remains unauthorized.

## Authoritative current checkpoint - P6 complete

The preceding block is historical. The P6 simplicity-first campaign was
completed after that checkpoint. Reconcile against `STATE.json` before any
future work:

```text
P6_CAMPAIGN=P6_SIMPLICITY_FIRST_DISCOVERY_V1
P6_SELECTION=READY_FOR_IMPLEMENTATION
P6_NAME=P6_DIRECT_NON_F64_TCONST_IMMEDIATE
P6_BASE=a08ee420e9bd0734a28363d60fc0f5f3e1169fb4
P6_HEAD=b9ac7d9e8370f013889b8efc9acaed0429447ac2
P6_PR=175
P6_MERGE=69f5908687123a9ad7a4659b5133f815f08377b1
ORIGIN_MAIN_FINAL=69f5908687123a9ad7a4659b5133f815f08377b1
FULL_SUITE_HEAD=b9ac7d9e8370f013889b8efc9acaed0429447ac2
FULL_SUITE_EXIT=0
LINUX_NATIVE=PASS
CI=PASS
P7_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
```

The P6 research reconciliation and experiment registry are authoritative for
the two-track profiling, candidate falsification, production result, and
negative results. Do not recreate P5, reopen P6, start P7, or issue shutdown.

## Current authoritative checkpoint: P7 complete

Reconcile `research-lab/STATE.json` before any further campaign. P7 selected,
implemented, and merged PR #176:

```text
P7_NAME=P7_DIRECT_TCMP_BRANCH_LOWERING
P7_HEAD=b118917ec5a5284899d27b1838712b2e04364caf
P7_MERGE=631b51e70562a33183ac14d0be5bbe2ddd140779
ORIGIN_MAIN=631b51e70562a33183ac14d0be5bbe2ddd140779
P7_LINUX_FULL_SUITE_SOURCE=CI_SHARDED_EQUIVALENT
P7_LINUX_FULL_SUITE_EXIT=0
P7_WINDOWS_FULL_SUITE_EXIT=1_PLATFORM_LIMITATION
P7_CI=PASS
P8_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
```

## Current P8.2 checkpoint

P8.2 `PRESERVED_POSSIBILITIES_COLLAPSE_POINTS_V1` completed as a negative
research result. The containment publication is at `d852a611`, the production
anchor remains `631b51e70562a33183ac14d0be5bbe2ddd140779`, and repository-level
GitHub Actions are disabled. No new Actions run occurred after publication.

The possibility-set notation is retained as a research ledger, not as a
compiler abstraction. The seven tracked families and their concrete witnesses
are in `reconciliations/P8_2_PRESERVED_POSSIBILITIES_20260813.md`. The only
proven conditional collapse is the already-shipped P7 `TCMP->TBR3` case. The
strongest unresolved family is initialization/memory-state materialization,
but P8.1 observer and failure evidence prevents a path-complete promotion.

```text
P8_2_STATUS=COMPLETE_NO_VALID_TARGET_YET
P8_SELECTION=NO_VALID_TARGET_YET
P8_STARTED=NO
PRODUCTION_CODE_CHANGED=NO
P9_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
```

The next research step, if authorized in a later campaign, is one bounded
path-complete observer-aware attribution experiment. Do not start production
P8 or P9 from this checkpoint.

The production change is limited to liveness-gated direct lowering of an
adjacent `TCMP`/`TBR3` pair. Keep successor-observer fallback, instruction
limits, initialization checks, f64 unordered behavior, ABI, reference, and
memory obligations intact. Do not start P8 or issue shutdown. Read the external
P7 final report and `S3-ZK-0049` before proposing another target.

## Authoritative current checkpoint: P8.3 closed without a production target

P8.3 performed the required bounded path-complete memory-state necessity
experiment on `631b51e70562a33183ac14d0be5bbe2ddd140779`.

```text
P8_3_STATUS=COMPLETE_NO_VALID_TARGET_YET
P8_SELECTION=NO_VALID_TARGET_YET
P8_STARTED=NO
PRODUCTION_CODE_CHANGED=NO
FULL_SUITE_RUN=NO
P9_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
```

The largest bounded accidental subclass was a definite non-address-taken
`REGISTER_INIT_CHECK` family with 1660 dynamic events in 11 workloads. It is
emulator-only, has no measured native effect, and cannot replace the public
runtime safety check until proof-bearing Assembly transport and exact fallback
exist. TADDR remains unsupported by the existing emulator. Read
`research-lab/reconciliations/P8_3_MEMORY_STATE_NECESSITY_20260813.md`,
`S3-EXP-0030`, and `S3-ZK-0055` before any future campaign. Do not start P9 or
issue shutdown.

## Authoritative P8 final closure - 2026-08-14

The previous P8.3 negative checkpoint was superseded by the final P8 promotion.
P8 is merged and must not be restarted:

```text
CURRENT_ORIGIN_MAIN=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
P8_NAME=P8_PROOF_GUIDED_NATIVE_INIT_CHECK_ELISION
P8_BASE=631b51e70562a33183ac14d0be5bbe2ddd140779
P8_IMPLEMENTATION_HEAD=87eb49cd19a78570f07d66ce7982650c8b422210
P8_PR=178
P8_MERGE=5dd6844607ba3a2d5830ed836fb9026eed86d0fb
P8_STATUS=COMPLETE_MERGED
P8_FULL_SUITE_HEAD=87eb49cd19a78570f07d66ce7982650c8b422210
P8_FULL_SUITE_EXIT=0
P8_ACTIONS_ENABLED=NO
P8_NEW_ACTIONS_RUNS=0
P9_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
REBOOT_EXECUTED=NO
```

The selected implementation is conservative native recomputation from
validated CFG/use-def facts. It does not add public proof metadata. P8.3's
416 safe static sites and 1660 dynamic events matched exactly; 402 sites and
1558 events were native-consumable. All 24 Linux O0/O1 pairs preserved
semantics. Structural totals changed checks 550->148, instructions
20903->20099, branches 4746->4344 and text 107709->102646; loads/stores stayed
10175. Runtime and compile-time measurements are unavailable/not-comparable.

Read `research-lab/HANDOFF.md`, `STATE.json`,
`reconciliations/P8_FINAL_PROOF_GUIDED_INIT_ELISION_20260814.md`,
`experiments/S3-EXP-0031-p8-final-proof-guided-init-elision.md`, and
`zettelkasten/notes/S3-ZK-0056.md` before any future work. P9 remains
unauthorized; only an explicitly requested read-only readiness audit is
allowed.

## P9 selection checkpoint

P9 selection research is now closed as `NO_VALID_TARGET_YET`. Do not start
production P9 from this checkpoint. The validated sidecar model covered 15
workloads and counted 143151 O1 modelled native dynamic x86 executions. The
5431 observed stack-resident frame-value events were exactly
3.793895956018% of that model; they do not establish spills or a removable
family. Direct indexed addressing falsified the current fixed-array base
reload hypothesis. Register allocation is not promoted automatically.

The strongest candidate to carry forward is the bounds-validity contract
surface. The next smallest research experiment is proof-bearing loop-carried
TLOAD/TSTORE bounds and validity sharing or hoisting with checked fallback,
failure-order, initialization, immutability and instruction-limit controls.
No production code, benchmark rerun, Actions execution or shutdown occurred.
Read `research-lab/HANDOFF.md`, `STATE.json`,
`reconciliations/P9_TARGET_SELECTION_CAUSAL_FRAME_20260814.md`,
`experiments/S3-EXP-0032-p9-causal-frame-representation-attribution.md`, and
`zettelkasten/notes/S3-ZK-0057.md` before future work.

## P9.1 bounds/validity checkpoint

P9.1 is closed as `NO_VALID_TARGET_YET`. The P9 dynamic model reproduced
exactly at 289500 across 15 workloads. Explicit safety realization was 65224
modelled dynamic x86 lines; bounds were 17464 and memory initialization 6660.
The minimum local-constant, success-edge, loop and same-object reuse models
found zero proven eligible sites. `AVOIDABLE_DYNAMIC=0`.

Do not start production P9. Register initialization remains P8 territory;
slices were not silently treated as fixed arrays. The next discriminating
question is proof-bearing loop-carried object/index/length identity through
the Assembly contract with all invalidators closed. No production code,
benchmark rerun, Actions run or shutdown occurred. Read
`research-lab/HANDOFF.md`, `STATE.json`,
`reconciliations/P9_1_BOUNDS_VALIDITY_CONTRACT_ATTRIBUTION_20260814.md`,
`experiments/S3-EXP-0033-p9-1-bounds-validity-contract-attribution.md`, and
`zettelkasten/notes/S3-ZK-0058.md` before future work.
