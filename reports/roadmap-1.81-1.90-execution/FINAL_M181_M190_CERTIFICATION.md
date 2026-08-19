# Final M1.81-M1.90 Publication Certification

This is a local publication and readiness record. It does not create a pull
request, merge, tag, release, package publication, or shutdown. The source
candidate was reviewed at `546bc096ea3c125d8a4271f61fc31dffc5c6b750`; the
later report/pre-plan commit is documentation-only and is recorded separately
after commit because a report cannot contain its own commit hash.

## Source review

The final M1.81-M1.90 source was re-read against the campaign contract:

- M1.81 uses executable resumable async IR with explicit suspension and no
  silent synchronous fallback.
- M1.82 preserves move-only Future ownership, module-qualified identities, and
  deterministic generic specialization identities.
- M1.83 keeps admission, active-poll ownership, wake ordering, and
  cancellation serialized and bounded.
- M1.84 streams process output into a shared bounded budget and kills/reaps on
  overflow or timeout.
- M1.85 enforces bounded HTTP framing and certificate-required,
  hostname-checked HTTPS policy.
- M1.86 binds registry origin and digest into immutable cache identity and
  verifies content before exposure.
- M1.87 uses the vetted Ed25519 `cryptography` provider with no home-grown
  production fallback; the provider is unavailable on this Windows host.
- M1.88/M1.89 expose complete AssemblyProgram lowering, ABI, object identity,
  relocation, ELF/Mach-O validation, and explicit native environment status.
- M1.90 validates target-specific release artifacts and Apache-2.0 license
  metadata; publication remains disabled.

No production blocker or high finding was identified by this review. Native
Linux AArch64 and macOS ARM64 execution remain environment deferments, and
the Ed25519 provider test remains deferred rather than converted to PASS.

## Local S3 gates

The exact source candidate passed compileall, the 18-file focused set, the
cross-layer backend/verifier/reference/native group, and the smart affected
runner. The focused set contains 97 collected tests: 96 passed and one
optional cryptography test skipped. Cross-layer platform skips were preserved.

The one new broad T4 was run exactly once as
`M181_M190_CORRECTION_PUBLICATION_T4` in an external temporary state
directory. It selected 359 test files, returned 336 passing files, 1 failing
file, 22 timed-out files, and exit 1. Passing files contain 82 individual
pytest skips. The failing file was
`tests/test_external_jsmn_s3.py`, O1 representative fixture; its focused file
rerun passed with exit 0, so the failure is recorded as transient and not
silently promoted to PASS. The timeout list is preserved in the external T4
log and is not confused with a green full-suite gate.

## Benchmark gates

The benchmark branch was extended with the mandatory channels correctness gate
for capacities 1, 8, and 64. It checks FIFO order, count, SHA-256 checksum,
sender close, receiver drain, and final channel close.

The existing JSMN runner used an explicit `S3_REPO` and completed verify-only
and smoke successfully. One initial aggregated verify exposed a transient
token-capture `None` error; direct O0/O1 fixture checks and the retry passed.
JSMN smoke completed six fixtures with zero blocked fixtures and no native
timings on Windows.

The new campaign correctness gate reports 10 PASS and 1 DEFERRED (Ed25519
provider unavailable), zero failures. The new smoke gate passed as
`CHARACTERIZATION_ONLY` with eight bounded characterization rows; no
comparative performance claim is made and the full benchmark was not run.

| Campaign area | Classification |
|---|---|
| async task, await chain, channels, executor, process I/O, HTTP loopback, registry/cache, reproducibility | executable correctness; local characterization only |
| TLS policy | structural only; no local certificate fixture |
| Ed25519 | deferred; `cryptography` unavailable |
| Linux AArch64 and macOS ARM64 | structural only on Windows; native deferred |

The historical T4 remains unchanged: 359 selected, 336 pass, 0 fail, 23
timeout, exit 1, with `ORIGINAL_T4_RESTARTED=NO`.

## Machine-readable status

```text
M181_M190_RECONCILIATION_STATUS=COMPLETE_LOCAL_CERTIFICATION_WITH_T4_BLOCKER
S3_START_HEAD=de8eb0aae347bd9f331c40931040ae5f7b057759
S3_FINAL_HEAD=546bc096ea3c125d8a4271f61fc31dffc5c6b750
S3_FINAL_HEAD_MEANING=SOURCE_CANDIDATE_CERTIFIED_BEFORE_DOCUMENTATION_COMMIT
S3_WORKTREE_CLEAN=YES_AFTER_FINAL_DOCUMENTATION_COMMIT
COMPILEALL=PASS
FOCUSED_SELECTED=97
FOCUSED_PASS=96
FOCUSED_FAIL=0
FOCUSED_SKIP=1_OPTIONAL_CRYPTOGRAPHY
CROSS_LAYER_SELECTED=8_FILES
CROSS_LAYER_PASS=8_FILES_EXIT_0
CROSS_LAYER_FAIL=0
SMART_SELECTED=14_FILES
SMART_PASS=14
SMART_FAIL=0
SMART_TIMEOUT=0
CRYPTOGRAPHY_PROVIDER=UNAVAILABLE
ED25519_PROVIDER_TEST=DEFERRED
LINUX_AARCH64_NATIVE=DEFERRED_BY_ENVIRONMENT
MACOS_ARM64_NATIVE=DEFERRED_BY_ENVIRONMENT
SEMANTICS_REVIEW=PASS
SAFETY_REVIEW=PASS
BENCHMARK_SPECIAL_CASES=NONE
PUBLICATION_T4_NAME=M181_M190_CORRECTION_PUBLICATION_T4
PUBLICATION_T4_RUN=YES_EXACTLY_ONCE
PUBLICATION_T4_SELECTED=359
PUBLICATION_T4_PASS=336_FILES
PUBLICATION_T4_FAIL=1_FILE
PUBLICATION_T4_TIMEOUT=22_FILES
PUBLICATION_T4_SKIP=82_TESTS_INSIDE_PASSING_FILES
PUBLICATION_T4_EXIT=1
PUBLICATION_T4_FAILURE=tests/test_external_jsmn_s3.py::test_s3_jsmn_representative_fixture_is_stable_across_optimization[O1]
PUBLICATION_T4_FAILURE_FOCUSED_REPRO=NO
M181_M190_BLOCKERS=ONE_TRANSIENT_T4_JSMN_FAILURE_PLUS_22_T4_TIMEOUTS
M181_M190_HIGH_FINDINGS=NONE_AFTER_FOCUSED_REPRO
M181_M190_READY_FOR_PR=NO

BENCH_START_HEAD=c9cb38c41d11dba73403e49d9cf0025422af7de7
BENCH_FINAL_HEAD=fbf53a0eb8cf39ed0245438b6b47dfde63658b20
BENCH_REMOTE_HEAD=ABSENT_BEFORE_AUTHORIZED_PUSH
BENCH_WORKTREE_CLEAN=YES
BENCH_EXECUTABLE_CAMPAIGNS=async_task,await_chain,channels,executor,process_io,http_loopback,registry_cache,reproducibility
BENCH_CHARACTERIZATION_ONLY=async_task,await_chain,channels,executor,process_io,http_loopback,registry_cache,reproducibility
BENCH_PERFORMANCE_ELIGIBLE=NONE_WITHOUT_PINNED_REFERENCE_TOOLCHAIN
BENCH_STRUCTURAL_ONLY=tls_policy,aarch64_structure
BENCH_DEFERRED=signature
JSMN_CORRECTNESS=PASS_AFTER_TRANSIENT_RETRY
JSMN_SMOKE=PASS_6_FIXTURES_0_BLOCKED
M181_ASYNC_CORRECTNESS=PASS
M181_ASYNC_SMOKE=PASS_CHARACTERIZATION_ONLY
M182_FUTURE_CORRECTNESS=PASS
M183_EXECUTOR_CORRECTNESS=PASS
M184_PROCESS_CORRECTNESS=PASS
M185_HTTP_CORRECTNESS=PASS
M186_REGISTRY_CORRECTNESS=PASS
M187_ED25519_CORRECTNESS=DEFERRED_PROVIDER_UNAVAILABLE
M188_LINUX_AARCH64_MODE=STRUCTURAL_ONLY
M189_MACOS_ARM64_MODE=STRUCTURAL_ONLY
M190_REPRODUCIBILITY_CORRECTNESS=PASS
BENCHMARK_CORRECTNESS=PASS_WITH_DEFERRED
BENCHMARK_SMOKE=PASS_CHARACTERIZATION_ONLY
BENCHMARK_FULL=NO
BENCHMARK_RESULTS_PUBLISHED=NO

M191_M200_EXISTING_ROADMAP_FOUND=NO_SUBSTANTIVE_ROADMAP
M191_M200_PREPLAN_CREATED=YES
M191_M200_IMPLEMENTATION_STARTED=NO
M191_ENTRY_CRITERIA_SATISFIED=NO
PUSH_EXISTING_BRANCHES=AUTHORIZED_PENDING_FINAL_STATUS
NEW_CORRECTION_PUSH=NO
PR_CREATED=NO
MERGE_EXECUTED=NO
TAG_CREATED=NO
RELEASE_CREATED=NO
M1_91_IMPLEMENTATION_STARTED=NO
SHUTDOWN=NO
```

The benchmark head line is filled from the actual final benchmark
`git rev-parse HEAD` before the documentation commit. No benchmark report or
result was published.
