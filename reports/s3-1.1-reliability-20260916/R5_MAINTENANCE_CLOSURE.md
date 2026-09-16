# S3 1.1 R5 — Maintenance Closure

Status: **technically complete; release decision pending**.

## Candidate and provenance

```text
BASE_MAIN=11d8ce2e0c80e5d92fb779e8b39f446efdb25120
R5_CANDIDATE_HEAD=d277a862223e8d07b39fd9a687dd1ce0651af63b
R5_CANDIDATE_TREE=3c0fe208aead52ae34f8d63629e7edb0c10c4482
R5_BRANCH=feat/s3-1.1-r4-r5-reliability-closure-20260916
R5_PYTHON=3.13.15
R5_PLATFORM=Linux x86-64
SOURCE_MUTATION_DURING_CAMPAIGN=NO
R5_CAMPAIGN_INVOCATIONS=1
```

The candidate contains the additive R4 Reliability Lab implementation and its
documentation. No compiler, runtime, IR, Assembly, backend, or 1.0.0
production semantics changed. The immutable `v1.0.0` baseline remains the
historical release at `7b3c4a56599fc545b30d81ed2956399a31de0223`.

## Windows regression

The full Windows suite completed with exit code `0` on the R4 implementation
commit `774849b1303e3fb726c2c4972457bfa88ba3247d`. The only commit after that
execution, `d277a862223e8d07b39fd9a687dd1ce0651af63b`, changes documentation
only; the executable and test inputs are byte-identical. This is recorded as
the current candidate regression evidence, not as a new 1.0.0 certification.

```text
WINDOWS_FULL_REGRESSION=PASS
WINDOWS_FULL_REGRESSION_SOURCE=R4_FULL_SUITE_AT_774849B1303E3FB726C2C4972457BFA88BA3247D
WINDOWS_R4_FOCUSED_TESTS=101 passed
WINDOWS_COMPILEALL=PASS
```

## Authoritative R5 campaign

The campaign was invoked exactly once on the exact candidate head:

```text
CAMPAIGN_ID=r5-maintenance-closure-20260916
CAMPAIGN_SEED=20260916
CAMPAIGN_CASES=256
CAMPAIGN_NATIVE_CASES=32
R5_CAMPAIGN_EXIT=0
R5_CASE_RESULTS=256
R5_COUNTS={"PASS":256}
HOSTED_O0=256
HOSTED_O1=256
LINUX_NATIVE_O0=32
LINUX_NATIVE_O1=32
REPLAY_FAILURE_BUNDLES=0
UNCLASSIFIED_FAILURES=0
```

The persisted campaign report is canonical JSON and has SHA-256
`a582a252584027271707986ae634abe1d12ab1ee87b9903d18c0d693e2090258`.
The canonical stdout summary has SHA-256
`b8234e79298d9f2d1bafcc73bd4508225d00501e09ca5848068f11cbf0322c13`; stderr
was empty and has SHA-256
`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`.
The raw files are preserved outside the repository under the
`s3-r5-evidence-20260916` evidence archive.

This campaign is a fresh bounded R5 maintenance campaign. It is not a
replacement for, or a claim of, a new full 1.0.0 `393/393` release T4. The
historical v1.0.0 result remains `393/393 PASS` as the immutable baseline.

## Closure decision

```text
R5_PROCESS_ISOLATION=PASS
R5_HARD_TIMEOUT_WATCHDOG=PASS
R5_DETERMINISTIC_GENERATION=PASS
R5_REPLAY=PASS
R5_MINIMIZATION=PASS
R5_HOSTED_O0_O1_DIFFERENTIAL=PASS
R5_LINUX_X86_64_BOUNDED_DIFFERENTIAL=PASS
R5_UNCLASSIFIED_FAILURES=0
R5_TECHNICALLY_COMPLETE=YES
V1_0_HISTORICAL_T4=393/393 PASS
V1_0_BASELINE_REGRESSION=PASS
FULL_SELFHOST_REENTRY=NO
RELEASE_DECISION_REQUIRED=YES
RELEASE_AUTHORIZED=NO
MERGE_AUTHORIZED=NO
PYPI_PUBLICATION=NO
```

Issue #283 remains open for reliability-track evidence. Issue #284 remains
open for the independent GitHub Actions runner-provisioning problem; no
workflow weakening or issue closure is part of this campaign.

The observed GitHub Actions runs for this branch were classified as
infrastructure failures: all jobs completed in approximately 1-4 seconds
with an empty `steps` list, before any workflow command ran. The observed run
IDs include `35105316275`, `35105316280`, `35105688150`, and `35105687979`.
They were not rerun, and this condition does not invalidate the independent
Windows and Linux evidence above.

```text
GITHUB_ACTIONS_CLASSIFICATION=INFRASTRUCTURE_FAILURE_UNDER_ISSUE_284
GITHUB_ACTIONS_RERUN=NO
```
