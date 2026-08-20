# T4 Failure Triage

Historical raw T4 transcripts remain unchanged. The pre-review timeout set
was compared with the post-review set before the final run; no timeout file was
rerun individually.

## Timeout-set provenance

```text
PREVIOUS_TIMEOUT_COUNT=23
POST_REVIEW_TIMEOUT_COUNT=26
POST_REVIEW_VERIFIED_PREEXISTING_TIMEOUTS=23
POST_REVIEW_NEW_TIMEOUTS=3
POST_REVIEW_RESOLVED_TIMEOUTS=0
```

The 23 files common to the historical and post-review sets were:

```text
tests/test_assembly_program_text_adapter.py
tests/test_assembly_renderer_candidate_readiness.py
tests/test_assembly_text_renderer.py
tests/test_assembly_tokenizer.py
tests/test_compare_assembly_renderer.py
tests/test_m150_renderer_component.py
tests/test_s3_program_check.py
tests/test_s3_renderer_bootstrap_spike.py
tests/test_s3_renderer_contract.py
tests/test_s3_renderer_event_stream.py
tests/test_s3_renderer_event_writer.py
tests/test_s3_renderer_first_text.py
tests/test_s3_renderer_generic_sign.py
tests/test_s3_renderer_generic_simple_call.py
tests/test_s3_renderer_generic_text.py
tests/test_s3_renderer_line_blueprints.py
tests/test_s3_renderer_line_encodings.py
tests/test_s3_renderer_line_sequences.py
tests/test_s3_renderer_output_buffer.py
tests/test_s3_renderer_output_model.py
tests/test_s3_renderer_sign_text.py
tests/test_s3_renderer_simple_call_text.py
tests/test_s3_renderer_text_segments.py
```

The three post-review additions were:

```text
tests/test_decimal_functions.py
tests/test_external_jsmn_s3.py
tests/test_self_hosting_opcode_classifier.py
```

None of those three paths overlaps the TLS test correction or the M1.99
source/benchmark files. No changed-code correlation was established.

## Final T4

The single new T4 used the new test-correction HEAD and produced:

```text
FINAL_T4_HEAD=1808cc560fa52a474d7d1b6d84734abc18585ce8
FINAL_T4_SELECTED_FILES=369
FINAL_T4_PASS_FILES=344
FINAL_T4_FAIL_FILES=0
FINAL_T4_TIMEOUT_FILES=25
FINAL_T4_EXIT=1
FINAL_T4_REPORT=T4-post-tls-20260820-194441.txt
```

Relative to the 23-file historical set, the final 25-file timeout set has 23
verified preexisting files and two timeout files still new relative to that
historical set: `tests/test_decimal_functions.py` and
`tests/test_self_hosting_opcode_classifier.py`. Relative to the immediately
preceding 26-file post-review set, `tests/test_external_jsmn_s3.py` resolved
and no new timeout appeared.

The TLS failure is resolved: the final T4 has zero failed files and
`tests/test_m194_tls_server.py` completed successfully. The 25 timeout files
remain timeout evidence, not PASS. Because the campaign contract does not
authorize accepting a mixed set containing new unverified timeout files, the
release gate remains blocked by timeout policy.

```text
T4_TRIAGE_PASS_IN_ISOLATION=NO_RELEASE_PROMOTION
T4_TRIAGE_PREEXISTING_TIMEOUT=23_VERIFIED
T4_TRIAGE_ENVIRONMENT_DEFERRED=25_ORCHESTRATOR_TIMEOUTS
T4_TRIAGE_REPRODUCIBLE_FAILURE=0
T4_TRIAGE_UNRESOLVED=0_FUNCTIONAL_FAILURES
T4_STATUS=TIMEOUT
T4_STATUS_REASON=TIMEOUT_POLICY_BLOCKER
```
