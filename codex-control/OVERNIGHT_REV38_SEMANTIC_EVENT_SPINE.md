# OVERNIGHT REV38 — SEMANTIC EVENT SPINE

Revision 38 supersedes Rev37 for the current Stage1 streaming campaign.

## Current evidence

- Streaming multi-pass architecture: PASS_FRAME_SAFE.
- Full-resident banking: REJECTED_NATIVE_FRAME.
- Reported canonical streaming frame: 82781 / 131072 logical trits.
- Dedicated bounded native V replay writer/probe exists and passed a narrow native fixture.
- Exact observed fixture record: `V 0 0 3 2 32 1 0 -1`.
- Native canonical V stream is still blocked because the canonical Stage1 does not yet preserve/reconstruct the full semantic fields required by S3IR2 V records.
- S1.3 and later lanes are NOT_STARTED.
- `S3_STAGE1_EMITTER_BLOCKED` remains expected and is not the current terminal blocker.

## Architectural diagnosis

The Rev37 writer proved output mechanics. The missing layer is now semantic provenance, not serialization.

S3IR2 V records require:

```text
value_id function_id kind type_code anchor_start anchor_length mutable storage_id
```

Do not solve this by storing the complete V lane or by reopening full-resident banking.

Instead implement a bounded semantic event spine/replay source that preserves or deterministically reconstructs the required fields at the point semantic values/registers are created during parsing/lowering.

The hosted semantic reference assigns logical value IDs module-monotonically by function order and register-index order. Local/loop source bindings are appended by the S3IR2 stream contract after hosted IR values. Physical storage is not semantic identity.

## Current atomic task

```text
AUDIT_MISSING_V_FIELDS_AND_IMPLEMENT_BOUNDED_REGISTER_SEMANTIC_EVENT_RECONSTRUCTION_FEEDING_NATIVE_V_REPLAY
```

### Step A — missing-field matrix

For parameter, constant, instruction_result and local_binding, report each V field as one of:

```text
AVAILABLE_DIRECTLY
RECONSTRUCTABLE_DETERMINISTICALLY
MISSING_REQUIRES_NARROW_METADATA_PRESERVATION
NOT_APPLICABLE
```

Do not call a field unavailable until the canonical parser/lowering/source tables and the recovered expression-lowering candidate have been inspected.

### Step B — provenance at value/register creation

Prefer preserving/reconstructing minimal semantic metadata when a value/register is created rather than attempting to recover it from lossy packed IR later.

Allowed bounded state includes function bases/counts, parameter maps, current expression value IDs, current semantic event fields, and small fixed tables bounded independently of total module values.

Forbidden state includes arrays/banks proportional to total V/I/O/R records.

### Step C — replay order

Reproduce exactly the pinned oracle order for the exact same source SHA and provenance.

Do not hardcode historical record counts. Every canonical source edit requires rerunning the hosted oracle against that exact source.

### Step D — native equality

First prove fixtures for parameter, constant, expression result, local, mutable local, multiple functions, and logical IDs crossing 365. Then prove canonical hosted/native V equality for count, every field, order and deterministic stream SHA.

Only then may S1.2 canonical completeness become PASS.

## Autonomous continuation

If S1.2 becomes PASS, commit/push normally and continue autonomously through:

```text
S1.3 streamed def/use
S1.4 calls
S1.5 terminators
S1.6 canonical serialization
S1.7 general emitter
Stage1
SELF_EMIT
Stage2
Stage3
fixed point
authorized correctness
benchmark last
```

Every previous gate must PASS first.

## Locks

- No full-resident semantic IR.
- No single S3 memory object >365 elements.
- Logical ValueId remains i64 and is not a storage slot.
- Native logical frame must remain <=131072; do not raise the limit.
- No PR merge.
- No force push / force-with-lease.
- No history rewrite.
- No destructive reset/restore/clean of evidence worktrees.
- Missing evidence is NOT_PROVABLE/NOT_RUN, never PASS.
- Hosted oracle is reference evidence only.

## Terminal-state rule

`IR current lacks semantic information` is NOT automatically terminal while the missing fields can be deterministically reconstructed from source/lowering or narrowly preserved at value creation without violating bounded-memory and S3IR2 contracts.

A terminal blocker requires an explicit per-field impossibility proof after bounded reconstruction/preservation options are exhausted.

## Shutdown

Windows shutdown remains authorized only after the final report is saved and a TRUE terminal state is reached: maximum safely authorized completion or a fully documented blocker with no remaining safe autonomous repair.

Before shutdown preserve evidence, finish intended validated commits/pushes, confirm no build/test/oracle/git/file-write processes remain, and record final branch/HEAD/remote/divergence. Reboot, suspend and hibernate remain unauthorized.
