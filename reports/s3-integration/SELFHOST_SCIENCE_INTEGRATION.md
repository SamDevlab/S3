# S3 1.x Self-Hosting and Scientific Foundation Integration

## Candidate

- Integration branch: `integration/s3-1.x-selfhost-science`
- Initial integration SHA and source freeze: `d064c17ea811ab926df515cb90884e8c6efffb3d`
- Base `main` at validation and publication preparation: `4c7aaf4ad59fdacdd83f230e11a0bd979081c80a`
- Source identity with PR #309: exact; this campaign adds no executable-source changes.
- Included lineage: PRs #301–#309, from the source frontend through the first scientific RMSD kernel.

| PR | Capability |
| --- | --- |
| #301 | Source frontend |
| #302 | Native identifier expressions |
| #303 | Statement sequences |
| #304 | Native program frontend |
| #305 | Native semantic execution |
| #306 | Typed values |
| #307 | Indexed data |
| #308 | Aggregate references |
| #309 | First scientific RMSD kernel |

Excluded: P2, P2H, the #310 exact-segment experiment, and all instruction-budget promotion. PRs #301–#309 remain open and Draft. PRs #310–#312 were not modified. No benchmarks were run.

## Local Validation

- Windows focused group: passed; `python -m compileall -q bootstrap/s3` passed.
- Linux host: x86_64, Python 3.13.15, pytest 9.1.1.
- Linux `compileall`: passed.
- Linux focused group with `S3_NATIVE_REQUIRED=1`: exit 0. It covered frontend control/registration/types, source frontend, whole-program composition, native frontend/semantic/indexed execution, x86-64, static-text IR, aggregate results, and scientific kernel. The quiet transcript did not report a numeric aggregate.
- `git diff --check`: passed on the clean source candidate.

## Environment Recovery

The Linux VM is `Linux x86_64`. At recovery inspection, `/` and `/home` were on `/dev/sda2` (25 GiB, 100% used, 0 bytes available); `/var/tmp` shared that same filesystem. `/tmp` was a 4,317,220,864-byte `tmpfs`, with 2,233,745,408 bytes available and 1,022,732 free inodes at inspection. Its existing contents included unrelated temporary checkouts and an 845 MiB pytest tree; these were inspected but not removed. The default Zig global cache was `/home/vboxuser/.cache/zig` on the full root filesystem.

The run used a dedicated `tmpfs` scratch area under `/dev/shm/s3-integration-gate-recovery-20260924-01`, created and validated within the same remote session as the suite. Before starting it had 4,317,216,768 bytes available, 1,054,003 free inodes, was owned by `vboxuser`, writable, and had 5.5 GiB of VM memory available. `TMPDIR`, `TEMP`, `TMP`, `ZIG_GLOBAL_CACHE_DIR`, and `ZIG_LOCAL_CACHE_DIR` were pointed into this isolated area. Python's effective temporary directory and Zig's effective global/local cache overrides were verified before pytest started. No old cache, checkout, or user data was deleted; no system mount configuration or VM sizing was changed.

The previous valid-checkout failure was the Zig `NoSpaceLeft` error while `/tmp` was the shared temporary filesystem; the root filesystem was also full while Zig's default global cache was located there. The precise failed allocation was not exposed by Zig, so the recovery addressed both constrained locations rather than claiming one unproven allocation site. The fresh isolated scratch and cache placement removed the environmental constraint for the subsequent run.

## Full-Suite Evidence

The source freeze remained `d064c17ea811ab926df515cb90884e8c6efffb3d`. There was exactly one full-suite run after correcting the environment:

```text
COMMAND=python -m pytest -q
S3_NATIVE_REQUIRED=1
HEAD=d064c17ea811ab926df515cb90884e8c6efffb3d
PLATFORM=Linux 7.0.0-31-generic x86_64, glibc 2.43
PYTHON=3.13.15
PYTEST=9.1.1
ZIG=0.14.1
GCC=15.2.0
GNU_AS=2.46
GNU_LD=2.46
START_UTC=2026-09-24T19:49:50.095832+00:00
CAPTURE_END_UTC=2026-09-24T21:00:08.1983768Z
PASSED=4350
SKIPPED=1
FAILED=0
EXIT=0
```

The repository config supplies `addopts = "-q"` and the command also used `-q`, so pytest emitted progress markers without its usual aggregate summary. Counts above were computed from the captured terminal progress markers: 4,350 pass dots and one skip marker; there were no failure/error markers. Subtest-level totals were not separately emitted and remain unavailable. This is a valid full-suite pass on the exact frozen executable source.

Raw transcript: `reports/s3-integration/evidence/full-suite-final-linux-d064c17.txt`

SHA-256: `74e98bd885edb120d383ae049a404973e92fc341bd0c152a3164502e8aa7f922`

The earlier invalid archive attempt remains preserved in `full-suite-no-git-harness-attempt.txt.gz` (exit 1; missing Git metadata; 8 failures and 113 errors; raw SHA-256 `b6d74f73041471c40d8de0fd2bdfdba674a480382f20aa9ab327f112c429e071`; gzip SHA-256 `cff381f369317323b23d79996d5538506ccae4eacdaaf2fd2c950802aa1a6d5a`). The earlier valid-checkout attempt remains preserved in `full-suite-git-checkout-tmpfs-attempt.txt.gz` (exit 1; Zig `NoSpaceLeft`; raw SHA-256 `c82132ef1ed9a213b929f9517113e36f86e18878bbbddab53c89436bcf9cb5d9`; gzip SHA-256 `f6df23b62475bc4fc4fba0c48ef7546363e4ba0d77aa7516744d8c19ac1759d7`). Those historical transcripts were not overwritten.

## CI Root Cause Audit

The three original natural runs (`36047465499`, `36047465527`, `36047465609`) targeted PR #313 at head `5bdf833bf569b39cd601e6b0958e112d1e17ca06`. They comprise 13 jobs; all 13 had `steps=[]`, `runner_id=0`, and an empty runner name. Their requested hosted labels were `ubuntu-latest` or `ubuntu-24.04`; no job required a self-hosted runner. Job/matrix records were created, so the workflows were parsed and expanded before job provisioning failed. Repository Actions settings report `enabled=true`, `allowed_actions=all`; the owner is a personal account, and the repository has no self-hosted runners.

The failure annotations on all three workflows explicitly state: “The job was not started because recent account payments have failed or your spending limit needs to be increased.” This establishes the supported classification `BILLING_OR_QUOTA`; the annotation does not distinguish which of those two account conditions applies. The account billing endpoint could not be read with the current GitHub CLI authorization because it lacks the `user` scope; no additional scope was requested and no billing setting was changed. Workflow YAML, runner labels, conditions, permissions, Actions enablement, and reusable-workflow references do not explain this failure.

## CI Fix / Validation

```text
CI_CONFIG_CHANGED=NO
CI_FIX_APPLIED=NO
CI_VALIDATION_RERUN=NO
CI_RELEASE_GATE=BLOCKED
```

No workflow/config edit or manual rerun was justified: the recorded blocker is account billing/spending policy, not repository configuration. The Actions gate remains blocked until the account owner resolves the message shown in GitHub Billing & plans. No new CI run was requested from this campaign.

## Final Delivery Gate

```text
PR313=OPEN
PR313_DRAFT=YES
PR313_MERGED=NO
INTEGRATION_BRANCH_HEAD=5bdf833bf569b39cd601e6b0958e112d1e17ca06
INTEGRATION_SOURCE_FREEZE_SHA=d064c17ea811ab926df515cb90884e8c6efffb3d
EXECUTABLE_SOURCE_CHANGED=NO
TEST_SOURCE_CHANGED=NO
LOCAL_INTEGRATION_VALIDATION=PASS
FULL_SUITE_GATE=PASS
GITHUB_CI=BLOCKED_BY_BILLING_OR_QUOTA
GITHUB_CI_REQUIRED_FOR_THIS_MERGE=NO
CI_WAIVER_BY_HUMAN_DECISION=YES
CI_RELEASE_GATE=BLOCKED
STACK_DELIVERY_STATUS=READY_FOR_REVIEW
READY_FOR_HUMAN_MERGE_DECISION=YES
```

GitHub Actions did not pass: it remains blocked by `BILLING_OR_QUOTA`. The owner explicitly accepted the preserved local Linux validation as sufficient for this merge and waived GitHub Actions as a required gate. No workflow/config fix, Actions rerun, benchmark, or research work was performed. This records a human-approved gate waiver, not a CI success.
