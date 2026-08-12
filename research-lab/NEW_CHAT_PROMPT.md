# New Chat Bootstrap Prompt

Copy/paste the block below into a new ChatGPT/Codex conversation when the previous conversation reaches its context limit.

```text
We are continuing the S3 compiler research project.

Production repository:
https://github.com/SamDevlab/S3

Durable research branch:
research/zettelkasten-lab-20260812

Before proposing or implementing anything:

1. Fetch/read these files from that research branch:
   - research-lab/HANDOFF.md
   - research-lab/STATE.json
   - research-lab/RESEARCH_PROTOCOL.md
   - research-lab/zettelkasten/INDEX.md
   - research-lab/hypotheses/P4_GLOBAL_VALUE_RESIDENCY.md
   - research-lab/prototypes/README.md

2. Treat those files as the durable context for prior decisions, performance history,
   Zettelkasten conventions, research hypotheses, testing policy, and safety constraints.

3. Inspect the CURRENT origin/main independently. The SHA stored in the handoff is only
   an historical anchor and production may have advanced.

4. Do not merge research/zettelkasten-lab-20260812 directly to main.
   Proven research ideas must be ported to a fresh production branch from current main.

5. Preserve the methodology:
   - Zettelkasten atomic notes;
   - explicit source vs inference vs measurement;
   - negative results are permanent knowledge;
   - mathematical models compete by evidence;
   - exact expensive methods may be research oracles;
   - do not assume RA is the bottleneck without true-spill attribution;
   - focused tests during implementation, full suite only for a coherent production candidate.

6. If I provide new FINAL_P*_REPORT.md or *_RESULT.json files, reconcile them with
   STATE.json and update the durable research handoff before selecting the next milestone.

Start by returning:
CURRENT_ORIGIN_MAIN=
RESEARCH_BRANCH_HEAD=
DURABLE_CONTEXT_LOADED=YES/NO
PRODUCTION_STATE_FROM_HANDOFF=
RESEARCH_PRIMARY_QUESTION=
NEXT_UNRESOLVED_EXPERIMENTS=

Then continue from evidence, not from assumptions.
```
