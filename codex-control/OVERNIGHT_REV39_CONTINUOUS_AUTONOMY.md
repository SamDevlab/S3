# OVERNIGHT REV39 — CONTINUOUS AUTONOMOUS EXECUTION

Revision 39 supersedes Rev38 for the current Stage1 streaming campaign.

## User intent

The user is unavailable and explicitly authorizes continuous technical autonomy. Do not stop at ordinary blockers, command failures, context compaction, checkpoints, long-running gates, or a single unsuccessful repair while a safe authorized next action remains.

The objective is continuous progress, not periodic final reports.

## Current evidence

- Streaming multi-pass architecture: PASS_FRAME_SAFE.
- Full-resident banking: REJECTED_NATIVE_FRAME.
- Reported canonical streaming frame: 82781 / 131072 logical trits.
- Dedicated bounded native V replay writer: PASS_NARROW_FIXTURE.
- Current first blocker: semantic event source for exact canonical V replay.
- S1.3 and later lanes are not yet authorized until S1.2 exact canonical V equality passes.
- `S3_STAGE1_EMITTER_BLOCKED` is expected before later gates and is NOT terminal here.

## Current atomic task

```text
AUDIT_MISSING_V_FIELDS_AND_IMPLEMENT_BOUNDED_REGISTER_SEMANTIC_EVENT_RECONSTRUCTION_FEEDING_NATIVE_V_REPLAY
```

Continue the Rev38 semantic-event-spine design. Preserve bounded state, deterministic replay, exact S3IR2 semantics and frame safety.

## Mandatory autonomous loop

Repeat this loop until a TRUE terminal state is reached:

```text
1. reconcile branch/worktree/control revision
2. read AUTONOMOUS_BATON
3. identify first unpassed gate / first causal blocker
4. inspect evidence and relevant source
5. choose the smallest safe attributable implementation or repair
6. preserve evidence before architectural changes
7. edit
8. run the smallest proving test
9. if PASS, run the next enclosing gate
10. classify failures exactly
11. update AUTONOMOUS_BATON
12. commit/push coherent validated checkpoints when appropriate
13. immediately continue to the next allowed task
```

Do not wait for user confirmation between loop iterations.

## AUTONOMOUS_BATON

Maintain a resumable checkpoint at:

```text
reports/selfhost/stage1/AUTONOMOUS_BATON_REV39.md
```

Update it before long-running commands, after meaningful discoveries, after each validated checkpoint, and before any response that could terminate the current model/session.

It must contain at least:

```text
CONTROL_REVISION=39
BRANCH=
HEAD=
SOURCE_SHA256=
WORKTREE_STATUS=
CURRENT_GATE=
CURRENT_FIRST_BLOCKER=
LAST_COMPLETED_ACTION=
LAST_TEST_RESULT=
NEXT_SAFE_ACTION=
ACTIVE_LONG_RUNNING_PROCESS=
EVIDENCE_FILES=
COMMITS_CREATED=
PUSH_STATUS=
FRAME_TRITS=
ORACLE_PROVENANCE=
```

A context compaction or model-context reset is not a campaign reset. Re-read CURRENT/OVERRIDES/REV39 and AUTONOMOUS_BATON, reconcile actual git/process state, and resume from `NEXT_SAFE_ACTION`.

## Explicitly NON-TERMINAL conditions

None of the following alone permits a final stop:

```text
S3_STAGE1_EMITTER_BLOCKED
native canonical V currently emits 0 records
one or more required semantic fields are absent from packed IR
one focused test fails
one adjacent/legacy test fails
native build fails with an attributable implementation error
hosted/native oracle mismatch
source SHA changed after self-source edit
frame usage increased but remains repairable
individual command timeout
long-running oracle/build with no stdout while process remains alive
transient VM/SSH/process failure
context compaction
checkpoint/report written
working tree dirty with preserved intended changes
remote upstream not configured
first attempted implementation rejected
```

For these states, diagnose, repair/retry/reconcile and continue.

## Retry and recovery policy

For a transient command/process/tool failure:

1. determine whether the original process is still alive before launching a duplicate;
2. avoid duplicate expensive oracle/build processes;
3. preserve original output/transcript;
4. retry only when the failure is attributable and retry is safe;
5. if the same causal approach fails three narrow attempts, change architecture/strategy within authorized constraints instead of stopping;
6. document rejected approaches as evidence and continue with the next viable bounded design.

`three narrow attempts` is a trigger to reconsider the approach, not a terminal-state rule.

## TRUE terminal state

A final response / campaign stop is allowed only when ONE of these is true:

### A. Maximum authorized campaign completed

All applicable gates through the currently authorized route have been completed with exact evidence:

```text
S1.2
S1.3
S1.4
S1.5
S1.6
S1.7
Stage1
real SELF_EMIT
real Stage2
real Stage3
fixed point
correctness
benchmark last when eligible
```

### B. Proven no-safe-path blocker

A blocker is terminal only if ALL are true:

```text
- exact first failing gate is identified;
- root cause is supported by concrete evidence;
- bounded source/lowering replay or narrow metadata preservation was audited;
- at least one alternative safe architecture was considered when applicable;
- continuing would require a forbidden action, normative semantic change without authorization, destructive evidence loss, merge/force/history rewrite, or a capability that is genuinely unavailable;
- there is no remaining safe autonomous repair, test, diagnostic, worktree, replay, or implementation step within Rev39 authorization.
```

If `NEXT_SAFE_ACTION` can be written meaningfully, the state is NOT terminal.

## No premature final response

Do not produce a final campaign report merely because the current gate remains BLOCKED after one iteration.

Intermediate reports are checkpoints only. After writing one, continue immediately unless TRUE terminal criteria are satisfied.

A message equivalent to:

```text
S1.2 remains blocked; no commit/push was made
```

is NOT a valid terminal response if another safe implementation/diagnostic step exists.

## Autonomous technical decisions

You may autonomously:

- inspect source/history/oracle references;
- design bounded semantic event/replay structures;
- edit canonical Stage1 and focused tooling/tests;
- create preservation patches and new clean recovery worktrees;
- run focused, Stage0, compileall, hosted oracle, native build and native probes;
- start the authorized VirtualBox Ubuntu guest headless if required;
- make coherent implementation/documentation commits after gates pass;
- configure branch upstream and push normally;
- update trackers and evidence reports;
- advance automatically after explicit previous-gate PASS.

Choose the design that is simplest, bounded, deterministic, fail-closed and closest to the frozen S3IR2 oracle.

## Architectural locks

- STREAMING_MULTI_PASS remains authoritative.
- No full-resident V/I/O/R tables or proportional banks.
- No single S3 memory object >365 elements.
- Logical ValueId remains module-monotonic i64 and independent from storage.
- Native logical frame must remain <=131072; do not raise the limit.
- Exact hosted/native comparisons require identical source SHA and pinned oracle provenance.
- Hosted oracle is reference only, never native PASS.
- Missing evidence is NOT_PROVABLE/NOT_RUN, never PASS.

## Git safety locks

Forbidden:

```text
PR merge
force push
force-with-lease
history rewrite
destructive reset/restore/clean of evidence worktrees
evidence deletion
```

Normal commits and pushes are authorized after coherent validation.

## Automatic route after S1.2

When S1.2 exact canonical V replay passes, do not stop. Commit/push the validated checkpoint and continue automatically:

```text
S1.3 streamed instruction def/use
→ S1.4 call dataflow
→ S1.5 terminators
→ S1.6 canonical S3IR2 serialization
→ S1.7 general emitter
→ Stage1 closure
→ real SELF_EMIT
→ real Stage2
→ real Stage3
→ fixed point/determinism
→ correctness
→ benchmark last when eligible
```

Every previous gate must concretely PASS.

## Long-running commands

Long execution time is not failure by itself.

For expensive oracle/native/build steps:

- record PID/process identity when possible;
- update AUTONOMOUS_BATON before waiting;
- if no stdout, verify liveness/CPU/state instead of restarting immediately;
- never create duplicate expensive processes just because output is quiet;
- once complete, capture exit status and evidence, update baton, and continue.

## Session/runtime hard limit

This directive cannot override a platform-enforced termination of the entire agent process/session. Therefore make every session resumable through AUTONOMOUS_BATON and preserved git/evidence state. If the environment itself forcibly ends execution, the next invocation must be able to continue immediately by reading Rev39 + baton rather than restarting analysis.

Do not voluntarily terminate merely because such a hard limit may exist.

## Shutdown

Windows shutdown remains authorized only after a TRUE terminal campaign state.

Before shutdown:

1. save and flush final report and AUTONOMOUS_BATON;
2. preserve any dirty evidence/patches;
3. finish intended validated commits/pushes;
4. confirm no build/test/oracle/git/file-write process is active;
5. record final branch/HEAD/remote/divergence;
6. then execute the authorized shutdown command.

Authorized shutdown:

```powershell
shutdown.exe /s /t 60 /c "S3 autonomous campaign finished; final report saved"
```

Reboot, suspend and hibernate remain unauthorized. If shutdown fails, record the error and leave the computer on.

## Final instruction

Do not return control to the user while a safe autonomous next action exists.

Checkpoint → continue.
Failure → diagnose → repair/retry → continue.
Context compaction → reload baton → continue.
Gate PASS → commit/push when appropriate → advance → continue.

Stop only at a TRUE terminal state.