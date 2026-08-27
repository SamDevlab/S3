# Stage 01 — Precheck and selective handoff import

## Goal

Preserve the current PR #268 worktree, load the live control plane, and make the authoritative S3IR2 v2 handoff available locally without merging PR #270.

## Entry gate

- Control plane fetched and revision acknowledged.
- Current implementation branch/HEAD/status recorded.
- One SSH/Linux health check may be performed if native work will be needed in this run.

## Required actions

1. Record:
   - branch;
   - HEAD;
   - `git status --short`;
   - canonical `s3c_stage1.s3` SHA256;
   - existing local modifications/untracked evidence.
2. Fetch `parallel/pr268-semantic-lowering-v1-20260827`.
3. Read the authoritative v2 files listed in the megaprompt.
4. If those files are absent locally, selectively import/copy only the v2 handoff files after checking for path conflicts. Do not merge PR #270.
5. Do not change compiler semantics in this stage.

## Forbidden

- reset/clean;
- canonical Stage1 overwrite;
- repeated health-check loop;
- Stage2/T4;
- protocol redesign.

## Exit evidence

```text
CONTROL_REVISION=
IMPLEMENTATION_BRANCH=
HEAD=
CANONICAL_SOURCE_SHA256=
WORKTREE_PRESERVED=YES
HANDOFF_V2_READ=YES
PR270_MERGED=NO
```

Proceed automatically to Stage 02 if the control revision is unchanged and automatic advancement remains allowed.
