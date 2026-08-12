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

12. Do NOT start or define P5 from the post-P4 recommendation alone.
    First quantitatively separate metadata-state staging, SSA/phi/loop staging,
    true RA spills, call/ABI traffic and mandatory reference/address identity.

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
```
