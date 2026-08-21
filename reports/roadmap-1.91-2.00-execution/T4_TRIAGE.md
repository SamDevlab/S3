# T4 Failure Triage

Historical T4 transcripts remain unchanged. No T4 was run in this prompt.

## Provenance and host

```text
HEAD=cff4da02c6f135c44dd0b8c75795361aac0ebcfc
BRANCH=feature/m191-m200-autonomous-20260819
WORKTREE_CLEAN=YES
LAST_BOOT=2026-08-21T04:52:45.5000000-03:00
HOST_UPTIME_AT_SNAPSHOT=00:20:00
PYTHON=3.11.9
WINDOWS=Microsoft Windows 11 Home 10.0.26200 Build 26200
LOGICAL_CPUS=8
FREE_MEMORY_KB=1452168
PROCESS_COUNT=274
HYPERVISOR_PRESENT=False
```

## Post-reboot JSMN characterization

Each run used a separate Python process with a 300-second watchdog and was
immediately followed by a separate `tests/test_ternary.py` control process.
The five-run raw capture is
`T4-timeout-policy-post-reboot-jsmn-20260821-052241.txt`.

```text
RUNS_SECONDS=43.749,35.661,30.623,36.608,36.673
EXIT_CODES=0,0,0,0,0
PYTEST_RESULT=5/5 runs reported 18 passed
TIMEOUT_COUNT=0
ABNORMAL_EXIT_COUNT=0
CONTROL_RUNS_SECONDS=4.424,4.402,4.405,4.385,5.451
CONTROL_PASS_COUNT=5
ORPHAN_PROCESS_DETECTED=NO
```

The five-run maximum was below 45 seconds, so the 10-run margin capture
`T4-timeout-policy-post-reboot-jsmn-10x-20260821-052715.txt` was required and
completed:

```text
RUNS_SECONDS=37.737,38.640,30.544,30.565,31.600,31.550,29.592,30.588,35.626,32.556
EXIT_CODES=0,0,0,0,0,0,0,0,0,0
PYTEST_RESULT=10/10 runs reported 18 passed
TIMEOUT_COUNT=0
ABNORMAL_EXIT_COUNT=0
CONTROL_RUNS_SECONDS=5.448,4.402,4.388,4.406,4.372,4.407,4.426,4.422,4.364,5.540
CONTROL_PASS_COUNT=10
ORPHAN_PROCESS_DETECTED=NO
MEDIAN_SECONDS=31.575
P95_SECONDS=38.640
P95_METHOD=NEAREST_RANK
MAX_SECONDS=38.640
COEFFICIENT_OF_VARIATION=0.0935
JSMN_DEFAULT_60S_MARGIN=HEALTHY
```

## Lifecycle audit

The exact path is `_run_s3` -> `compile_source` for IR inspection, then
`run_source_with_buffer_capture`, which compiles again and invokes the hosted
Assembly Emulator. The 17 `_run_s3` test cases therefore perform 34
in-memory compile passes; the source-contract test performs no execution.
There are no subprocess, native toolchain, linker, temporary executable, or
external JSMN build calls in this test path.

```text
JSMN_CHILD_PROCESS_COUNT_ESTIMATE=0
JSMN_NATIVE_BUILD_COUNT=0
JSMN_TEMP_ARTIFACT_MODEL=NONE
JSMN_PROCESS_CLEANUP_MODEL=NOT_APPLICABLE; NO_CHILDREN
ORPHAN_PROCESS_DETECTED=NO
ROOT_VARIANCE_PHASE=NOT_APPLICABLE_POST_REBOOT
```

## Classification and next gate

```text
PRE_REBOOT_CLASSIFICATION=HOST_SCHEDULING_VARIANCE
POST_REBOOT_CLASSIFICATION=PRE_REBOOT_HOST_STATE_CONTAMINATION
RUNNER_CHANGE=NO
S3_PRODUCTION_CHANGE=NO
NEXT_T4_ELIGIBLE=YES
T4_RUNS_THIS_PROMPT=0
```

Eligibility is not execution: a human decision is required before another
final T4.
