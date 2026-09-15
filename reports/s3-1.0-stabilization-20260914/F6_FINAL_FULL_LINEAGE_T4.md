# F6 Final Full-Lineage T4

Date: 2026-09-15

## Frozen candidate and run identity

```text
DATE=2026-09-15
FROZEN_SOURCE_SHA=7b3c4a56599fc545b30d81ed2956399a31de0223
FREEZE_ATTESTATION_SHA=17d791548bee982fb941766124cd1473d1a38829
T4_WORKTREE=C:\Users\samue\Downloads\S3\S3-final-t4-20260915
T4_WORKTREE_HEAD_MATCH=YES
T4_WORKTREE_TRACKED_STATUS_BEFORE_RUN=CLEAN
T4_PLATFORM=Windows 11 AMD64
T4_PYTHON=Python 3.13.15 (C:\Users\samue\AppData\Local\Programs\Python\Python313\python.exe)
T4_PYTEST=9.1.1
T4_RUNNER=s3test.v1
T4_PROFILE=full
T4_COMMAND=python tools/s3test.py full --format json --timeout 60 --state-dir .s3-test-state-s3-1.0-final
T4_START_LOCAL=2026-09-15T06:53:54.5464214-03:00
T4_END_LOCAL=2026-09-15T08:24:02.6377398-03:00
T4_START_UTC=2026-09-15T09:53:54.5720137+00:00
T4_END_UTC=2026-09-15T11:24:02.6395379+00:00
T4_AUTHORIZED_INVOCATIONS=1
T4_INVOCATIONS=1
T4_ADDITIONAL_RUNS=0
RESUME_INVOCATIONS=0
PROCESS_EXIT_CODE=0
T4_TERMINAL=YES
```

The frozen-candidate full-lineage run was invoked exactly once and completed
naturally. No tests, resumes, or retries were run after it.

## Result

```text
T4_SCHEMA=s3.smart-test-report
T4_SCHEMA_VERSION=s3.smart-test-report.v1
T4_RUNNER_VERSION=s3test.v1
T4_HEAD=7b3c4a56599fc545b30d81ed2956399a31de0223
T4_FINGERPRINT=bf894779126203151756760b8abcfa4c46d5e24ee39717e51fa0cec2b8f37b0d
T4_SELECTED=393
T4_PASSED=393
T4_FAILED=0
T4_TIMED_OUT=0
T4_UNCLASSIFIED_FAILURES=0
T4_UNCLASSIFIED_TIMEOUTS=0
T4_EXIT_CODE=0
FULL_LINEAGE_T4=PASS
SOURCE_MUTATION_AFTER_FREEZE=NO
```

Both the raw JSON report and the persisted `latest.json` identify the same
schema, runner, full profile, HEAD, fingerprint, and summary. Each contains
393 test rows, all with status `PASS`; there are no unexpected or non-pass
rows. The report summary is `status=PASS`, `failed=0`, and `timed_out=0`.

## Preserved raw evidence

Evidence is retained locally and is not included in the release commit.

```text
RAW_EVIDENCE_DIR=C:\Users\samue\Downloads\S3\S3-final-t4-20260915\reports-local\s3-1.0-final-t4-20260915-065212
RAW_STDOUT_PATH=C:\Users\samue\Downloads\S3\S3-final-t4-20260915\reports-local\s3-1.0-final-t4-20260915-065212\raw-stdout.txt
RAW_STDOUT_SHA256=680ec1f9c01e4d8f485d0f6bba78915e4d9d6b5bea8d5319acb8c9bf09470b4b
RAW_STDERR_PATH=C:\Users\samue\Downloads\S3\S3-final-t4-20260915\reports-local\s3-1.0-final-t4-20260915-065212\raw-stderr.txt
RAW_STDERR_SHA256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
EXIT_STATUS_PATH=C:\Users\samue\Downloads\S3\S3-final-t4-20260915\reports-local\s3-1.0-final-t4-20260915-065212\exit-status.txt
EXIT_STATUS_SHA256=53a8ffa5b78a3457919fce9227782bfff442cde34d000068b1b17e2869f62d6f
STATE_JSON_PATH=C:\Users\samue\Downloads\S3\S3-final-t4-20260915\reports-local\s3-1.0-final-t4-20260915-065212\state-snapshot\latest.json
STATE_JSON_SHA256=e776955a2d9b42f19a75c3a320ba04234c8896f7be578368f37d930bebe6f459
STATE_MD_PATH=C:\Users\samue\Downloads\S3\S3-final-t4-20260915\reports-local\s3-1.0-final-t4-20260915-065212\state-snapshot\latest.md
STATE_MD_SHA256=2fdbb4a0f488930523afcc7c47c2138995ae9bb2fc9ad086d380c901aa303a82
SHA256_MANIFEST_PATH=C:\Users\samue\Downloads\S3\S3-final-t4-20260915\reports-local\s3-1.0-final-t4-20260915-065212\sha256-manifest.txt
SHA256_MANIFEST_SHA256=25baa79e6bfcb494f818a3c55b26ad4e95e282ab0ba72cec71040398f1167b58
```

The run metadata file records the command, candidate identity, host, and raw
evidence paths. The SHA-256 manifest was written after the process completed;
it hashes the already persisted stdout, stderr, exit status, and copied state
snapshots. No evidence file was interpreted before those files and hashes
were preserved.

## Disposition and publication boundary

```text
F6_FINAL_T4=PASS
S3_1_0_FINAL_CANDIDATE=READY
UNRESOLVED_RELEASE_BLOCKERS=0
STABLE_RELEASE_AUTHORIZATION=PENDING_HUMAN_DECISION
F7_PUBLICATION_AUTHORIZED=NO
MERGE=NO
TAG_V1_0_0=NO
GITHUB_RELEASE_V1_0_0=NO
PYPI_PUBLISHED=NO
```

This report attests the full-lineage result for the frozen source SHA. It does
not authorize merging PR #281 or any stable publication action.
