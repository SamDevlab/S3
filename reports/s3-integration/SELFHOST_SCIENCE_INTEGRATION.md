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

## Full-Suite Evidence

The source freeze remained `d064c17ea811ab926df515cb90884e8c6efffb3d` throughout. Two full-suite invocations are preserved because the first used a source archive without Git metadata and the campaign's one permitted retry corrected that harness condition.

1. `full-suite-no-git-harness-attempt.txt.gz`: exit 1. This run used an extracted archive without `.git`; tests requiring `git show HEAD:<path>` and Git commit metadata failed. The transcript records 8 failed tests and 113 errors. It is not valid candidate evidence. SHA-256 of the original transcript bytes: `b6d74f73041471c40d8de0fd2bdfdba674a480382f20aa9ab327f112c429e071`; SHA-256 of the gzip artifact: `cff381f369317323b23d79996d5538506ccae4eacdaaf2fd2c950802aa1a6d5a`.
2. `full-suite-git-checkout-tmpfs-attempt.txt.gz`: a clean Git checkout at the exact source freeze; exit 1. The only reported failure was `tests/test_s3bench_cross_language.py::test_available_external_toolchains_match_one_checksum`: Zig could not create a compilation because the VM's `/tmp` tmpfs ran out of space (`NoSpaceLeft`). This is an environment-capacity failure; no source defect was established. SHA-256 of the original transcript bytes: `c82132ef1ed9a213b929f9517113e36f86e18878bbbddab53c89436bcf9cb5d9`; SHA-256 of the gzip artifact: `f6df23b62475bc4fc4fba0c48ef7546363e4ba0d77aa7516744d8c19ac1759d7`.

The quiet pytest output did not provide exact passed/skipped/subtest totals. No further full-suite run is authorized or performed in this snapshot. The focused Linux transcript is `focused-linux-d064c17.txt`.

## Publication and Gate

This report captures the local evidence before the integration branch is published. Natural GitHub Actions status must be read from the Draft PR after publication. A local full-suite pass has **not** been established; therefore this candidate is blocked for merge readiness regardless of CI outcome. No merge, default change, tag, release, or production promotion is authorized.

Human merge gate: **NO** until the Linux full suite can complete on the unchanged source candidate with adequate temporary storage.
