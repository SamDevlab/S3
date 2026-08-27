# START HERE — Codex live Stage1 control

From the active PR #268 worktree, do not checkout this branch.

Run:

```bash
CONTROL_BRANCH=control/codex-stage1-semantic-v2-20260827
git fetch origin "$CONTROL_BRANCH"
CONTROL_REF="origin/$CONTROL_BRANCH"

git show "$CONTROL_REF:codex-control/CURRENT.json"
git show "$CONTROL_REF:codex-control/OVERRIDES.md"
git show "$CONTROL_REF:codex-control/MEGAPROMPT_STAGE1_SEMANTIC_V2.md"
git show "$CONTROL_REF:codex-control/STAGE_SEQUENCE.json"
```

Then begin the stage indicated by `CURRENT.json`.

Before each new stage and each important commit, fetch/read the control files again.

If the revision changed, newer control instructions take precedence before continuing.

Never merge/check out/cherry-pick the control branch into PR #268.
