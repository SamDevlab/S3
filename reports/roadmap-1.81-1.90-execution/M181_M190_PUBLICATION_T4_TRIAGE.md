# M1.81-M1.90 Publication T4 Triage

This is bounded triage of the one publication T4 already executed at the
current campaign line. The global T4 was not rerun.

```text
TRIAGE_HEAD=70148e884cb42dd3b9f18522e23ad528349f833d
CERTIFIED_SOURCE_HEAD=546bc096ea3c125d8a4271f61fc31dffc5c6b750
ORIGINAL_T4_HEAD=546bc096ea3c125d8a4271f61fc31dffc5c6b750
ORIGINAL_T4_SELECTED=359
ORIGINAL_T4_PASS=336
ORIGINAL_T4_FAIL=1
ORIGINAL_T4_TIMEOUT=22
ORIGINAL_T4_EXIT=1
GLOBAL_T4_RERUN=NO
```

## JSMN O1 failure

The exact failing node was run three times serially with fresh basetemp
directories on the current branch. All three completed successfully:

| Run | Exit | Seconds | Classification |
|---:|---:|---:|---|
| 1 | 0 | 6.194 | PASS |
| 2 | 0 | 5.134 | PASS |
| 3 | 0 | 5.353 | PASS |

```text
NODE=tests/test_external_jsmn_s3.py::test_s3_jsmn_representative_fixture_is_stable_across_optimization[O1]
JSMN_O1_REPEAT_RUNS=3
JSMN_O1_REPEAT_PASS=3
JSMN_O1_REPEAT_FAIL=0
JSMN_O1_CLASSIFICATION=TRANSIENT_NON_REPRODUCIBLE
```

The original T4 failure remains recorded as a failure. These three new passes
do not rewrite it.

## Current timeout nodes

Each exact node came from the new T4 log, ran serially with a fresh basetemp,
and received a bounded 180-second individual limit. `exit=null` means the
individual subprocess reached that timeout; it is not a PASS.

### PASS_IN_ISOLATION

| Node | Exit | Seconds | Classification |
|---|---:|---:|---|
| `tests/test_assembly_tokenizer.py` | 0 | 143.484 | PASS_IN_ISOLATION |
| `tests/test_s3_program_check.py` | 0 | 114.395 | PASS_IN_ISOLATION |
| `tests/test_s3_renderer_bootstrap_spike.py` | 0 | 114.533 | PASS_IN_ISOLATION |
| `tests/test_s3_renderer_event_stream.py` | 0 | 153.784 | PASS_IN_ISOLATION |
| `tests/test_s3_renderer_event_writer.py` | 0 | 143.109 | PASS_IN_ISOLATION |
| `tests/test_s3_renderer_generic_simple_call.py` | 0 | 99.418 | PASS_IN_ISOLATION |
| `tests/test_s3_renderer_generic_text.py` | 0 | 91.957 | PASS_IN_ISOLATION |
| `tests/test_s3_renderer_line_blueprints.py` | 0 | 133.907 | PASS_IN_ISOLATION |
| `tests/test_s3_renderer_line_encodings.py` | 0 | 137.029 | PASS_IN_ISOLATION |
| `tests/test_s3_renderer_line_sequences.py` | 0 | 152.914 | PASS_IN_ISOLATION |
| `tests/test_s3_renderer_output_buffer.py` | 0 | 122.936 | PASS_IN_ISOLATION |
| `tests/test_s3_renderer_output_model.py` | 0 | 122.897 | PASS_IN_ISOLATION |

### PREEXISTING_EXPENSIVE_TEST

The following nodes reached the 180-second individual limit on the current
head. All ten also appear in the older historical timeout report. That report
is context only; the classification below is based on the current individual
runs.

| Node | Exit | Seconds | Classification |
|---|---:|---:|---|
| `tests/test_assembly_program_text_adapter.py` | null | 180.019 | PREEXISTING_EXPENSIVE_TEST |
| `tests/test_assembly_renderer_candidate_readiness.py` | null | 180.038 | PREEXISTING_EXPENSIVE_TEST |
| `tests/test_assembly_text_renderer.py` | null | 180.029 | PREEXISTING_EXPENSIVE_TEST |
| `tests/test_compare_assembly_renderer.py` | null | 180.023 | PREEXISTING_EXPENSIVE_TEST |
| `tests/test_m150_renderer_component.py` | null | 180.030 | PREEXISTING_EXPENSIVE_TEST |
| `tests/test_s3_renderer_contract.py` | null | 180.029 | PREEXISTING_EXPENSIVE_TEST |
| `tests/test_s3_renderer_generic_sign.py` | null | 180.037 | PREEXISTING_EXPENSIVE_TEST |
| `tests/test_s3_renderer_sign_text.py` | null | 180.032 | PREEXISTING_EXPENSIVE_TEST |
| `tests/test_s3_renderer_simple_call_text.py` | null | 180.111 | PREEXISTING_EXPENSIVE_TEST |
| `tests/test_s3_renderer_text_segments.py` | null | 180.247 | PREEXISTING_EXPENSIVE_TEST |

No current timeout produced a traceback or functional failure. There were no
environment deferments and no unresolved nodes.

## Classification summary

```text
T4_TRIAGE_TOTAL=23
T4_TRIAGE_PASS_IN_ISOLATION=12
T4_TRIAGE_ENVIRONMENT_DEFERRED=0
T4_TRIAGE_PREEXISTING_TIMEOUT=10
T4_TRIAGE_REPRODUCIBLE_FAILURE=0
T4_TRIAGE_UNRESOLVED=0
T4_TRIAGE_COMPLETE=YES
PUBLICATION_T4_ORIGINAL_EXIT=1
PUBLICATION_T4_REWRITTEN=NO
PUBLICATION_T4_RERUN=NO
```

Focused, cross-layer, and smart gates remain green from the prior exact source
candidate certification. No source blocker or high finding was introduced by
this read-only triage. The original T4 numbers remain unchanged and the
campaign is locally ready for PR review, but no PR or push is performed here.
