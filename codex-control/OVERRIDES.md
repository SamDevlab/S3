# Live overrides

CONTROL_REVISION: 37

## CURRENT TASK — CANONICAL V REPLAY CONTINUATION

Read first:

```text
codex-control/OVERNIGHT_REV37_V_REPLAY_CONTINUATION.md
codex-control/CURRENT.json
```

Current implementation branch:

```text
recovery/pr268-stage1-streaming-values-20260828
```

Reported implementation HEAD:

```text
1ec76af89992f119865a370488593ad5c85c4c49
```

Last tested canonical source SHA:

```text
44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
```

## Current evidence

```text
S1.1 Foundation = PASS
S1.2 mechanism = PASS
Streaming architecture/native frame gate = PASS
Full-resident banking = REJECTED_NATIVE_FRAME
Streaming frame = 82781 / 131072 trits
Hosted canonical V stream = 38724 for last tested source/provenance snapshot
Native canonical V stream = 0
S1.2 canonical native V stream = BLOCKED
S1.3 Def/Use = NOT_STARTED
```

## Critical correction

`S3_STAGE1_EMITTER_BLOCKED` is expected before later Stage1 lanes close and is NOT a terminal blocker while a dedicated bounded native V replay/observation path remains implementable.

Do not stop merely because the general emitter is blocked.

Current first blocker:

```text
S1_2_CANONICAL_STREAM_COMPLETENESS
```

Current atomic task:

```text
IMPLEMENT_DEDICATED_BOUNDED_NATIVE_V_REPLAY_OBSERVATION_PATH_INDEPENDENT_OF_GENERAL_EMITTER
```

## Autonomous route

Continue autonomously through evidence-gated transitions:

```text
S1.2 exact native V replay
→ S1.3 streamed instruction def/use
→ S1.4 streamed call dataflow
→ S1.5 complete terminators
→ S1.6 canonical S3IR2 serialization
→ S1.7 general emitter
→ Stage1 closure
→ real SELF_EMIT
→ real Stage2
→ Stage2 builds real Stage3
→ fixed point/determinism
→ correctness
→ benchmark LAST
```

Every prior gate must concretely PASS before the next begins.

## V replay requirement

Implement a narrow native/Stage1 observation path that emits or captures canonical `V` records sequentially without invoking the general emitter and without retaining the complete V lane in memory. Reuse existing byte-output/probe/runtime mechanisms when suitable. This observation path is evidence machinery, not the final general emitter.

Prove exact same-source hosted/native equality for V count, IDs, function IDs, kind, type code, anchors, mutability, storage ID, order, cross-365 logical IDs and determinism.

Any source edit requires rerunning the exact hosted oracle on the exact new source SHA with pinned oracle/reference provenance.

## Streaming locks

- Do not return to full-resident semantic IR banking.
- Logical IDs are not storage slots.
- Logical ValueId remains module-monotonic i64 according to S3IR2.
- No single S3 array/memory object >365 elements.
- Keep native frame <=131072 logical trits; never raise the limit to obtain PASS.
- Use bounded streaming/replay with a small fixed number of source passes.
- Hosted oracle is reference evidence only, never native Stage1 proof.

## Repair authority

Capture the first causal failure, apply the narrowest repair, run the smallest proving test and then rerun the gate. Up to three narrow repairs per same cause. Structural redesign is authorized if evidence-backed, bounded, deterministic, fail-closed and S3IR2-compatible.

A known general-emitter gap is not enough to declare a terminal blocker during S1.2 replay work.

## Git/worktree

Allowed: validated commits, normal push/push -u, tracker updates, preservation patches, clean recovery worktrees when needed to preserve evidence.

Forbidden: PR merge, force push/force-with-lease, history rewrite, destructive reset/restore/clean of evidence worktrees, destructive evidence deletion.

## Final shutdown authorization

Windows shutdown remains authorized only after a TRUE terminal campaign state:

- maximum safely reachable authorized completion, or
- a newly proven fully documented blocker with no safe remaining autonomous repair.

The current `S3_STAGE1_EMITTER_BLOCKED` state alone is explicitly NOT terminal while S1.2 native V replay has not been implemented/exhausted.

Before shutdown: save and flush final report; preserve dirty evidence; finish intended validated commit/push; verify no build/test/oracle/git/file-write process remains active; record final branch/HEAD/remote/divergence and maximum gate reached. Then use the shutdown command already authorized by Rev36. Do not reboot, suspend or hibernate.

## Evidence policy

```text
missing evidence = NOT_PROVABLE / NOT_RUN
hosted oracle = NOT native Stage1 proof
PASS = exact concrete evidence only
```

Never fabricate progress.
