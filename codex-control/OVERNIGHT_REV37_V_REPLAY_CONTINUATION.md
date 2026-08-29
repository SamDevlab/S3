# S3 Rev37 — Canonical V Replay Continuation

Revision 37 corrects the premature Rev36 terminal classification.

## Current evidence

- Streaming multi-pass architecture: PASS_FRAME_SAFE.
- Full-resident banking: REJECTED_NATIVE_FRAME.
- Native build: PASS.
- Reported frame: 82781 / 131072 logical trits.
- Hosted canonical S3IR2 V stream: 38724 records for the last tested source/provenance snapshot.
- Native canonical V stream: 0 records.
- `S3_STAGE1_EMITTER_BLOCKED` remains expected before S1.2/S1.3/S1.6/S1.7 closure.

## Critical correction

`S3_STAGE1_EMITTER_BLOCKED` is NOT a terminal blocker while a narrower authorized path exists to observe/replay canonical semantic records.

The current first blocker is:

`S1_2_CANONICAL_STREAM_COMPLETENESS`

The current required implementation task is:

`IMPLEMENT_DEDICATED_BOUNDED_NATIVE_V_REPLAY_OBSERVATION_PATH_INDEPENDENT_OF_GENERAL_EMITTER`

## Required architecture

Implement a narrow native/Stage1 observation path that emits or captures canonical `V` records sequentially without requiring the general emitter and without storing the complete V lane resident in memory.

The path may reuse existing Stage1 byte-output/probe/runtime mechanisms. It must not masquerade as the final general emitter.

Logical semantic identity remains independent from physical storage. Value IDs remain module-monotonic i64 according to the frozen S3IR2 oracle.

No full-resident semantic banks. No array/memory object above 365 elements. Keep native frame <=131072 logical trits.

## Autonomous execution rule

Do not stop merely because the general emitter is blocked. Continue autonomous narrow repairs/design until one of these occurs:

1. Exact native/hosted canonical V equality passes, then advance through gated S1.3, S1.4, S1.5, S1.6, S1.7, Stage1, real SELF_EMIT, Stage2, Stage3, fixed point, correctness, benchmark last; or
2. A new terminal blocker is proven after exhausting safe bounded alternatives and is not merely the known general-emitter gap.

For S1.2, prove exact same-source hosted/native V count, IDs, function IDs, kind, type code, anchors, mutability, storage_id, order, cross-365 IDs, determinism, native build and frame gate.

Any source edit requires rerunning the exact oracle on the exact new source SHA. Pin oracle/ref/blob provenance.

## Git safety

Validated commits and normal push are authorized. PR merge, force push, history rewrite, destructive reset/restore/clean and evidence deletion remain forbidden.

## Shutdown

Windows shutdown remains authorized only after a true terminal campaign state: maximum safely reachable authorized completion or a newly proven terminal blocker with no remaining safe autonomous repair. The known `S3_STAGE1_EMITTER_BLOCKED` state by itself is NOT sufficient for terminal shutdown while S1.2 replay work remains possible.

Before shutdown, save/flush the final report, preserve dirty evidence, finish intended validated commit/push, verify no build/test/oracle/git/file-write process remains active, then use the authorized shutdown command from Rev36. Reboot/suspend/hibernate remain forbidden.
