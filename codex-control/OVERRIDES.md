# Live overrides

CONTROL_REVISION: 33

## PROVENANCE GRAPH ONLY — NO REAPPLICATION

Revision 32 completed clean detached worktree creation and coarse classification.

Confirmed:

```text
DIRTY_WORKTREE=C:\Users\samue\Downloads\S3\S3-actual-stage1-compiler-seed-20260824
CLEAN_WORKTREE=C:\Users\samue\Downloads\S3\S3-PR268-Clean-Rev32
HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
CLEAN_STATUS_EMPTY=YES
KEEP_STAGE1_CORE=28
QUARANTINE_OLD_COMPACTION_CAPACITY=366
QUARANTINE_HISTORICAL_REPORTS=66
REGENERABLE=1
UNKNOWN=2
```

Unknown files:

```text
scratch_host_probe_stage4.py
scratch_test_eq_chain.py
```

## Authorized now

Read `codex-control/RECOVERY_REV33_PROVENANCE_GRAPH.md`.

Perform read-only provenance/dependency analysis only:

1. inspect each KEEP/UNKNOWN relevant source/test/tool;
2. map each to Stage03/pass1, expression lowering, call dataflow, terminators/serialization/emitter, oracle/conformance, or unknown;
3. distinguish native Stage1 implementation evidence from hosted oracle/reference support;
4. resolve the two scratch unknowns without executing them;
5. check whether KEEP items depend on quarantined compaction/capacity work;
6. determine the highest semantic checkpoint supported by exact artifact-linked evidence;
7. produce a minimal ordered reapplication plan;
8. write Rev33 outputs outside both worktrees;
9. STOP.

## Evidence rule

File presence is not PASS evidence.
Historical PASS can only be carried forward when an existing report/checkpoint concretely links command/result/hash to the exact artifact under review.
Missing linkage = NOT_PROVABLE.

## Forbidden

No source mutation in either worktree.
No patch/copy reapplication.
No tests/builds/probes.
No artifact regeneration.
No cleanup/deletion.
No commit/push/pull/rebase/merge.
No reset/restore/checkout/clean.
No canonical promotion/mutation.
No SELF_EMIT/Stage2/Stage3/T4/benchmark/merge.

## Authorization boundary

Read-only provenance = YES
External provenance reports = YES
Reapply work = NO
Build/test = NO
Cleanup = NO
Commit/push = NO
Semantic resume = NOT YET
