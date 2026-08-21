# M2.00 T4 Timeout Policy

## Decision

The two new timeout files were independently characterized in fresh Python
processes. Each completed successfully in all three runs and each has a
median above the default 60-second per-file budget. They are bounded slow
workloads, not functional regressions or hangs.

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

The control group was selected from recurring renderer/toolchain-heavy T4
timeouts:

```text
tests/test_compare_assembly_renderer.py=WATCHDOG_300S
tests/test_m150_renderer_component.py=WATCHDOG_300S
tests/test_s3_renderer_generic_text.py=175.666S_EXIT_0
```

The controls establish that the default budget is structurally below the
runtime of heavy renderer workloads on this Windows host. The two watchdog
terminations were diagnostic-child cleanup at the explicit 300-second
watchdog, not T4 results and not functional assertions.

## Declarative classes

The policy is stored in `tests/test-impact.json` and interpreted by
`tools/s3test.py`:

```text
DEFAULT=60S
HEAVY_SELF_HOSTING=180S
HEAVY_RENDERER=300S
```

`DEFAULT` remains the command-line default. The heavy values are finite and
are applied only to explicitly assigned test paths. There is no filename
pattern fallback, previous-result lookup, unlimited class, or automatic
promotion of timeout to PASS. Unknown classes fail closed at manifest load.

The two newly characterized files are assigned to
`HEAVY_SELF_HOSTING`. The 23 recurring renderer/toolchain timeout files are
assigned to `HEAVY_RENDERER` so every timeout in the prior final candidate has
an explicit, reviewable class. The report schema records both the applied
class and the applied seconds for every selected file.

The timeout policy fingerprint is included in smart-test resume fingerprints;
changing a class or assignment invalidates a saved state rather than reusing
it.

## Semantics

The subprocess model is unchanged: files run serially, stdout and stderr are
captured through `communicate()`, and Windows timeout cleanup uses
`taskkill /PID /T /F`. The applied value is a wall-clock budget for the whole
pytest file process. A timeout remains `TIMEOUT` in the raw report and does not
become a test PASS.

```text
POLICY=EXPLICIT_BOUNDED_HEAVY_TIMEOUT_CLASSES
DEFAULT_T4_FILE_TIMEOUT=60
T4_TIMEOUT_CLASS_METADATA=DECLARATIVE
T4_TIMEOUT_RESULT_PRESERVED=YES
UNKNOWN_CLASS=FAIL_CLOSED
```
