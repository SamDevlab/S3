# Final M1.81-M1.90 Publication Certification

This report preserves the completed local campaign evidence and records the
post-PR-review correction line separately. Historical test results are not
rewritten by the later source corrections.

## Historical certified campaign evidence

The pre-review source candidate `546bc096ea3c125d8a4271f61fc31dffc5c6b750`
passed the established local gates:

- compileall: PASS;
- focused: 97 selected, 96 passed, 0 failed, 1 optional `cryptography` skip;
- cross-layer: 8 files, exit 0;
- smart affected gate: 14 passed, 0 failed, 0 timeout;
- Ed25519 provider execution: DEFERRED because `cryptography` was unavailable;
- Linux AArch64 native execution: DEFERRED_BY_ENVIRONMENT;
- macOS ARM64 native execution: DEFERRED_BY_ENVIRONMENT.

The publication T4 was run exactly once and remains exactly:

- selected: 359;
- pass: 336 files;
- fail: 1 file;
- timeout: 22 files;
- exit: 1.

The failing JSMN O1 node was rerun three times with fresh state and passed 3/3,
so it is classified `TRANSIENT_NON_REPRODUCIBLE`. All 22 timeout files were
independently triaged: 12 `PASS_IN_ISOLATION`, 10
`PREEXISTING_EXPENSIVE_TEST`, 0 reproducible failure, and 0 unresolved. The
original T4 result is not converted to green and was not rerun.

The independent benchmark campaign at
`fbf53a0eb8cf39ed0245438b6b47dfde63658b20` recorded 10 correctness PASS and
1 DEFERRED, with smoke classified `CHARACTERIZATION_ONLY`. Channels correctness
covers capacities 1/8/64. No full comparative benchmark result was published.

## Final PR review findings and corrections

A later final source review of PR #183 found two HIGH and three MEDIUM issues.
The publication branch now contains source/test corrections for all of them.
The correction source/test line through `2e20c4af260bc6e4a3e7faa3b4368e36c8982120`
contains:

1. **M1.88/M1.89 typed AAPCS64 lowering** — `AssemblyType.F64` now uses the
   floating-point ABI class for parameters, calls, helper calls, results,
   constants, moves, and returns. Mixed integer/floating signatures allocate
   x/d register classes independently. Structural Linux/macOS tests cover the
   typed ABI path.
2. **M1.90 fail-closed bundle verification** — verification now requires exact
   manifest membership, rejects duplicate/non-canonical/non-regular archive
   members, applies file-count and total-uncompressed-byte limits, validates a
   strict manifest schema, binds LICENSE size/hash, rejects manifest divergence,
   and checks every listed payload hash/size. M1.80 and M1.90 adversarial tests
   cover extras, duplicate members, canonical-path abuse, LICENSE tampering,
   manifest divergence, and oversize content.
3. **M1.85 HTTP hardening** — the socket transport uses one monotonic deadline
   across connect/TLS/send/receive and request headers/hosts fail closed on
   unsupported non-ASCII V1 input.
4. **M1.86 canonical registry origin** — DNS-style authorities are normalized
   to lowercase before identity/transport use and malformed aliases are
   rejected.
5. **AArch64 native evidence binding** — transition to `NATIVE_CERTIFIED`
   requires an evidence record bound to the exact structural artifact hash,
   executable hash, target, toolchain identity, exit code, and scalar result
   when applicable.
6. **Benchmark documentation reconciliation** — channels and the 10 PASS / 1
   DEFERRED benchmark state are recorded correctly; existing characterization
   is explicitly historical relative to the newer source correction head.

Architecture reports for M1.85, M1.86, M1.88, M1.89, and M1.90 were updated to
match the hardened contracts.

## Required post-review validation

These corrections were applied through the GitHub branch interface. They have
**not** yet been executed in the user's local Windows campaign worktree after
this final review. Therefore the branch is not yet merge-certified solely from
this report.

Do **not** rerun the global T4. The required next gate is bounded to the changed
subsystems plus the existing focused/cross-layer/smart publication gates:

- `python -m compileall bootstrap/s3`;
- `tests/test_m180_toolchain_distribution.py`;
- `tests/test_m185_async_http.py`;
- `tests/test_m186_registry_transport.py`;
- `tests/test_m188_aarch64_integration.py`;
- `tests/test_m189_macos_arm64_integration.py`;
- `tests/test_m190_release_candidate.py`;
- the existing M1.81-M1.90 focused gate;
- affected cross-layer backend/verifier tests;
- the smart affected gate.

The benchmark correctness/smoke subset affected by channels/HTTP/registry/
AArch64/reproducibility should also be rerun against the new S3 head before any
new benchmark characterization is attributed to it.

## Machine-readable status

```text
PR_NUMBER=183
PR_BRANCH=feature/m181-m190-autonomous-20260819
PRE_REVIEW_CERTIFIED_SOURCE_HEAD=546bc096ea3c125d8a4271f61fc31dffc5c6b750
POST_REVIEW_CORRECTION_HEAD_BEFORE_THIS_REPORT=2e20c4af260bc6e4a3e7faa3b4368e36c8982120

HISTORICAL_COMPILEALL=PASS
HISTORICAL_FOCUSED_SELECTED=97
HISTORICAL_FOCUSED_PASS=96
HISTORICAL_FOCUSED_FAIL=0
HISTORICAL_FOCUSED_SKIP=1_OPTIONAL_CRYPTOGRAPHY
HISTORICAL_CROSS_LAYER=8_FILES_EXIT_0
HISTORICAL_SMART_PASS=14
HISTORICAL_SMART_FAIL=0
HISTORICAL_SMART_TIMEOUT=0

PUBLICATION_T4_RUN=YES_EXACTLY_ONCE
PUBLICATION_T4_SELECTED=359
PUBLICATION_T4_PASS=336_FILES
PUBLICATION_T4_FAIL=1_FILE
PUBLICATION_T4_TIMEOUT=22_FILES
PUBLICATION_T4_EXIT=1
PUBLICATION_T4_REWRITTEN=NO
PUBLICATION_T4_RERUN=NO
JSMN_O1_CLASSIFICATION=TRANSIENT_NON_REPRODUCIBLE_3_OF_3_PASS
T4_TRIAGE_PASS_IN_ISOLATION=12
T4_TRIAGE_PREEXISTING_TIMEOUT=10
T4_TRIAGE_REPRODUCIBLE_FAILURE=0
T4_TRIAGE_UNRESOLVED=0

FINAL_REVIEW_HIGH_FOUND=2
FINAL_REVIEW_MEDIUM_FOUND=3
FINAL_REVIEW_LOW_FOUND=1
POST_REVIEW_SOURCE_CORRECTIONS_APPLIED=YES
POST_REVIEW_TESTS_ADDED=YES
POST_REVIEW_LOCAL_EXECUTION=PENDING
POST_REVIEW_GLOBAL_T4_REQUIRED=NO

M188_M189_TYPED_AAPCS64_FIX=APPLIED_PENDING_LOCAL_TEST
M190_FAIL_CLOSED_BUNDLE_VERIFY_FIX=APPLIED_PENDING_LOCAL_TEST
M185_DEADLINE_ASCII_FIX=APPLIED_PENDING_LOCAL_TEST
M186_CANONICAL_ORIGIN_FIX=APPLIED_PENDING_LOCAL_TEST
ARM64_NATIVE_EVIDENCE_BINDING_FIX=APPLIED_PENDING_LOCAL_TEST
BENCHMARK_APPLICABILITY_DOC_FIX=APPLIED

ED25519_PROVIDER=DEFERRED_PROVIDER_UNAVAILABLE
LINUX_AARCH64_NATIVE=DEFERRED_BY_ENVIRONMENT
MACOS_ARM64_NATIVE=DEFERRED_BY_ENVIRONMENT
BENCHMARK_FULL=NO
BENCHMARK_RESULTS_PUBLISHED=NO

M181_M190_READY_FOR_PR=YES_ALREADY_OPEN
M181_M190_READY_FOR_MERGE=NO_PENDING_POST_REVIEW_LOCAL_GATE
MERGE_EXECUTED=NO
TAG_CREATED=NO
RELEASE_CREATED=NO
M1_91_IMPLEMENTATION_STARTED=NO
```

No tag, release, package publication, branch deletion, global T4 rerun, or
M1.91 implementation is authorized by this report.
