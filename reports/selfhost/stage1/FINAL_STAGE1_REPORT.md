# Stage1 Bootstrap IR and General Emitter Closure

## Candidate

- `FINAL_TESTED_SOURCE_HEAD=bb6cac76270fa1eccf98a9f246e1ee00993ff923`
- `T4_TESTED_HEAD=bb6cac76270fa1eccf98a9f246e1ee00993ff923`
- `SOURCE_CHANGED_AFTER_FINAL_GATES=NO`
- `T4_RERUN_REQUIRED=NO`
- canonical source bytes: `156257`
- canonical source SHA-256: `1ad04849dc80edeae6e0d1327677f0b79b0ef604180952adf45075dff7f78a1a`
- branch: `feature/actual-stage1-compiler-seed-20260824`
- PR: `#268`, Draft, no merge

## Pipeline result

The frozen Stage1 source performs real bounded lexing, parsing, semantic checks,
IR construction and verification. The audit reached 34 source functions (29
local and 5 foreign), 64 parameters, 23 locals, 305 blocks, 1460 instructions,
1213 values, 656 calls (653 internal and 3 foreign), 104 branches, 6 loops and
107 returns. The event categories remain explicit and fail closed at their
configured capacities.

```text
SELF_LEX=PASS
SELF_PARSE=PASS
SELF_SEMANTIC=PASS_BOUNDED
SELF_IR=PASS_LOSSLESS_BOOTSTRAP_SUBSET
SELF_VERIFY=PASS_LOSSLESS_BOOTSTRAP_SUBSET
GENERAL_EMITTER=PARTIAL_LITERAL_RETURN_SUBSET
FUNCTION_EMISSION=PASS_LITERAL_FIXTURE
SELF_EMIT=BLOCKED
STAGE1_TO_STAGE2=BLOCKED_NOT_STARTED
FULL_SELF_HOSTING=NO
```

The general emitter now consumes preserved IR for the verified multi-function
literal-return fixture. It emits deterministic symbols and native Linux
x86-64 assembly. It does not inspect raw source, pattern-match source text,
embed Stage2 assembly, or claim support for locals, expressions, branches,
loops, calls or general typed instruction selection.

## First blocker

The full canonical self source reaches the real emitter boundary and exits 2
with `S3_STAGE1_AUDIT ...` followed by `S3_STAGE1_EMITTER_BLOCKED`. The primary
blocker is `IR_CALL_ARGUMENT_POOL_CAPACITY_EXCEEDED`: the current bounded call
argument lanes cannot represent the full self-source event stream. The broader
`GENERAL_EMITTER_CAPABILITY_GAP` is a secondary capability boundary. This is a
fail-closed result. No fake Stage2 artifact was created and Stage3 was not
started.

## Focused and native evidence

- focused IR/general-emitter/smart-runner tests: `35 passed, 1 skipped`
- focused canonical-source tests: `4 passed`
- `python -m compileall bootstrap tests tools`: PASS
- Linux x86-64 trivial native fixture: PASS
- Linux x86-64 multi-function literal emitter fixture: PASS
- self-source native attempt: expected blocker contract PASS
- benchmark: NOT RUN
- performance claim: NONE

No final artifact or assembly digest is claimed because the self-source emitter
blocked before producing one. The supported native fixture outputs were
verified on `s3-vm`; they do not establish full self-hosting.

## Final T4

The final T4 was executed exactly once at the frozen source head. Raw evidence:
`reports/selfhost/stage1/t4-final-20260825-010551.raw.txt`

```text
T4_START=2026-08-25T01:05:51.8831870-03:00
T4_END=2026-08-25T02:37:23.7493296-03:00
T4_SELECTED=455
T4_PASS=454
T4_FAIL=0
T4_TIMEOUT=1
T4_EXIT=1
```

The sole timeout was:

```text
path=tests/test_stage1_compiler_seed.py
timeout_class=HEAVY_SELF_HOSTING
applied_timeout_seconds=180
captured_output_tail=....
```

The timeout is recorded as a timeout, not converted into a pass. No T4 rerun
is required because no executable/compiler/test logic changed after this run;
subsequent work is evidence, handoff and documentation only.

## Safety and handoff

The liveness-only watchdog script is present but was not started because no
stable controller PID was registered safely:

```text
WATCHDOG_STARTED=NO
WATCHDOG_TRIGGERED=NO
EMERGENCY_SHUTDOWN=NO
```

It does not use elapsed duration, no-output, heartbeat, test, build or SSH
signals and does not kill processes. The normal shutdown request is reserved
for the final handoff after evidence is committed and pushed.

## Scope boundary

No Stage2, Stage3, benchmark, merge, tag or release was started. The next
technical unit is to extend the verified IR and general emitter without
increasing bounds silently, then retry SELF_EMIT only after a new source freeze
and a new single T4.
