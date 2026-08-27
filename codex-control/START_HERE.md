# START HERE — Codex live Stage1 control

From the active PR #268 worktree, do not checkout this branch.

Minimum control refresh:

```bash
CONTROL_BRANCH=control/codex-stage1-semantic-v2-20260827
git fetch origin "$CONTROL_BRANCH"
CONTROL_REF="origin/$CONTROL_BRANCH"

git show "$CONTROL_REF:codex-control/CURRENT.json"
git show "$CONTROL_REF:codex-control/OVERRIDES.md"
```

If `CURRENT.json` exposes a stage-specific command-card file, read that next and use it as the short operational path for the current atomic task. For the current Stage05 campaign:

```bash
git show "$CONTROL_REF:codex-control/STAGE05_COMMAND_CARD.md"
```

Only open the longer stage/oracle/plan files when the command card or a new failure points to them.

Before each new stage and each important implementation commit, fetch/read `CURRENT.json` and `OVERRIDES.md` again. If the revision changed, newer control instructions take precedence before continuing.

Never merge/check out/cherry-pick the control branch into PR #268.
