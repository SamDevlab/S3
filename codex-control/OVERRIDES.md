# Live overrides

CONTROL_REVISION: 36

## CURRENT TASK — AUTONOMOUS STREAMED BOOTSTRAP

Read first:

```text
codex-control/OVERNIGHT_REV36_STREAMING_AUTONOMY.md
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
S1.2 canonical native V stream = BLOCKED
S1.3 Def/Use = NOT_STARTED
```

Current first blocker:

```text
S1_2_CANONICAL_STREAM_COMPLETENESS
```

Current atomic task:

```text
IMPLEMENT_BOUNDED_LOSSLESS_CANONICAL_V_REPLAY_STREAM_WITH_EXACT_ORACLE_PROVENANCE
```

## Autonomous route

The user explicitly authorizes continuous autonomous technical decisions while away. Do not pause merely to request confirmation for ordinary technical choices that remain inside Rev36 locks.

Proceed only through evidence-gated transitions:

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

Every previous gate must have concrete PASS evidence before the next gate begins.

## Streaming locks

- Do not return to full-resident semantic IR banking.
- Logical IDs are not storage slots.
- Logical ValueId remains module-monotonic `i64` according to S3IR2.
- No single S3 array/memory object >365 elements.
- Keep native frame <=131072 logical trits; never raise the limit to obtain PASS.
- Use bounded streaming/replay with a small fixed number of source passes.
- Any source edit requires rerunning the exact hosted oracle on the exact new source SHA before equality claims.
- Hosted oracle output is architecture/reference evidence, never native Stage1 proof.

## Oracle provenance

Before exact equality claims, record exact source SHA, oracle/ref/blob provenance, semantic-reference provenance, source-binding-reference provenance, bootstrap pipeline HEAD, Python executable/PYTHONPATH and invocation mode. Same source + same provenance must reproduce identical counts and stream hash twice.

## Repair authority

For each concrete blocker, capture evidence, identify first causal failure, apply the narrowest repair, rerun the smallest proving test, then rerun the gate. Up to three narrow repairs for the same cause are allowed. A structural redesign is allowed autonomously if it is evidence-backed, preserves rejected attempts, remains bounded, and does not violate normative language/resource locks.

Stop only on a terminal blocker that cannot be safely attributed/resolved within the authorized architecture, or when a forbidden operation/spec change would be required. Document exact evidence before stopping.

## Git/worktree

Allowed:

```text
validated commits
normal push / push -u
tracker updates
preservation patches
new clean recovery worktree/branch when necessary to preserve dirty evidence
```

Forbidden:

```text
PR merge
force push / force-with-lease
history rewrite
destructive reset/restore/clean of preserved evidence worktrees
destructive evidence deletion
```

## Final shutdown authorization

The user now authorizes shutting down the Windows computer after the campaign reaches a terminal state.

Terminal state means either:

- maximum safely reachable authorized completion, or
- a fully documented blocker with no further safe autonomous repair available.

Before shutdown:

1. write and flush the final report;
2. preserve dirty evidence;
3. finish intended validated commit/push;
4. verify no build, test, oracle, git, or file-write process remains active;
5. record final branch/HEAD/remote/divergence and maximum gate reached.

Then execute:

```text
shutdown.exe /s /t 60 /c "S3 autonomous campaign finished; final report saved"
```

Do not reboot, suspend, or hibernate. Do not escalate privileges if shutdown fails; record the error and leave the host running.

## Evidence policy

```text
missing evidence = NOT_PROVABLE / NOT_RUN
failure without attribution = FAIL / BLOCKED as appropriate
PASS = exact concrete evidence only
```

Never fabricate progress.
