# Codex live control plane — Stage1 semantic lowering v2

This directory is an out-of-band instruction channel for the Codex work on PR #268.

## Absolute rule

The control branch is **read-only from the implementation worktree**.

Never merge, rebase, cherry-pick, or checkout this branch over the active PR #268 worktree. Read it with `git fetch` + `git show` only.

Control branch:

```text
control/codex-stage1-semantic-v2-20260827
```

Implementation branch:

```text
feature/actual-stage1-compiler-seed-20260824
```

Semantic handoff branch / PR:

```text
parallel/pr268-semantic-lowering-v1-20260827
PR #270
```

## Mandatory control check

At process start, before every new stage, before every implementation commit, and before any canonical Stage1 mutation:

```bash
CONTROL_BRANCH=control/codex-stage1-semantic-v2-20260827
git fetch origin "$CONTROL_BRANCH"
CONTROL_REF="origin/$CONTROL_BRANCH"
git show "$CONTROL_REF:codex-control/CURRENT.json"
git show "$CONTROL_REF:codex-control/OVERRIDES.md"
```

Then read the stage file named by `active_stage_file` when the control revision changed, or the next stage file in the sequence when automatic advancement remains allowed and the revision did not change.

Do **not** use `git checkout $CONTROL_BRANCH` in the implementation worktree.

## Revision protocol

Remember the last observed `control_revision`.

- Same revision: continue the already-approved stage sequence.
- Higher revision: stop before beginning the next irreversible action, re-read `CURRENT.json`, `OVERRIDES.md`, and the newly selected stage file, then adapt the plan.
- `emergency_stop=true`: preserve worktree/evidence and stop development immediately after the current atomic command.
- `pause_after_current_stage=true`: finish the current stage evidence, then stop before the next stage.
- Any `*_authorized=false` gate is binding even if earlier stages pass.

Every checkpoint/report must include:

```text
CONTROL_BRANCH=
CONTROL_REVISION=
CONTROL_ACTIVE_STAGE=
CONTROL_OVERRIDE_APPLIED=YES/NO
```

## Instruction precedence inside this control plane

1. `CURRENT.json` safety/authorization booleans and emergency controls.
2. `OVERRIDES.md` current revision directives.
3. The selected stage file.
4. `MEGAPROMPT_STAGE1_SEMANTIC_V2.md` global mission and invariants.
5. Older historical reports/prototypes.

S3IR2 v2 itself is frozen unless `CURRENT.json` and `OVERRIDES.md` explicitly authorize a protocol revision.

## Updating the path later

The user can ask ChatGPT to modify this branch. A control update should:

1. increment `control_revision`;
2. update `active_stage` / `active_stage_file` if the route changes;
3. put the concrete change in `OVERRIDES.md` or a new stage file;
4. leave implementation code untouched.

Because Codex fetches this branch at each stage boundary, new guidance becomes visible without merging anything into PR #268.
