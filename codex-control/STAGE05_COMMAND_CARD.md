# Codex fast path — recovery/provenance

Read `CURRENT.json`, `OVERRIDES.md`, and `RECOVERY_REV33_PROVENANCE_GRAPH.md` first.

## REVISION 33 — PROVENANCE GRAPH ONLY

Revision 32 completed successfully:

```text
HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
DIRTY_WORKTREE=preserved
CLEAN_DETACHED_WORKTREE=created and empty
KEEP_STAGE1_CORE=28
QUARANTINE_OLD_COMPACTION_CAPACITY=366
QUARANTINE_HISTORICAL_REPORTS=66
REGENERABLE=1
UNKNOWN=2
```

## Do this now

```text
1. inspect KEEP and UNKNOWN items read-only
2. build exact per-file provenance/dependency records
3. resolve scratch_host_probe_stage4.py and scratch_test_eq_chain.py without executing them
4. distinguish native Stage1 implementation from hosted oracle/conformance
5. identify exact artifact-linked historical validation, if any
6. determine highest semantic checkpoint actually provable
7. produce minimal ordered reapplication waves with exact paths
8. write reports outside both worktrees
9. STOP
```

Do not claim PASS from file presence alone.
Do not copy/apply anything to the clean worktree yet.

## Locked

No source mutation.
No patch/copy reapplication.
No cleanup.
No tests/builds/probes.
No commit/push.
No canonical promotion.
No SELF_EMIT/Stage2/Stage3/T4/benchmark/merge.
