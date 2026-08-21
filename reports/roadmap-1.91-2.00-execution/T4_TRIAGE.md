# T4 Failure Triage

Historical raw T4 transcripts remain unchanged. The policy T4 was run once
after the bounded timeout-class runner change; no fourth T4 was run.

## Runner and policy

```text
RUNNER_COMMIT=1712f76
POLICY_DOCUMENT_COMMIT=efab5bf
DEFAULT_TIMEOUT=60
PARALLELISM=1
PROCESS_MODEL=SERIAL_PYTEST_SUBPROCESS_PER_FILE
TIMEOUT_SEMANTICS=WHOLE_FILE_WALL_CLOCK
CHILD_TREE_CLEANUP=taskkill /PID /T /F
```

The manifest declares `DEFAULT=60`, `HEAVY_SELF_HOSTING=180`, and
`HEAVY_RENDERER=300`. The result schema records the selected class and
seconds; unknown classes fail closed.

## Required timeout diagnostics

```text
DECIMAL_CHANGED_IN_M191_M200=NO
DECIMAL_RUNS_SECONDS=116.604,101.277,108.882
DECIMAL_MEDIAN_SECONDS=108.882
DECIMAL_RESULT=STABLE_SLOW_TEST_EXCEEDS_T4_FILE_BUDGET

OPCODE_CLASSIFIER_CHANGED_IN_M191_M200=NO
OPCODE_RUNS_SECONDS=99.557,87.832,83.417
OPCODE_MEDIAN_SECONDS=87.832
OPCODE_RESULT=STABLE_SLOW_TEST_EXCEEDS_T4_FILE_BUDGET
```

The two diagnostic groups were 3/3 pytest PASS under a 300-second watchdog.
They were assigned to `HEAVY_SELF_HOSTING=180` before the policy T4.

Control runs were:

```text
tests/test_compare_assembly_renderer.py=WATCHDOG_300S
tests/test_m150_renderer_component.py=WATCHDOG_300S
tests/test_s3_renderer_generic_text.py=175.666S_EXIT_0
```

## Final policy T4

```text
NEW_T4_RUNS=1
FINAL_T4_HEAD=efab5bf6a0d790f167004a15696f4bc4e62c87dc
FINAL_T4_SELECTED_FILES=369
FINAL_T4_PASS_FILES=352
FINAL_T4_FAIL_FILES=0
FINAL_T4_TIMEOUT_FILES=17
FINAL_T4_UNCLASSIFIED_TIMEOUT_FILES=0
FINAL_T4_EXIT=1
FINAL_T4_STATUS=TIMEOUT
FINAL_T4_REPORT=T4-timeout-policy-20260820-214407.txt
ADDITIONAL_T4_RUNS=0
```

Timeout class distribution:

```text
HEAVY_RENDERER_300S=16
HEAVY_SELF_HOSTING_180S=0
DEFAULT_60S=1
```

The timeout files are:

```text
tests/test_assembly_program_text_adapter.py
tests/test_assembly_renderer_candidate_readiness.py
tests/test_assembly_text_renderer.py
tests/test_compare_assembly_renderer.py
tests/test_external_jsmn_s3.py
tests/test_m150_renderer_component.py
tests/test_s3_renderer_bootstrap_spike.py
tests/test_s3_renderer_contract.py
tests/test_s3_renderer_event_stream.py
tests/test_s3_renderer_event_writer.py
tests/test_s3_renderer_generic_sign.py
tests/test_s3_renderer_line_blueprints.py
tests/test_s3_renderer_line_encodings.py
tests/test_s3_renderer_line_sequences.py
tests/test_s3_renderer_sign_text.py
tests/test_s3_renderer_simple_call_text.py
tests/test_s3_renderer_text_segments.py
```

## Residual JSMN diagnosis

The residual `tests/test_external_jsmn_s3.py` was not changed in this
campaign. Three fresh 300-second-watchdog processes were run after the
policy T4:

```text
RUN_1_SECONDS=7.237
RUN_1_EXIT=-1073741510
RUN_1_PYTEST_RESULT=NO_TERMINAL_RESULT
RUN_2_SECONDS=26.190
RUN_2_EXIT=-1073741510
RUN_2_PYTEST_RESULT=NO_TERMINAL_RESULT
RUN_3_SECONDS=130.917
RUN_3_EXIT=0
RUN_3_PYTEST_RESULT=18 passed
WATCHDOG_TIMEOUT=NO
CLASSIFICATION=HOST_SCHEDULING_VARIANCE
```

The two process exits are Windows `0xC000013A`, not pytest failures. Their
presence prevents a stable bounded-pass conclusion. The one successful run
also exceeds the applied 60-second T4 budget. The residual remains a release
blocker; it was not reassigned or hidden after the final T4.

```text
T4_TRIAGE_PASS_IN_ISOLATION=NO_RELEASE_PROMOTION
T4_TRIAGE_PREEXISTING_TIMEOUT=16_EXPLICIT_HEAVY_RENDERER
T4_TRIAGE_ENVIRONMENT_DEFERRED=1_EXTERNAL_JSMN
T4_TRIAGE_REPRODUCIBLE_FAILURE=0
T4_TRIAGE_UNRESOLVED=1_TIMEOUT_RESIDUAL
```
