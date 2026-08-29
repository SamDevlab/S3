# Live overrides

CONTROL_REVISION: 39

## CURRENT TASK — CONTINUOUS AUTONOMOUS SEMANTIC EVENT SPINE

Read first:

```text
codex-control/OVERNIGHT_REV39_CONTINUOUS_AUTONOMY.md
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
Canonical native V replay = BLOCKED by semantic-event provenance/source
S1.3 = NOT_STARTED
```

## Continuity override

The user explicitly authorizes continuous autonomous technical work while unavailable.

Do not end the campaign while a safe authorized next action exists.

A checkpoint, report, test failure, build failure, oracle mismatch, context compaction, quiet long-running command, transient VM/process failure, dirty preserved worktree, missing packed-IR field, `S3_STAGE1_EMITTER_BLOCKED`, or zero canonical V records is not terminal by itself.

Follow the Rev39 loop continuously:

```text
reconcile
→ identify first causal blocker
→ inspect evidence
→ choose smallest safe bounded repair/design
→ test
→ classify
→ update baton
→ continue
```

Three unsuccessful narrow repairs mean reconsider the approach, not stop the campaign.

## Current atomic task

```text
AUDIT_MISSING_V_FIELDS_AND_IMPLEMENT_BOUNDED_REGISTER_SEMANTIC_EVENT_RECONSTRUCTION_FEEDING_NATIVE_V_REPLAY
```

Prefer bounded source/lowering replay or narrow metadata preservation at semantic value/register creation. Do not reopen full-resident banking.

## AUTONOMOUS_BATON

Maintain:

```text
reports/selfhost/stage1/AUTONOMOUS_BATON_REV39.md
```

Update it before long-running commands and after meaningful checkpoints. After context/session recovery, reread Rev39 + baton, reconcile actual git/process state and resume from the recorded next safe action.

## Architecture locks

- STREAMING_MULTI_PASS remains authoritative.
- No full-resident V/I/O/R tables or proportional banks.
- Logical ValueId remains module-monotonic i64 and independent from storage.
- No S3 object larger than 365 elements.
- Native logical frame remains at or below 131072 logical trits; do not raise it.
- Same-source hosted/native comparison requires pinned oracle provenance.
- Hosted oracle is reference only, never native PASS.
- Missing evidence is NOT_PROVABLE/NOT_RUN, never PASS.

## Automatic route

After exact canonical V equality passes, continue automatically through S1.3, S1.4, S1.5, S1.6, S1.7, Stage1, real SELF_EMIT, real Stage2, real Stage3, fixed point, correctness and benchmark last. Every prior gate must concretely PASS.

## True terminal rule

Stop only after maximum authorized completion or after a documented blocker for which no safe autonomous repair, diagnostic, replay, worktree or implementation path remains within Rev39 authorization.

If a meaningful `NEXT_SAFE_ACTION` exists, the campaign is not terminal.

## Git locks

Allowed: implementation edits, tests, oracle runs, native builds/probes, preservation patches, clean recovery worktrees, coherent validated commits, normal pushes and tracker updates.

Forbidden: PR merge, force push, force-with-lease, history rewrite, destructive reset/restore/clean of evidence worktrees, and evidence deletion.

## End-of-campaign power action

The previously granted end-of-campaign Windows power-off authorization remains valid only after a true terminal state, final evidence preservation and confirmation that no relevant process or write is active. Reboot, suspend and hibernate remain unauthorized.
