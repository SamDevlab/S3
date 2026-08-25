# Stage1 General Emitter Capability Closure

## Candidate

- `FINAL_TESTED_SOURCE_HEAD=2b9a391dc1376d34cd13a946a16d92693d389898`
- `T4_TESTED_HEAD=d8089a65fe43201e65dd6d0245a629d3c68eeae2`
- `SOURCE_CHANGED_AFTER_T4=NO`
- `T4_RERUN_REQUIRED=NO`
- canonical source: `selfhost/compiler/s3c_stage1.s3`
- source bytes: `166984`
- source SHA-256: `20fddbb73eee9ae09de911493f2f2da01ab582c7a6de879ea2e557946716a341`
- branch: `feature/actual-stage1-compiler-seed-20260824`
- PR: `#268`, Draft, not merged

## Closed checkpoint

The former call-argument-pool blocker is resolved and remains historical only:

```text
POOL_REQUIRED=736
POOL_CAPACITY=746
POOL_BANKS=[365,365,16]
POOL_HEADROOM=10
IR_CALL_ARGUMENT_POOL_CAPACITY=PASS
```

Native Linux x86-64 post-fix evidence measured 656 calls, 736 arguments,
maximum arity 4, and first unstorable argument index `-1`. The closure evidence
is in `call-argument-pool-closure.json`.

## IR audit and emitter result

The canonical self-source reaches lexing, bounded parsing, semantic checks,
IR construction, and verification. The current IR preserves function identity,
aggregate counts, packed event records, bounded call metadata, value records,
and bounded block target lanes. It does not preserve typed per-instruction
definitions, uses, results, local/parameter identities, or complete terminator
semantics.

The required-shape matrix is recorded in
`general-emitter-required-ops.json`, and the Linux x86-64 ABI contract is in
`bootstrap-abi.md`.

```text
GENERAL_EMITTER=FAIL_CLOSED
PARAMETER_EMISSION=BLOCKED_EMITTER_PARAMETER
LOCAL_EMISSION=BLOCKED_EMITTER_LOCAL
VALUE_EMISSION=BLOCKED_EMITTER_VALUE
ARITHMETIC_EMISSION=BLOCKED_EMITTER_ARITHMETIC
COMPARISON_EMISSION=BLOCKED_EMITTER_COMPARISON
INTERNAL_CALL_EMISSION=BLOCKED_EMITTER_INTERNAL_CALL
FOREIGN_CALL_EMISSION=BLOCKED_EMITTER_FOREIGN_CALL
CFG_EMISSION=BLOCKED_EMITTER_CFG
BRANCH_EMISSION=BLOCKED_EMITTER_CFG
LOOP_EMISSION=BLOCKED_EMITTER_LOOP
RETURN_EMISSION=PASS_LITERAL_FIXTURE_ONLY
```

The supported multi-function literal-return fixture emits deterministic native
Linux x86-64 assembly and links successfully. The canonical self-source was
executed from the clean post-fix build and returned exit code `2` with
`S3_STAGE1_EMITTER_BLOCKED`; it produced no assembly.

```text
SELF_EMIT=BLOCKED
FIRST_BLOCKER=GENERAL_EMITTER_CAPABILITY_GAP
STAGE1_TO_STAGE2=BLOCKED_NOT_STARTED
STAGE3=NOT_STARTED
FULL_SELF_HOSTING=NO
BENCHMARK=NOT_RUN
PERFORMANCE_CLAIM=NONE
```

## Validation

- focused IR/general-emitter/smart-runner tests: `37 passed, 1 skipped`
- `python -m compileall bootstrap tests tools`: PASS
- JSON validation: PASS
- `git diff --check`: PASS
- Linux x86-64 supported-subset native fixtures: PASS

## Final T4

The final T4 was executed exactly once after the source candidate was frozen.
The raw transcript is `t4-final-20260825-103341.raw.txt`.

```text
T4_START=2026-08-25T10:33:41.4971731-03:00
T4_END=2026-08-25T12:02:10.2415276-03:00
T4_SELECTED=455
T4_PASS=454
T4_FAIL=0
T4_TIMEOUT=1
T4_UNCLASSIFIED_TIMEOUT=0
T4_EXIT=1
```

The only timeout was:

```text
path=tests/test_stage1_compiler_seed.py
timeout_class=HEAVY_SELF_HOSTING
applied_timeout_seconds=180
captured_output_tail=....
```

The timeout remains a timeout and is not reclassified as a pass. No T4 rerun
is required because no compiler, runtime, or test logic changed after the T4.

## Scope boundary

No source rereading, source pattern matching, Python code generation, embedded
Stage2 assembly, Stage2 attempt, Stage3 work, benchmark, merge, tag, or release
was started. The next technical unit is to extend the verified IR with typed
definition/use/result lanes and complete block terminator semantics, then add
stack-first emission over those lanes.
