# F6 Final Candidate Freeze

Date: 2026-09-15

## Candidate and provenance

```text
BRANCH=release/s3-1.0.0-candidate-prep-20260914
REMOTE_HEAD_BEFORE_FREEZE=7b3c4a56599fc545b30d81ed2956399a31de0223
FROZEN_SOURCE_SHA=7b3c4a56599fc545b30d81ed2956399a31de0223
F5_EXECUTION_HEAD=58b6f13295703bf7d26b83e41e831aef00f39682
FREEZE_WORKTREE_HEAD_MATCH=YES
```

The frozen candidate was checked out detached in
`S3-f6-final-freeze-canonical-20260915`. The worktree used tracked Git-blob
line endings (`core.autocrlf=false` for the one-time worktree checkout); no
source file was edited.

The complete post-F5 delta is three release-report files only:

```text
reports/s3-1.0-stabilization-20260914/F5_FOCUSED_NATIVE_CERTIFICATION.md
reports/s3-1.0-stabilization-20260914/F5_LINUX_EXECUTION.md
reports/s3-1.0-stabilization-20260914/F6_F7_FREEZE_AND_PUBLICATION_BOUNDARY.md
```

```text
POST_F5_EXECUTION_PRODUCTION_DELTA=NONE
POST_F5_EXECUTION_TEST_DELTA=NONE
POST_F5_EXECUTION_PACKAGING_LOGIC_DELTA=NONE
POST_F5_EXECUTION_RUNTIME_DELTA=NONE
POST_F5_EXECUTION_BACKEND_DELTA=NONE
POST_F5_EXECUTION_SECURITY_OR_DEPENDENCY_DELTA=NONE
```

## Prior gates

```text
F0=PASS_EXCEPT_FINAL_FREEZE
F1=COMPLETE
F2=COMPLETE
F3=PASS
F4=PASS
F5_HOST_INDEPENDENT=PASS
F5_NORMAL_MATRIX=PASS
F5_LINUX_X86_64_NATIVE=PASS
F5_EXECUTION_HEAD=58b6f13295703bf7d26b83e41e831aef00f39682
```

F5 Linux evidence records 9,409 pytest case executions, zero failures, zero
skips, and no unclassified failures. No F5 gate was rerun for F6.

## Source and version checks

```text
PYTHON=3.13.15
GIT_DIFF_CHECK=PASS
COMPILEALL=PASS
RELEASE_VERSION_SURFACE_TESTS=2 passed, exit 0
DISTRIBUTION=s3-bootstrap 1.0.0
SOURCE_SYNTAX=0.6
IR_JSON=0.6.0
S3_ASSEMBLY=0.6.0
S3_DIAGNOSTIC=1.0.0
WASM_COMPILER_IDENTITY=s3-bootstrap-1.0.0
```

The detached candidate had no tracked modifications after validation. Build
outputs remain in the two untracked `dist-freeze-*` evidence directories and
are not part of the attestation commit.

## Final package reconstruction

The final pair was built twice from the frozen SHA with `build 1.6.1`,
isolated build dependency `setuptools 84.0.0`, Python 3.13.15, and
`SOURCE_DATE_EPOCH=1700000000`. Each output directory contains exactly one
wheel and one sdist.

```text
FINAL_WHEEL_NAME=s3_bootstrap-1.0.0-py3-none-any.whl
FINAL_WHEEL_BYTES=433995
FINAL_WHEEL_SHA256=4c8985a4969e48d8c969beef06e208f397dfd15fcb9184d8e6a0ba49717b387c
FINAL_WHEEL_REPRODUCIBLE=PASS

FINAL_SDIST_NAME=s3_bootstrap-1.0.0.tar.gz
FINAL_SDIST_BYTES=692123
FINAL_SDIST_SHA256=5f0965ee52a74f5bd147d696ba7dbab5e61e4a163bbb6dc67209439b8497e6ea
FINAL_SDIST_REPRODUCIBLE=PASS
```

Each A/B pair is byte-identical. Final archive metadata reports package
`s3-bootstrap`, version `1.0.0`. The wheel has 161 entries. The sdist has 570
archive members: 569 regular files plus its top-level directory, matching the
569-file F3 count. Both inventories exactly match the F3-certified inventories. LICENSE
is present in both, README is present in the sdist, and the scan found no
unsafe paths, local build/venv junk, credentials, bytecode, or machine-specific
paths.

The final hashes do not equal the historical Windows F3 hashes:

```text
F3_WHEEL=437037 bytes, SHA256=3b8490c30a09eaa594920462f8c9c9e7267bc270e92ca79e635f593d2ee83d76
F3_SDIST=695713 bytes, SHA256=f295a899d147f7170f4143fb5fa30b9c42b70db10a2d45d60f3a85a34c9f7ae8
FINAL_ARTIFACTS_MATCH_F3=NO
```

The difference was investigated against the preserved F3 archives. There are
no added or removed archive entries. In the wheel, 156 payload entries differ
only in CRLF/LF line endings and the remaining changed entry is `RECORD`, whose
hashes and sizes necessarily follow those payload bytes. In the sdist, all 551
changed regular-file entries are equal after CRLF/LF normalization; there are
no non-line-ending content differences. The F3 Windows-built artifacts carry
CRLF in those source payloads, while this final build uses the exact LF bytes
stored in the frozen Git tree. This is a checkout line-ending difference, not
a source or package-logic delta. Reproducibility and inventory checks pass for
the selected frozen-tree artifacts.

## Clean install and CLI

A new Python 3.13.15 virtual environment installed only the final frozen
wheel (`pip install --no-deps`; the project declares no runtime dependencies).

```text
INSTALLED_METADATA_VERSION=1.0.0
FINAL_CLEAN_INSTALL=PASS
s3 --help=PASS
s3 check examples/first.s3=PASS
s3 run examples/first.s3=PASS (program returned 6)
s3 check examples/static_array.s3=PASS
FINAL_CLI_SMOKE=PASS
```

## Freeze declaration and publication boundary

```text
FINAL_PACKAGE_REBUILD=PASS
FINAL_PACKAGE_REPRODUCIBILITY=PASS
FINAL_PACKAGE_INVENTORY=PASS
FINAL_CLEAN_INSTALL=PASS
FINAL_CLI_SMOKE=PASS
UNRESOLVED_PRE_T4_BLOCKERS=0
F6_CANDIDATE_FROZEN=YES
FROZEN_SOURCE_SHA=7b3c4a56599fc545b30d81ed2956399a31de0223
SOURCE_MUTATION_AFTER_FREEZE=NO

FINAL_T4_AUTHORIZED=NO
FINAL_T4_RUN=NO
MERGE=NO
TAG_V1_0_0=NO
GITHUB_RELEASE_V1_0_0=NO
PYPI_PUBLISHED=NO
```

The candidate SHA above is the pre-attestation source SHA. The commit that
records this report is tracked separately as `FREEZE_ATTESTATION_SHA`; future
final T4 must check out `FROZEN_SOURCE_SHA`, not the moving branch head.

```text
NEXT_ACTION=AWAIT_EXPLICIT_AUTHORIZATION_FOR_EXACTLY_ONE_FINAL_FULL_LINEAGE_T4
```
