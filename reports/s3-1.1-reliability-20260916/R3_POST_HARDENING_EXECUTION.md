# S3 1.1 — R3 post-hardening execution evidence

Status: **PASS / R3 COMPLETE**

Date: 2026-09-16

## Source identity

```text
EXECUTION_SHA=f16d4a8117dd6d7ceee84b691d6d9bfa1031b390
EXECUTION_TREE=ab48220ee35baf88f2f27bdec832af0261517d54
WINDOWS_ORIGIN_MAIN_SHA=f16d4a8117dd6d7ceee84b691d6d9bfa1031b390
SOURCE_DRIFT=NO
SOURCE_MUTATION_DURING_EXECUTION=NO
```

The private-repository control plane was verified on Windows using authenticated `origin/main`. The Ubuntu VM executed the exact commit/tree object. No GitHub credentials were installed on the VM.

## Remote execution environment

```text
REMOTE_EXECUTION=YES
SSH_HOSTNAME=Ubuntuserve
SSH_USER=vboxuser
PLATFORM=Ubuntu 26.04 LTS
ARCH=x86_64
PYTHON=3.13.15
PYTHON_PATH=/home/vboxuser/.local/share/uv/python/cpython-3.13.15-linux-x86_64-gnu/bin/python3.13
CC=/usr/bin/cc GCC 15.2.0
AS=/usr/bin/as GNU Binutils 2.46
LD=/usr/bin/ld GNU Binutils 2.46
```

Python 3.13.15 was recovered from the already existing user-level `uv` installation and used to create the isolated execution environment.

## Preflight

```text
MODULE_ENTRYPOINT_PROBE=PASS
DIRECT_ENTRYPOINT_PROBE=PASS
DIFF_CHECK=PASS
COMPILEALL=PASS
FOCUSED_SELECTED=91
FOCUSED_PASSED=91
FOCUSED_FAILED=0
FOCUSED_SKIPPED=0
FOCUSED_EXIT_CODE=0
FOCUSED_GATE=PASS
HARDENING_REGRESSION_SELECTED=11
HARDENING_REGRESSION_PASSED=11
HARDENING_REGRESSION_FAILED=0
HARDENING_REGRESSION_GATE=PASS
```

The hardening regression selection covered the post-exit output-overflow classification and native backend error-family separation introduced before this campaign.

## Authorization / invocation accounting

```text
ATTEMPT_3_AUTHORIZED=YES_CONSUMED
ATTEMPT_3_CAMPAIGN_INVOCATIONS=1
ATTEMPT_3_ADDITIONAL_RUNS=0
```

The authoritative campaign was invoked exactly once. No retry or replacement campaign was executed.

## Campaign

```text
CAMPAIGN_ID=r3-linux-post-hardening-20260916
CAMPAIGN_SEED=20260915
CASE_COUNT=128
NATIVE_CASE_COUNT=16
CONFIRMATION_RUNS_PER_PATH=2
TOTAL_RESULTS=128
PASS_COUNT=128
NON_PASS_COUNT=0
CAMPAIGN_EXIT_CODE=0
```

### Hosted differential gate

```text
HOSTED_CASES=128
HOSTED_O0_OBSERVATIONS=128
HOSTED_O1_OBSERVATIONS=128
HOSTED_NON_PASS=0
HOSTED_O0_O1_DIFFERENTIAL=PASS
```

### Linux x86-64 native differential gate

```text
NATIVE_SELECTED=16
NATIVE_O0_OBSERVATIONS=16
NATIVE_O1_OBSERVATIONS=16
NATIVE_NON_PASS=0
LINUX_X86_64_BOUNDED_DIFFERENTIAL=PASS
```

### Outcome accounting

```json
{"PASS":128,"EXPECTED_REJECTION":0,"UNEXPECTED_REJECTION":0,"UNEXPECTED_ACCEPT":0,"MISCOMPILE":0,"CRASH":0,"TIMEOUT":0,"NONDETERMINISM":0,"RESOURCE_LIMIT":0,"HARNESS_ERROR":0}
```

```text
NONDETERMINISM_CASES=0
MISCOMPILE_CASES=0
RESOURCE_LIMIT_CASES=0
HARNESS_ERROR_CASES=0
TIMEOUT_CASES=0
CRASH_CASES=0
REPLAY_BUNDLES=0
REPLAY_MISSING=0
REPLAY_OVERSIZE=0
```

Zero replay bundles are expected for an all-PASS campaign.

## Evidence location and hashes

VM evidence root:

```text
/home/vboxuser/s3-r3-post-hardening-evidence-20260916T095001Z
```

Campaign report:

```text
/home/vboxuser/s3-r3-post-hardening-evidence-20260916T095001Z/campaign.json
```

SHA-256:

```text
CAMPAIGN_REPORT_SHA256=f749d501a01d7f6f2b13e60d934b0c17dfac3cd3ccafe932ab27bd3e419e54d1
CAMPAIGN_STDOUT_SHA256=81c69160abde6d5ee9156e51972466ec042bdd56c0524eeacee70fef65f7106a
CAMPAIGN_STDERR_SHA256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
CAMPAIGN_STATUS_SHA256=9a271f2a916b0b6ee6cecb2426f0b3206ef074578be55d9bc94f6f3fe3ab86aa
ENVIRONMENT_SHA256=b08969cb6c3c3e43314aef14fd7842a23d5cadba4b99f384a6faed4502a96715
PRECHECK_SHA256=19e8b91849e18731bcad6c87062b4d6c6bea7de6955430270a38117f25577ab1
HASH_MANIFEST_SHA256=90ad0bc165d5b3d4fad93aabf5b553ae15c584100cd39dc39472f33196cd1952
```

The raw VM artifacts are not copied into this repository by this bookkeeping change; this report preserves their exact paths and hashes.

## Historical attempt provenance

- Attempt 1 ran on `968982e63e9d7a373432ae27ec78c1ed3b02f9ef` and failed before generated cases due to the direct-entry import defect. Its evidence remains in `reports/s3-1.1-reliability-20260915/R3_EXECUTION_ATTEMPT_1.md`.
- Attempt 2 ran on pre-hardening `a3aa7bd7d7d1177d1f83b0dc3ce861da05dfc3f3` and completed 128/128 PASS including 16 native cases. That evidence remains historical and does not certify the hardened source.
- Attempt 3 is the authoritative post-hardening certification recorded here.

## Conclusion

```text
R3=COMPLETE
R3_UNRESOLVED_FAILURES=0
READY_FOR_R4=YES
R4=NOT_STARTED
R5=NOT_STARTED
```

`READY_FOR_R4=YES` is readiness only. It does not authorize R4 implementation. GitHub Actions runner provisioning remains a separate infrastructure problem tracked under issue #284. Stable `v1.0.0` remains immutable; no release, PyPI publication, or self-host re-entry is implied by this result.
