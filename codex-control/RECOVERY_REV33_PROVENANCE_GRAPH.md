# Recovery revision 33 — provenance graph before reapplication

Revision 32 completed clean-worktree creation and coarse classification.

## Confirmed state

```text
DIRTY_WORKTREE=C:\Users\samue\Downloads\S3\S3-actual-stage1-compiler-seed-20260824
CLEAN_WORKTREE=C:\Users\samue\Downloads\S3\S3-PR268-Clean-Rev32
HEAD=d67da9ea7dc8b83b0b80adb681011717eebec616
LOCAL_REMOTE_LEFT_RIGHT=0 0
DIRTY_TRACKED_MODIFIED=36
DIRTY_UNTRACKED=454
CLEAN_WORKTREE_STATUS_EMPTY=YES
```

Revision-32 classification reported:

```text
KEEP_STAGE1_CORE=28
QUARANTINE_OLD_COMPACTION_CAPACITY=366
QUARANTINE_HISTORICAL_REPORTS=66
REGENERABLE_ARTIFACTS=1
UNKNOWN_REVIEW_REQUIRED=2
UNKNOWN=scratch_host_probe_stage4.py;scratch_test_eq_chain.py
```

High-value preserved artifacts:

```text
selfhost/compiler/s3c_stage1.s3
  sha256=739dc6ac16c2c79a4f3bff0b7ca2f40324171b3ad155f7a6265747d441cb5758
  classification=Stage03-lineage source

.artifacts/s3c_stage1_expression_lowering_v2.s3
  sha256=ff047a880b871d6428e2f33198db09d9b5c416b940df8bfe4d96867031439858

selfhost/compiler/stage1_semantic_stream_v2.s3
  sha256=b2ee279dbb11358a0c5b9774e08e9217f4c904a9bb39825a71ad8362362e4d5c
```

## Purpose of revision 33

Do not reapply files yet.

Build a read-only provenance/dependency graph for all KEEP and UNKNOWN items sufficient to answer:

1. Which files belong to the confirmed Stage03/pass1 lineage?
2. Which files are later expression-lowering work?
3. Which files are later call-dataflow/Stage05 work?
4. Which files are hosted oracle/conformance only and are not native Stage1 implementation evidence?
5. Which files are supporting tests/tools versus implementation sources?
6. Do any KEEP files depend on quarantined compaction/capacity work?
7. What exactly are `scratch_host_probe_stage4.py` and `scratch_test_eq_chain.py`?
8. What is the highest semantic checkpoint supported by concrete local artifacts, without executing tests/builds?
9. What is the minimal ordered file set that would need to be reapplied to a clean worktree for the next validation cycle?

## Evidence sources

Use read-only inspection of:

- dirty worktree contents and diffs;
- clean worktree at d67da9e;
- revision-31 recovery package manifests/patch;
- local reports/checkpoints already present;
- git history and blame/log for tracked files;
- frozen semantic handoff PR #270 / c12e45d only as an oracle reference, not as proof of native Stage1 completion.

Do not run tests, builds, compiler probes, self-emit, or generated candidates.

## Required per-file record

For each KEEP and UNKNOWN source/test/tool relevant to Stage1 resume, record:

```text
PATH=
TRACKED_STATE=
SHA256=
BYTES=
DIFFERS_FROM_CLEAN_HEAD=
ROLE=IMPLEMENTATION|TEST|TOOL|ORACLE|REPORT|SCRATCH
SEMANTIC_LANE=PASS1_BINDINGS|EXPRESSION_LOWERING|CALL_DATAFLOW|TERMINATORS|SERIALIZATION|GENERAL_EMITTER|MULTI_LANE|NONE|UNKNOWN
PROVENANCE_EVIDENCE=
DEPENDS_ON=
DEPENDENCY_ON_QUARANTINED_WORK=YES|NO|UNKNOWN
NATIVE_STAGE1_EVIDENCE=YES|NO|UNKNOWN
HOSTED_ORACLE_ONLY=YES|NO
REAPPLY_CANDIDATE=YES|NO|UNKNOWN
```

## Unknown files

Inspect both unknown files fully, but do not execute them:

```text
scratch_host_probe_stage4.py
scratch_test_eq_chain.py
```

Classify each as one of:

```text
KEEP_SUPPORTING_TEST_OR_TOOL
QUARANTINE_HISTORICAL
REGENERABLE
UNKNOWN_REVIEW_REQUIRED
```

If uncertain, remain UNKNOWN.

## Highest supported semantic checkpoint

Report conservatively using exactly one of:

```text
CONFIRMED_STAGE03_PASS1
EXPRESSION_LOWERING_CANDIDATE_PRESENT_NOT_VALIDATED_IN_CURRENT_PROVENANCE
EXPRESSION_LOWERING_PREVIOUSLY_VALIDATED_EVIDENCE_FOUND
CALL_DATAFLOW_CANDIDATE_PRESENT_NOT_VALIDATED_IN_CURRENT_PROVENANCE
CALL_DATAFLOW_PREVIOUSLY_VALIDATED_EVIDENCE_FOUND
HIGHER_CHECKPOINT_NOT_PROVABLE
```

Do not claim a PASS from file presence alone.

A historical report may support `PREVIOUSLY_VALIDATED_EVIDENCE_FOUND` only if it contains concrete command/result/hash linkage to the exact candidate being classified.

## Minimal reapplication plan

Produce an ordered plan only; do not execute it.

Example shape:

```text
REAPPLY_WAVE_1=confirmed Stage03/native foundation
REAPPLY_WAVE_2=expression lowering candidate + exact dependencies
REAPPLY_WAVE_3=call-dataflow candidate + exact dependencies
REAPPLY_WAVE_4=oracle/conformance tests/tools if needed for validation
```

Each wave must list exact paths and why they belong there.

If causal ordering cannot be proven, say so and stop at the last provable wave.

## Outputs

Write outside both worktrees, preferably into the existing recovery package:

```text
rev33-provenance-graph.txt
rev33-file-records.txt
rev33-unknown-resolution.txt
rev33-reapply-plan.txt
```

## Forbidden

No source edits in either worktree.
No patch/copy application.
No tests/builds/probes.
No generated-artifact execution or regeneration.
No commit/push/pull/rebase/merge.
No reset/restore/checkout/clean.
No deletion/cleanup.
No canonical mutation.
No SELF_EMIT, Stage2, Stage3, T4, benchmark, or merge.
