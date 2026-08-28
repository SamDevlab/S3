# REV36 — AUTONOMOUS STREAMED STAGE1 → STAGE2 → STAGE3

This revision supersedes Rev35 for the active self-hosting recovery campaign.

## User authorization

The user explicitly authorizes continuous autonomous technical decision-making while away. The agent may inspect, edit, test, build, start the `Ubuntu server` VirtualBox guest headless when required, create preservation patches/worktrees, make coherent commits, update trackers, and perform normal non-force pushes without waiting for confirmation, provided every forward transition is gated by concrete evidence.

Missing evidence is never PASS.

## Active implementation

```text
BRANCH=recovery/pr268-stage1-streaming-values-20260828
BASE_HEAD=1ec76af89992f119865a370488593ad5c85c4c49
LAST_TESTED_SOURCE_SHA256=44f022820a9191e3a6d402c188eb4b242e0ffeefd7a149b15e2b46039031b9cb
```

Validated architecture evidence:

```text
REV35_FULL_RESIDENT_FRAME=375670
REV35_FULL_RESIDENT_BANK_MEMORY=291270
BASELINE_FRAME=87326
STREAMING_FRAME=82781
FRAME_LIMIT=131072
FRAME_HEADROOM=48291
STREAMING_FRAME_GATE=PASS
FULL_RESIDENT_BANKING=REJECTED
SEMANTIC_STORAGE_STRATEGY=STREAMING_MULTI_PASS
```

Current semantic state:

```text
S1.1_FOUNDATION=PASS
S1.2_MECHANISM=PASS
S1.2_STREAMED_CANONICAL_ENUMERATION=BLOCKED
S1.2_CANONICAL_COMPLETENESS=BLOCKED
S1.3_DEF_USE=NOT_STARTED
CURRENT_FIRST_BLOCKER=S1_2_CANONICAL_STREAM_COMPLETENESS
NEXT_TASK=IMPLEMENT_BOUNDED_LOSSLESS_CANONICAL_V_REPLAY_STREAM
```

Latest hosted snapshot for the last tested source, subject to exact provenance revalidation after any source change:

```text
S3IR2_TOTAL_V_RECORDS=38724
PARAMETERS=70
LOCAL_BINDINGS=246
CONSTANTS=34945
INSTRUCTION_RESULTS=3463
INSTRUCTIONS=58070
OPERAND_EDGES=37349
RESULT_EDGES=38408
CALLS=861
TERMINATORS=3747
```

## Oracle provenance lock

Before exact hosted/native equality claims, pin and record:

```text
SOURCE_SHA256
ORACLE_STREAM_REF/COMMIT/BLOB
SEMANTIC_IR_REFERENCE_REF/COMMIT/BLOB
SOURCE_BINDING_REFERENCE_REF/COMMIT/BLOB
BOOTSTRAP_PIPELINE_HEAD
PYTHON_EXECUTABLE
PYTHONPATH
OPTIMIZATION/INVOCATION MODE
```

Run the oracle twice. Same source and same oracle provenance must produce identical counts and stream hash. Any unexplained difference blocks semantic closure until attributed.

Frozen semantic handoff candidate:

```text
c12e45d646af27f85b39c391d3a7645a812b28c5
```

Do not assume a reference is authoritative merely from its filename; verify exact provenance.

## Architecture locks

1. Logical semantic IDs are not physical storage slots.
2. Value IDs remain module-monotonic logical `i64` identities according to S3IR2.
3. No single S3 array/memory object may exceed 365 elements.
4. Do not reintroduce full-resident value/constant/instruction/operand/result banks proportional to whole-module IR size.
5. Resident compiler state must remain bounded by fixed metadata, function/binding state, and live/replay state rather than total logical IR size.
6. The native frame limit remains 131072 logical trits. Do not increase it to make Stage1 pass.
7. Full-resident banking is preserved rejected evidence.
8. Streaming/replay should use a small fixed number of whole-source passes, not a whole-source rescan for every semantic record.
9. Do not weaken semantic, determinism, fail-closed, resource, or provenance tests to obtain PASS.

## Autonomous repair policy

For a concrete failure:

1. capture command/output/exit/hash;
2. identify the first causal failure;
3. make the narrowest attributable repair;
4. rerun the smallest proving test;
5. rerun the gate;
6. continue automatically if PASS.

Up to three narrow repairs for the same causal blocker are allowed. If the blocker is structural, the agent may choose and implement a better bounded architecture autonomously when evidence supports it and all locks above remain satisfied. Preserve rejected attempts before moving to a clean worktree/branch.

Stop forward progress only when the blocker cannot be safely attributed, would require changing language/runtime normative limits without evidence, requires destructive evidence cleanup, requires a merge/force push/history rewrite, or remains unresolved after the bounded repair/design attempts. Record the blocker exactly.

## S1.2 gate — canonical V replay

Implement bounded lossless native `V` replay and compare against the exact hosted S3IR2 stream from the same source SHA.

S1.2 PASS requires:

```text
ORACLE_PROVENANCE=PASS
HOSTED_V_COUNT=NATIVE_V_COUNT
VALUE_IDS=PASS
FUNCTION_IDS=PASS
VALUE_KINDS=PASS
TYPE_CODES=PASS
ANCHOR_STARTS=PASS
ANCHOR_LENGTHS=PASS
MUTABILITY=PASS
STORAGE_IDS=PASS
VALUE_ORDER=PASS
NO_UNRESOLVED=PASS
NO_TRUNCATION=PASS
NO_COLLISION=PASS
CROSS_365_LOGICAL_VALUE_IDS=PASS
DETERMINISM=PASS
FOCUSED_TESTS=PASS
STAGE0=PASS
COMPILEALL=PASS
NATIVE_BUILD=PASS
NATIVE_V_REPLAY=PASS
FRAME_AFTER<=131072
```

Any canonical source edit requires recomputing source SHA and regenerating the hosted oracle before comparison.

After PASS, create a coherent commit and normal push. Suggested commit:

```text
selfhost(stage1): stream canonical semantic value records
```

## S1.3 gate — streamed def/use

Only after S1.2 PASS, implement exact streamed `I`, ordered `O`, and `R` records using the same logical value IDs. Require nested-result reuse, non-commutative operand ordering, parameter/local/constant uses, deterministic instruction IDs, native probes, exact hosted/native conformance, and frame <=131072.

Suggested commit:

```text
selfhost(stage1): stream canonical instruction def-use
```

## S1.4 gate — calls

Only after S1.3 PASS, implement canonical streamed call dataflow (`C`, `A`), callee resolution, argument order, and call result links using the existing I/O/R/value identities.

## S1.5 gate — terminators

Only after S1.4 PASS, implement complete return/jump/branch3 semantic links and target identities. Fail closed on unresolved values or targets.

## S1.6 gate — canonical serialization

Only after S1.5 PASS, produce deterministic canonical S3IR2 v2 serialization. `Z31` must emerge from the five completeness lanes; never force it. Streaming serialization is allowed and preferred over retaining the whole artifact in frame memory.

## S1.7 gate — general emitter

Only after S1.2–S1.6 PASS, repair/complete the general emitter. Stage1 integration PASS requires canonical self-input to pass the emitter boundary and produce non-empty valid assembly with exact evidence.

## Bootstrap gates

Only after complete Stage1 PASS:

```text
SELF_EMIT
→ real Stage2
→ Stage2 builds real Stage3
→ Stage2↔Stage3 fixed-point/determinism gate
→ correctness matrix
→ benchmark last
```

Stage2 must be produced by real Stage1 self-emission, never copy/rename. Stage3 must be compiled by real Stage2. Fixed-point PASS uses the project's existing equality/determinism contract; do not invent a weaker comparator to obtain PASS.

Correctness precedes benchmark. No performance claim without comparable baseline and complete provenance.

## Git/worktree locks

Allowed:

```text
coherent validated commits
normal push
push -u for a new recovery branch
new clean recovery worktree/branch when preserving dirty evidence requires it
tracker/report updates
```

Forbidden:

```text
PR merge
force push
force-with-lease
history rewrite
reset/restore/clean of preserved dirty evidence worktrees
destructive deletion of recovery evidence
```

## Host safety and final shutdown

Do not reboot, suspend, or hibernate the Windows host.

The user now explicitly authorizes a Windows shutdown only after the autonomous campaign reaches either:

- the maximum safely reachable authorized gate through Stage3/fixed-point/correctness/benchmark, or
- a terminal blocker that has been fully documented and no further safe autonomous repair is available.

Before shutdown:

1. write and flush the final report;
2. preserve any dirty worktree evidence/patches;
3. finish any intended commit and normal push;
4. verify no build, test, git, oracle, or file-write process remains active;
5. record final branch/HEAD/remote/divergence and maximum gate reached.

Then execute exactly one normal Windows shutdown command, preferably:

```text
shutdown.exe /s /t 60 /c "S3 autonomous campaign finished; final report saved"
```

Do not reboot. Do not escalate privileges if shutdown fails. If shutdown is unavailable, record the exact error and leave the host running.

## Final report

Always write a final report with exact evidence for every lane:

```text
S1.1
S1.2
S1.3
S1.4
S1.5
S1.6
S1.7
STAGE1
SELF_EMIT
STAGE2
STAGE3
FIXED_POINT
CORRECTNESS
BENCHMARK
```

Use only PASS, FAIL, BLOCKED, NOT_RUN, NOT_PROVABLE, or NOT_APPLICABLE with concrete evidence. Never fabricate progress.
