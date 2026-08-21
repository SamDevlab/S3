# M2.00 T4 Timeout Policy

## Decision

The two originally new timeout files were characterized in three fresh
processes each before the policy T4. Both completed successfully in every
run, with medians above the default 60-second per-file budget. They are
bounded slow workloads, not functional regressions or 300-second hangs.

```text
DECIMAL_RUNS_SECONDS=116.604,101.277,108.882
DECIMAL_MEDIAN_SECONDS=108.882
DECIMAL_MAX_SECONDS=116.604
DECIMAL_CLASS=STABLE_SLOW_TEST_EXCEEDS_T4_FILE_BUDGET

OPCODE_RUNS_SECONDS=99.557,87.832,83.417
OPCODE_MEDIAN_SECONDS=87.832
OPCODE_MAX_SECONDS=99.557
OPCODE_CLASS=STABLE_SLOW_TEST_EXCEEDS_T4_FILE_BUDGET
```

The one-run control group was:

```text
tests/test_compare_assembly_renderer.py=WATCHDOG_300S
tests/test_m150_renderer_component.py=WATCHDOG_300S
tests/test_s3_renderer_generic_text.py=175.666S_EXIT_0
```

The controls establish that the default budget is below the runtime of
heavy renderer workloads on this Windows host. The two 300-second watchdog
terminations were diagnostic-child cleanup, not T4 results.

## Declarative classes

The policy is stored in `tests/test-impact.json` and interpreted by
`tools/s3test.py`:

```text
DEFAULT=60S
HEAVY_SELF_HOSTING=180S
HEAVY_RENDERER=300S
```

The classes are finite and assigned by explicit test-path metadata. The
runner has no filename-pattern fallback, previous-result lookup, unlimited
class, or automatic conversion of timeout to PASS. Unknown classes fail
closed at manifest load. The applied class and seconds are present in every
selected result, and the timeout-policy fingerprint participates in resume
eligibility.

The two characterized files are assigned to `HEAVY_SELF_HOSTING`; the
recurring renderer/toolchain files are assigned to `HEAVY_RENDERER`.

## Runner semantics

Files run serially. A class value is a wall-clock budget for the complete
pytest-file subprocess. Stdout and stderr are captured through
`communicate()`. Windows timeout cleanup uses `taskkill /PID /T /F`, so the
child process tree is terminated. A timeout remains `TIMEOUT` in the raw
report and is never a test PASS.

```text
RUNNER_CHANGE=YES
RUNNER_COMMIT=1712f76
DEFAULT_T4_FILE_TIMEOUT=60
T4_PARALLELISM=1
PROCESS_MODEL=ONE_PYTEST_SUBPROCESS_PER_FILE
TIMEOUT_KILL_MODEL=WINDOWS_TASKKILL_FORCE
CHILD_PROCESS_TREE_HANDLING=YES
OUTPUT_CAPTURE_MODEL=COMBINED_STDOUT_STDERR_PIPE
POLICY=EXPLICIT_BOUNDED_HEAVY_TIMEOUT_CLASSES
UNKNOWN_CLASS=FAIL_CLOSED
```

## Final policy T4

The one permitted policy T4 ran at
`efab5bf6a0d790f167004a15696f4bc4e62c87dc`. It applied an explicit class to
every timeout, but it still returned a timeout status:

```text
SELECTED=369
PASS=352
FAIL=0
TIMEOUT=17
T4_EXIT=1
HEAVY_RENDERER_TIMEOUTS=16
HEAVY_SELF_HOSTING_TIMEOUTS=0
DEFAULT_TIMEOUTS=1
UNCLASSIFIED_TIMEOUTS=0
```

The 16 renderer timeouts were at the explicit 300-second class. The decimal
and opcode files passed at the explicit 180-second class. The remaining
timeout was `tests/test_external_jsmn_s3.py` at the declared `DEFAULT=60`
class.

That residual was characterized after the policy T4 in three fresh
processes, without another T4:

```text
EXTERNAL_JSMN_RUNS_SECONDS=7.237,26.190,130.917
EXTERNAL_JSMN_EXIT_CODES=-1073741510,-1073741510,0
EXTERNAL_JSMN_PYTEST_RESULT=two non-terminal process aborts; one PASS
EXTERNAL_JSMN_WATCHDOG=NO
EXTERNAL_JSMN_CLASS=HOST_SCHEDULING_VARIANCE
```

The two `0xC000013A` exits are not pytest assertion failures, but they also
do not establish a stable bounded PASS. The 130.917-second pass exceeds the
default budget. This is therefore retained as an unresolved environment /
orchestration residual, not promoted to a heavy class after the final T4.

The raw policy T4 is preserved at
`T4-timeout-policy-20260820-214407.txt`. The JSMN diagnostic capture is
preserved outside the repository at
`%TEMP%\\s3-m200-external-jsmn-diagnostic-final-20260820-235715`.

```text
T4_RESULT_PRESERVED=YES
T4_STATUS=TIMEOUT
RELEASE_TIMEOUT_POLICY=DECLARED_CLASSES_REQUIRED_BUT_UNSTABLE_DEFAULT_RESIDUAL_NOT_ACCEPTED
```
