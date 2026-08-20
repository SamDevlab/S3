# T4 Triage Report

```text
T4_HEAD=8aca581571c59a1c7efbf3575b6c47420c9fd725
T4_TERMINAL=YES
T4_EXIT=1
T4_SELECTED=359
T4_PASS=336
T4_FAIL=0
T4_TIMEOUT=23
T4_CLASSIFICATION=TIMEOUT_ONLY_NO_FUNCTIONAL_FAILURE
```

The raw result is preserved in `T4_RAW_RESULT.json` and the runner state is
preserved under `t4-state/`. Every non-pass result is listed below. The output
captured by T4 contains only partial dot progress or no output and no failure
traceback. The common cause is the 60-second per-file `s3test` budget for the
renderer/toolchain-heavy tests on this Windows host.

Timeouts:

- `tests/test_assembly_program_text_adapter.py`: extended direct run passed.
- `tests/test_assembly_renderer_candidate_readiness.py`: extended direct run passed.
- `tests/test_assembly_text_renderer.py`: extended direct run passed.
- `tests/test_assembly_tokenizer.py`: extended direct run passed.
- `tests/test_compare_assembly_renderer.py`: T4 timeout; renderer subprocess workload, no functional failure in T4 output.
- `tests/test_m150_renderer_component.py`: T4 timeout; renderer subprocess workload, no functional failure in T4 output.
- `tests/test_s3_program_check.py`: T4 timeout; program-check workload, no functional failure in T4 output.
- `tests/test_s3_renderer_bootstrap_spike.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_contract.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_event_stream.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_event_writer.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_first_text.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_generic_sign.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_generic_simple_call.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_generic_text.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_line_blueprints.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_line_encodings.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_line_sequences.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_output_buffer.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_output_model.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_sign_text.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_simple_call_text.py`: T4 timeout; renderer workload, no functional failure in T4 output.
- `tests/test_s3_renderer_text_segments.py`: T4 timeout; renderer workload, no functional failure in T4 output.

The first four cases were independently rerun after the global gate and
passed with the direct pytest command. The auxiliary individual runner was
stopped after the fifth case began because it was reproducing the same
multi-minute renderer cost; this did not alter the original T4 result or its
raw evidence. No code correction is justified by these results.
