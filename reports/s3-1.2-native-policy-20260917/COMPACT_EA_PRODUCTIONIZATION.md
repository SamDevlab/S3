# Compact EA Productionization

BASE_MAIN_SHA=cade1d8834bbb4114a3498ee5914f2dfaf9a9dc8
FINAL_TESTED_SOURCE_HEAD=08b39da37a46b2114193fd4ee10c8b0e7082065b
SOURCE_CHANGED_AFTER_FINAL_GATES=NO

ACTIVE_TRACK=S3_1_2_NATIVE_BACKEND_PRODUCTIONIZATION
CURRENT_PUBLIC_STABLE=v1.0.0
S3_1_1_TECHNICAL_CLOSURE=PASS
S3_1_1_RELEASE_PREP=PARKED

COMPACT_EA_SUPPORTED_OPT_IN=YES
COMPACT_EA_DEFAULT=NO
EXPERIMENTAL_CANARY_RETIRED_OR_SHIMMED=SHIMMED

The native backend now accepts the explicit `compact-ea` policy through
`NativeCodegenPolicy`, `X8664Backend(native_policy=...)`, the public native
generation APIs, FFI build propagation, and the native CLI commands. The
default remains the baseline policy. Compact EA is selected per function only
when the indexed lowering safety conditions are proven; otherwise that
function deterministically falls back to baseline with an explicit reason.

The legacy experimental canary API remains as a compatibility shim and uses
the same centralized safety decision. No semantic, IR, Assembly, ABI, or
self-hosting behavior was changed, and no golden output was changed.

STRUCTURAL_AND_API_GATES=PASS
FOCUSED_WINDOWS_NATIVE_TESTS=PASS
WINDOWS_FULL_SUITE=ONE_ISOLATED_FAILURE
WINDOWS_FULL_SUITE_FAILURE=tests/test_reliability_runner_v2.py::test_r1_timeout_kills_descendant_process_tree
WINDOWS_FAILURE_FOCUSED_REPRODUCTION=PASS
WINDOWS_FAILURE_CLASSIFICATION=TIMING_OR_PROCESS_TREE_ENVIRONMENT_OUTSIDE_THIS_DIFF

LINUX_DIFFERENTIAL_CASES=128
LINUX_DIFFERENTIAL_ELIGIBLE_FUNCTIONS=128
LINUX_COMPACT_EA_APPLICATIONS=256
LINUX_NATIVE_CORRECTNESS=PASS
LINUX_SOAK_PASSES=3
LINUX_SOAK_NONDETERMINISM=0
LINUX_SOAK_DECISIONS_IDENTICAL=YES
LINUX_SOAK_OUTPUT_IDENTICAL=YES

LINUX_FULL_SUITE=PASS
LINUX_FULL_SUITE_EVIDENCE=pytest reached 100% with no failure output
LINUX_FULL_SUITE_WRAPPER_NOTE=outer SSH wrapper exit was unusable because of shell quoting; pytest itself completed without failures

PERFORMANCE_CHARACTERIZATION=NOT_RUN
NATIVE_SPEEDUP_CLAIM=NO
BENCHMARK_SPECIAL_CASES=NONE

PR=296
PR_STATE=OPEN
PR_DRAFT=YES
PR_MERGEABLE=YES
PR_MERGE_STATE=UNSTABLE
CI_RUN=35181318772
CI_HEAD=9090480d27576fdcc0d9a50895aee84b4c93e124
CI_STATUS=INFRASTRUCTURE_BLOCKED
CI_EVIDENCE=all jobs failed in about 2 seconds with steps=[] and no job logs
CI_RERUN=NO

PR190_MERGED=NO
PR295_STATUS=PARKED
ISSUE284_STATUS=OPEN
SELF_HOSTING_CHANGES=NO
RELEASE_OR_TAG=NO
PYPI_PUBLICATION=NO

This report records the implementation evidence for review. The Windows
full-suite timing failure remains visible and is not converted into a skip or
used to weaken the test. The feature branch is not ready for an unconditional
main merge until that environment-sensitive result and the CI infrastructure
failure are reviewed.

## Merge-readiness closure

HEAD_SHA=5267955f50fb436c21365fd72e25cec3a71134b5
HEAD_TREE=b9d1304177a70300f543d3eca5c067d521124060
POST_TESTED_SOURCE_EXECUTABLE_DELTA=NO

FEATURE_HEAD_FOCUSED=PASS
MAIN_FOCUSED=PASS
FEATURE_HEAD_FOCUSED_EXIT=0
MAIN_FOCUSED_EXIT=0

WINDOWS_TIMING_REPRO_RUNS=10
WINDOWS_TIMING_REPRO_PASSED=9
WINDOWS_TIMING_REPRO_FAILED=1
MAIN_TIMING_REPRO_RUNS=10
MAIN_TIMING_REPRO_PASSED=9
MAIN_TIMING_REPRO_FAILED=1
WINDOWS_TIMING_CLASSIFICATION=PREEXISTING_OR_ENVIRONMENTAL_WINDOWS_TIMING_FLAKE
WINDOWS_TIMING_FAILURE_MODE=DESCENDANT_MARKER_SURVIVED_ON_ONE_INVOCATION
TIMING_FIX_REQUIRED=NO_FOR_COMPACT_EA_PR
NO_COMPACT_EA_REGRESSION=YES

WINDOWS_FULL_SELECTED=3374
WINDOWS_FULL_PASSED=3151
WINDOWS_FULL_SKIPPED=223
WINDOWS_FULL_FAILED=0
WINDOWS_FULL_EXIT_CODE=0
WINDOWS_FULL_TRANSCRIPT=scratch/windows-full-compact-ea-closure-20260917.log

LINUX_EVIDENCE_REUSED_BECAUSE_EXECUTABLE_SOURCE_UNCHANGED=YES
LINUX_DIFFERENTIAL=128/128_PASS
LINUX_SOAK=3_PASS
LINUX_NONDETERMINISM=0
LINUX_FULL=PASS
COMPILEALL=PASS
DIFF_CHECK=PASS

The focused timing failure occurred once in ten fresh feature processes and
once in ten fresh `origin/main` processes. The failing assertion observed the
descendant marker after the worker timeout; this is retained as a real
pre-existing Windows process-tree timing/environment result, not relabeled as
a Compact EA failure and not hidden with a skip or xfail. No reliability
runner code was changed in this PR.

The final Windows full suite was run once on the exact current candidate and
completed with zero failures. The feature remains Draft because focused
timing stability is not 10/10 and GitHub Actions is blocked before execution.
