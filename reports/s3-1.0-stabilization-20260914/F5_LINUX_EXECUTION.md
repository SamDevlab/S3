# F5 Linux Execution

Date: 2026-09-15

## Candidate and delta

```text
EXECUTION_HEAD=58b6f13295703bf7d26b83e41e831aef00f39682
REMOTE_CANDIDATE_HEAD=58b6f13295703bf7d26b83e41e831aef00f39682
BRANCH=release/s3-1.0.0-candidate-prep-20260914
LOCAL_HEAD_MATCHES_REMOTE=YES
POST_WINDOWS_DELTA_CLASSIFICATION=DOCUMENTATION_AND_RELEASE_REPORTS_ONLY
POST_WINDOWS_CHANGED_FILES=reports/s3-1.0-stabilization-20260914/F5_FOCUSED_NATIVE_CERTIFICATION.md,reports/s3-1.0-stabilization-20260914/F6_F7_FREEZE_AND_PUBLICATION_BOUNDARY.md
POST_WINDOWS_PRODUCTION_DELTA=NONE
POST_WINDOWS_TEST_DELTA=NONE
POST_WINDOWS_PACKAGING_LOGIC_DELTA=NONE
POST_WINDOWS_RUNTIME_DELTA=NONE
```

The branch was fetched and fast-forwarded to the exact remote head before
execution. The comparison base was the Windows-certified source head
`779f6ddb0a5a2e55ea57a3c6e07749f150d83455`. The only intervening tracked files
were the two report/policy files listed above; no executable, test, or package
logic changed.

## Host and toolchain

```text
OS=Ubuntu 26.04 LTS (resolute)
ARCH=x86_64
KERNEL=Linux 7.0.0-31-generic
PYTHON_313=3.13.15
PYTHON_312=3.12.14
PYTHON_311=3.11.16
GCC=15.2.0
CLANG=21.1.8
CC=15.2.0
AS=GNU Binutils 2.46
LD=GNU Binutils 2.46
FILE_TOOL=5.46
READELF=GNU Binutils 2.46
PIP=26.2.1 (Python 3.13 environment)
PYTEST=9.1.1
PYTEST_XDIST=3.8.0
CRYPTOGRAPHY=50.0.1
```

Python 3.11 and 3.12 were installed with `uv` into user-managed locations and
used in separate temporary virtual environments. No system Python or OS
packages were modified. All three interpreters installed the candidate with
the development and crypto extras.

## Sanity and focused gates

```text
GIT_DIFF_CHECK=PASS
COMPILEALL=PASS
RELEASE_FOCUSED=57 passed, 0 failed, 0 skipped, exit 0
LINUX_NATIVE_CORE=176 passed, 0 failed, 0 skipped, exit 0
NATIVE_REQUIRED_ENV=S3_NATIVE_REQUIRED=1
NUMERIC_NATIVE=37 passed, 0 failed, 0 skipped, exit 0
SSA_VERIFIER=49 passed, 0 failed, 0 skipped, exit 0
DIFFERENTIAL=12 passed, 0 failed, 0 skipped, exit 0
GOLDEN_INSPECT=PASS (4 examples checked)
```

The release-focused and native-core commands were each executed twice: the
first execution passed, and a second output-explicit execution confirmed the
exact counts above. Both native-core executions used
`S3_NATIVE_REQUIRED=1`; the final confirmation completed in 311.49 seconds.

## Current workflow matrix

The groups below follow `.github/workflows/tests.yml` at `EXECUTION_HEAD`.
Every pytest group exited zero; no selected test was skipped.

| CI group | Local equivalent | Result |
| --- | --- | --- |
| `ssa-per-pass-verification` | `test_ssa_per_pass_verification.py` + `test_differential_correctness_matrix.py` | 49 passed |
| Python 3.11 unit | Workflow unit filter | 2,765 passed in 761.80s |
| Python 3.12 unit | Workflow unit filter | 2,765 passed in 735.23s |
| Python 3.13 unit | Workflow unit filter | 2,765 passed in 625.32s |
| Python 3.13 renderer | `renderer or adapter or fixture_output` | 361 passed in 3,068.60s |
| Python 3.13 benchmark | `benchmark or lehmer or prime` | 151 passed in 42.57s; 80 warnings |
| `native-x86-64` | Three required native modules, `S3_NATIVE_REQUIRED=1` | 176 passed |
| `numeric-domain-closure` | Five required numeric modules, `S3_NATIVE_REQUIRED=1` | 37 passed |
| `differential-generated` | Deterministic generation + differential harness | 12 passed |
| Benchmark smoke | `runtime.scalar.accumulate.v1`, S3 emulator, O0, shared-ci | PASS; correctness verified |
| Benchmark smoke schema | Four `test_s3bench_*` contract modules | 38 passed |
| Golden inspect (unit-job step) | `python tools/golden_inspect.py check` | PASS; 4 examples checked |

The focused release-impact gate also passed with 57 tests. The functional
benchmark smoke output is local/ignored and is not included in the commit. It
does not make a performance comparison or speedup claim.

## Totals and disposition

The total below counts pytest case executions, including deliberate repeated
release-focused/native confirmation runs and per-interpreter CI matrix
executions; repeated cases are counted again because they were executed again.

```text
TOTAL_TESTS_EXECUTED=9409
TOTAL_FAILURES=0
TOTAL_SKIPS=0
UNCLASSIFIED_FAILURES=0
BENCHMARK_GROUP_WARNINGS=80
ENVIRONMENT_DEFERMENTS=NONE
F5_NORMAL_MATRIX=PASS
F5_LINUX_X86_64_NATIVE=PASS
F5_READY_FOR_F6_FREEZE=YES
```

The benchmark smoke is functional validation only. No full-lineage T4 was run.
No candidate freeze, PR merge, tag, release, or PyPI publication was performed.

```text
FINAL_T4_RUN=NO
F6_CANDIDATE_FROZEN=NO
TAG_CREATED=NO
RELEASE_CREATED=NO
PYPI_PUBLISHED=NO
```
