# Live overrides

CONTROL_REVISION: 38

## CURRENT TASK — SEMANTIC EVENT SPINE FOR CANONICAL V REPLAY

Read first:

```text
codex-control/OVERNIGHT_REV38_SEMANTIC_EVENT_SPINE.md
codex-control/CURRENT.json
```

Implementation branch:

```text
recovery/pr268-stage1-streaming-values-20260828
```

## Current evidence

```text
S1.1 Foundation = PASS
S1.2 mechanism = PASS
Streaming architecture/native frame gate = PASS
Native bounded V writer = PASS_NARROW_FIXTURE
Full-resident banking = REJECTED_NATIVE_FRAME
Canonical native V replay = BLOCKED by missing/reconstructed semantic fields
S1.3 = NOT_STARTED
```

The Rev37 writer proved native output mechanics. The current first blocker is now the semantic event source feeding that writer.

## Current atomic task

```text
AUDIT_MISSING_V_FIELDS_AND_IMPLEMENT_BOUNDED_REGISTER_SEMANTIC_EVENT_RECONSTRUCTION_FEEDING_NATIVE_V_REPLAY
```

For every V field and value kind, classify whether it is directly available, deterministically reconstructable, or requires narrow metadata preservation at parsing/lowering/value creation.

Do not treat lossy packed IR as the only possible source. Prefer source/lowering replay or semantic metadata captured at register/value creation.

## Required architecture

- STREAMING_MULTI_PASS remains authoritative.
- No full-resident V/I/O/R tables or proportional banks.
- Logical ValueId remains module-monotonic i64 and independent from storage.
- No S3 object >365 elements.
- Native frame remains <=131072 logical trits; do not raise the limit.
- Exact hosted/native comparison must use identical source SHA and pinned oracle provenance.
- Hosted oracle is reference only, never native PASS.

## Non-terminal states

The following alone are explicitly NOT terminal:

```text
S3_STAGE1_EMITTER_BLOCKED
current packed IR lacks a required V field
canonical V replay currently emits 0 records
```

They become terminal only after a documented bounded reconstruction/preservation audit proves no safe S3IR2-compatible path remains.

## Autonomous route

When exact canonical V replay passes, commit/push normally and continue automatically through S1.3, S1.4, S1.5, S1.6, S1.7, Stage1, real SELF_EMIT, real Stage2, real Stage3, fixed point, correctness and benchmark last, with every previous gate concretely PASS.

## Git locks

Allowed: source edits, focused tests, hosted oracle, native builds/probes, preservation patches, clean recovery worktrees, validated commits, normal push/push -u and tracker updates.

Forbidden: PR merge, force push, force-with-lease, history rewrite, destructive reset/restore/clean of evidence worktrees, evidence deletion.

## Shutdown

Windows shutdown remains authorized only after a TRUE terminal campaign state and final report/evidence preservation. Before shutdown ensure no build/test/oracle/git/file-write process remains. Reboot, suspend and hibernate remain unauthorized.

## Evidence policy

```text
missing evidence = NOT_PROVABLE / NOT_RUN
PASS = exact concrete evidence only
```
