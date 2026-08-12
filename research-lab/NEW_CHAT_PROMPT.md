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
   - research-lab/zettelkasten/INDEX.md
   - research-lab/sources/README.md
   - research-lab/hypotheses/P4_GLOBAL_VALUE_RESIDENCY.md
   - research-lab/hypotheses/TERNARY_VIRTUALIZATION.md
   - research-lab/experiments/README.md
   - research-lab/prototypes/README.md

2. Treat them as durable context for prior decisions, performance history, literature bridges,
   Zettelkasten conventions, research hypotheses, experiments, testing policy and safety constraints.

3. Inspect CURRENT origin/main independently. SHAs in the handoff are historical anchors only.

4. Never merge research/zettelkasten-lab-20260812 directly to main.
   Proven mechanisms must be ported to a fresh production branch from current main.

5. Preserve the methodology:
   - one Zettel = one atomic idea;
   - distinguish source-established fact vs S3 inference vs measurement;
   - negative results/counterexamples are permanent knowledge;
   - mathematical models compete by evidence;
   - exact expensive algorithms may be bounded research oracles;
   - do not assume RA is the bottleneck without true-spill attribution;
   - do not assume S3 trit semantics equal any named many-valued logic without exact truth-table comparison;
   - treat quantum/DNA ternary literature as representation/architecture inspiration, not as a required backend;
   - information-theoretic quantities require a defined probability model; otherwise use deterministic information/precision measures;
   - focused tests during implementation, full suite only for a coherent production candidate.

6. Current research has three connected flexibility dimensions:
   LOCATION_FLEXIBILITY
   REPRESENTATION_FLEXIBILITY
   PROOF_KNOWLEDGE_FLEXIBILITY

7. Important unresolved experiments include:
   - RA OFF vs RA ON causal control;
   - >=50-value location/frame attribution;
   - compiler information-loss boundary audit;
   - exact current S3 trit semantics/lowering map;
   - ternary primitive-basis exact oracle;
   - ternary representation conversion graph;
   - ternary/finite-state minimization;
   - min-cut/exact-oracle and Lagrangian capacity experiments.

8. If I provide new FINAL_P*_REPORT.md or *_RESULT.json files, reconcile them with STATE.json and update HANDOFF.md/STATE.json before selecting the next production milestone.

Start by returning:
CURRENT_ORIGIN_MAIN=
RESEARCH_BRANCH_HEAD=
DURABLE_CONTEXT_LOADED=YES/NO
PRODUCTION_STATE_FROM_HANDOFF=
GLOBAL_VALUE_RESEARCH_QUESTION=
TERNARY_RESEARCH_QUESTION=
INFORMATION_PRESERVATION_QUESTION=
NEXT_UNRESOLVED_EXPERIMENTS=
P4_PRODUCTION_TARGET_SELECTED=YES/NO

Then continue from evidence, not assumptions.
```
