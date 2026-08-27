# Codex + ChatGPT paired engineering mode

Purpose: make Stage1 self-hosting work operate as one coordinated engineering loop rather than two mostly independent tracks.

This mode does not change stage scope or authorization. Codex owns implementation in the PR #268 candidate/worktree. ChatGPT owns oracle interpretation, control-plane guidance, S3-Benchmarks evidence/triage, and next-step narrowing. Neither side may silently claim evidence owned by the other.

## Ownership

### Codex owns

- candidate implementation in PR #268 worktree;
- local generator/candidate repairs;
- Stage0 checks;
- Linux native builds/runs;
- preserving exact stdout/stderr/exit status;
- candidate/source/binary hashes;
- the first observed failing fixture/mismatch.

### ChatGPT owns

- control-plane revisions and stage authorization;
- semantic oracle / strict-conformance interpretation;
- mapping verifier failures to S1/S2/S3/S4/S5 slices;
- S3-Benchmarks fixtures, triage and evidence contracts;
- regression/campaign/history analysis;
- deciding whether a reported result is enough to advance the control plane.

## Paired loop

For each meaningful implementation cycle:

1. Codex finishes the currently running atomic command; do not duplicate it.
2. Codex reports one compact `PAIRING_CHECKPOINT` block.
3. ChatGPT consumes that checkpoint together with the live control revision and oracle/benchmark contracts.
4. ChatGPT returns one of:
   - `CONTINUE_CURRENT_SLICE` with the smallest next proof;
   - `FIX_FIRST_BLOCKER` with the exact owning semantic lane;
   - `STAGE_EXIT_READY_FOR_REVIEW`;
   - `CONTROL_UPDATE_REQUIRED`.
5. Codex applies only the authorized slice and repeats.

Do not broaden implementation based on multiple speculative hypotheses. The first real mismatch remains the unit of work.

## Required PAIRING_CHECKPOINT

Use this exact key/value shape after a meaningful gate, native matrix, strict-conformance run, or before an implementation commit:

```text
PAIRING_CHECKPOINT_BEGIN
CONTROL_REVISION=<integer>
ACTIVE_STAGE=<stage id>
CANDIDATE_GIT_HEAD=<sha or LOCAL_UNCOMMITTED>
CANDIDATE_SOURCE_SHA256=<sha or NOT_RECORDED>
NATIVE_BINARY_SHA256=<sha or NOT_BUILT>
FIXTURE=<name or MATRIX>
COMMAND_CLASS=STAGE0_CHECK/NATIVE_BUILD/NATIVE_RUN/STRICT_CONFORMANCE/FOCUSED_TESTS/CHECKPOINT
EXIT_STATUS=<integer or NOT_APPLICABLE>
STATUS=PASS/FAIL/BLOCKED/RUNNING
Z_MASK=<integer or NOT_APPLICABLE>
STRICT_CONFORMANCE=PASS/FAIL/NOT_RUN
MAPPED_VALUES=<integer or NOT_APPLICABLE>
FIRST_REAL_BLOCKER=<single concise blocker or NONE>
CANONICAL_SOURCE_MUTATED=NO/YES
SELF_EMIT_EXECUTED=NO/YES
STAGE2_CREATED=NO/YES
STAGE3_CREATED=NO/YES
T4_EXECUTED=NO/YES
PAIRING_CHECKPOINT_END
```

Rules:

- never fabricate a missing SHA/status; use `NOT_RECORDED`/`NOT_RUN`;
- if a command is still running, report `RUNNING` only when a checkpoint is explicitly requested; normally let it finish first;
- include exactly one `FIRST_REAL_BLOCKER` when status is FAIL/BLOCKED;
- preserve raw evidence separately; the compact block is an index, not a replacement;
- a PASS checkpoint is not permission to cross a stage boundary unless the live control plane authorizes it.

## Current Stage04 closeout

While Stage04 remains active, the paired loop should focus only on:

- formal Stage04 checkpoint completeness;
- exact candidate/source/binary identities;
- focused tests;
- strict conformance;
- S1/S2 exit evidence;
- `Z 3` for supported Stage04 fixtures and `Z 0` for unsupported fail-closed fixtures.

Do not spend a new cycle re-proving healthy SSH/build infrastructure unless a current failure implicates it.

## Stage transition

When the Stage04 checkpoint satisfies the exit gate, Codex must re-fetch the control branch and report a `PAIRING_CHECKPOINT` with `COMMAND_CLASS=CHECKPOINT`. ChatGPT then evaluates the evidence against S3-Benchmarks/control contracts and, if sufficient, updates the live stage. Codex must not infer Stage05 merely from local PASS text.

## Safety boundary

This mode never grants canonical Stage1 mutation, SELF_EMIT, Stage2, Stage3 or T4. Those remain controlled by their explicit live authorization fields.
