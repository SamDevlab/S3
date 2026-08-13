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
