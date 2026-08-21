# M2.00 T4 Timeout Policy

## Policy

The runner policy remains explicit and finite:

```text
DEFAULT=60S
HEAVY_SELF_HOSTING=180S
HEAVY_RENDERER=300S
T4_PARALLELISM=1
PROCESS_MODEL=ONE_PYTEST_SUBPROCESS_PER_FILE
TIMEOUT_SEMANTICS=WHOLE_FILE_WALL_CLOCK
UNKNOWN_CLASS=FAIL_CLOSED
```

The timeout class and applied seconds are recorded for every selected file.
Timeout is never converted to PASS. No filename pattern, prior result, or
unlimited class is used.

## Pre-reboot evidence

The decimal and opcode classifier files were unchanged in M1.91-M2.00 and
both were stable slow workloads under the pre-reboot diagnostic. The final
policy T4 at `efab5bf6a0d790f167004a15696f4bc4e62c87dc` selected 369 files,
passed 352, failed 0, timed out 17, and exited 1. Sixteen timeout rows used
`HEAVY_RENDERER=300`; one, `tests/test_external_jsmn_s3.py`, used
`DEFAULT=60`. The raw T4 remains unchanged at
`T4-timeout-policy-20260820-214407.txt`.

## Post-reboot JSMN evidence

The only residual was retested after the Windows reboot. Five fresh
processes, each followed immediately by a fresh `tests/test_ternary.py`
control, all passed:

```text
JSMN_5X_SECONDS=43.749,35.661,30.623,36.608,36.673
JSMN_5X_EXIT_CODES=0,0,0,0,0
JSMN_5X_TIMEOUTS=0
JSMN_5X_CONTROLS=5/5_PASS
```

Because all five were below 60 seconds and the maximum was below 45 seconds,
the required 10-run margin sequence was executed:

```text
JSMN_10X_SECONDS=37.737,38.640,30.544,30.565,31.600,31.550,29.592,30.588,35.626,32.556
JSMN_10X_PASS=10/10
JSMN_10X_TIMEOUT=0
JSMN_10X_ABNORMAL_EXIT=0
JSMN_10X_ORPHAN=0
JSMN_10X_MEDIAN=31.575
JSMN_10X_P95=38.640
JSMN_10X_P95_METHOD=NEAREST_RANK
JSMN_10X_MAX=38.640
JSMN_10X_CV=0.0935
JSMN_10X_CONTROLS=10/10_PASS
JSMN_DEFAULT_60S_MARGIN=HEALTHY
```

This establishes `PRE_REBOOT_HOST_STATE_CONTAMINATION`. The residual is not
normally over 60 seconds and must not be promoted to a heavy class.

## Lifecycle audit

`tests/test_external_jsmn_s3.py` calls `compile_source` once and
`run_source_with_buffer_capture` once per `_run_s3` invocation. There are 17
such invocations across the parameterized cases, so 34 in-memory compiler
passes in total. The latter function compiles once more and executes the
hosted Assembly Emulator with memory capture. The test itself launches no
child process, no native compiler, no linker, and no external JSMN build.

```text
JSMN_CHILD_PROCESS_COUNT_ESTIMATE=0
JSMN_NATIVE_BUILD_COUNT=0
JSMN_TEMP_ARTIFACT_MODEL=NONE
JSMN_PROCESS_CLEANUP_MODEL=NO_TEST_CHILDREN; PYTEST_PROCESS_EXITS_NORMALLY
ORPHAN_PROCESS_DETECTED=NO
ROOT_VARIANCE_PHASE=NOT_APPLICABLE_POST_REBOOT
```

The process snapshots before and after every run contained no `python.exe`,
compiler, linker, or generated executable belonging to a completed test.
The remaining snapshot entries were Windows SearchHost and the diagnostic
PowerShell wrapper itself.

## Gate boundary

No T4 was run in this prompt. The evidence makes another final T4 eligible,
but does not perform it:

```text
RUNNER_CHANGE=NO
S3_PRODUCTION_CHANGE=NO
NEXT_T4_ELIGIBLE=YES
T4_RUNS_THIS_PROMPT=0
```
