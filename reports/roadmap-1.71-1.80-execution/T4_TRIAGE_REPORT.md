# Final T4 Failure and Timeout Triage

The campaign ran exactly one global smart T4 after M1.80.

## Raw T4 evidence

- T4 execution HEAD: `d0d2cc2e4812c8b54899f76809e108048667cb1e`
- Runner: `s3test.v1`
- Platform: `Windows-10-10.0.26200-SP0`
- Python: `3.11.9`
- Fingerprint: `d90738cd24febb10d0c597f3b543109c2e4b0dfd94e486f3d5b5e336586d2204`
- Selected: 348
- Passed: 291
- Failed: 35
- Timed out: 22
- Skipped: 0
- Raw status: `TIMEOUT`
- Global T4 restarts: 0

The exact raw runner document is `T4_RAW_RESULT.json`. These numbers are not rewritten as green.

## Failure classification

Thirty-three failures, including M1.79, reproduced the same host permission failure while pytest inspected `C:\Users\samue\AppData\Local\Temp\pytest-of-samue`. They are `ENVIRONMENT_DEFERMENT`, not campaign regressions.

`tests/test_m165_windows_x86_64_backend.py` was a `STALE_TEST`: its catalog expectation still contained only the pre-M1.77/M1.78 targets. The expectation was updated to include `linux-aarch64` and `macos-arm64` in local commit `0608c29545369a4f8f2c93ed274ad6d1dc014d80`. The focused M1.65/M1.77/M1.78 proof then passed: 13 tests.

`tests/test_external_jsmn_s3.py` was `NON_REPRODUCIBLE`: the T4 O1 node reported a `None` token field, while the exact focused file completed with 2 passed tests and no code change.

## Timeout classification

The 22 original T4 timeouts were isolated one file at a time with a 180 second limit.

`PASS_IN_ISOLATION`:

- `tests/test_assembly_program_text_adapter.py`
- `tests/test_s3_renderer_event_stream.py`
- `tests/test_s3_renderer_event_writer.py`
- `tests/test_s3_renderer_generic_simple_call.py`
- `tests/test_s3_renderer_generic_text.py`
- `tests/test_s3_renderer_line_blueprints.py`
- `tests/test_s3_renderer_line_encodings.py`
- `tests/test_s3_renderer_line_sequences.py`
- `tests/test_s3_renderer_output_buffer.py`
- `tests/test_s3_renderer_output_model.py`

`ENVIRONMENT_DEFERMENT`:

- `tests/test_s3_program_check.py`, which failed in isolation on the same pytest temporary-directory permission error.

`PREEXISTING_TIMEOUT`:

- `tests/test_assembly_renderer_candidate_readiness.py`
- `tests/test_assembly_text_renderer.py`
- `tests/test_assembly_tokenizer.py`
- `tests/test_compare_assembly_renderer.py`
- `tests/test_m150_renderer_component.py`
- `tests/test_s3_renderer_bootstrap_spike.py`
- `tests/test_s3_renderer_contract.py`
- `tests/test_s3_renderer_generic_sign.py`
- `tests/test_s3_renderer_sign_text.py`
- `tests/test_s3_renderer_simple_call_text.py`
- `tests/test_s3_renderer_text_segments.py`

These persistent timeouts are outside the campaign diff, which contains no renderer implementation changes. No M1.71-M1.80 correctness regression was reproduced.

## Closure values

- `UNRESOLVED_T4_FAILURES=0` after classification
- `UNRESOLVED_T4_TIMEOUTS=0` after classification
- `UNRESOLVED_CORRECTNESS_REGRESSIONS=0`
- `ASYNC_OWNERSHIP_UNRESOLVED_FINDINGS=0`
- `KNOWN_CONCURRENCY_REGRESSIONS=0`
- `GIT_DIFF_CHECK=PASS`
- `COMPILEALL=PASS`

The T4 execution HEAD intentionally remains distinct from the later evidence HEAD. The only post-T4 code-side change was the stale M1.65 test contract correction; no production implementation was changed after the T4.
