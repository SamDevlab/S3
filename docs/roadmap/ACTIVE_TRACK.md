# Active S3 project track

Last reviewed: 2026-09-15.

## Active track

```text
ACTIVE_TRACK=S3_1_1_RELIABILITY_AND_MAINTENANCE
CURRENT_PUBLIC_STABLE=v1.0.0
CURRENT_PRERELEASE=NONE
STABLE_V1_0_RELEASED=YES
REFERENCE_COMPILER=PYTHON
FULL_SELFHOST=DEFERRED_RESEARCH
PYPI_PUBLISHED=NO
S3_1_1_IMPLEMENTATION_STARTED=YES
S3_1_1_PHASE=R0_CONTRACT_FREEZE
```

S3 `v1.0.0` is the stable GitHub release of the current reference toolchain line. The stabilization campaign is complete and the next bounded objective is now selected: **S3 1.1 — Reliability & Maintenance**.

The 1.1 track strengthens the existing compiler before another broad capability train. Its primary deliverable is Reliability Lab v2 with deterministic generation, real subprocess isolation and killable timeouts, differential execution, replay, minimization, and structured triage.

See [`s3-1.1-reliability-maintenance.md`](s3-1.1-reliability-maintenance.md).

## Stable baseline

```text
V1_0_0_FROZEN_SOURCE=7b3c4a56599fc545b30d81ed2956399a31de0223
V1_0_0_FULL_LINEAGE_T4=393/393 PASS
V1_0_0_RELEASE_BLOCKERS=0
```

The annotated `v1.0.0` tag targets the exact frozen source that received the final one-shot full-lineage T4. That tag remains immutable while post-1.0 development continues on `main`.

## Immediate priorities

1. Keep repository documentation and state pointers aligned with `v1.0.0`.
2. Restore reliable GitHub Actions runner execution and then protect `main` with required checks.
3. Retire obsolete review/self-host PRs without deleting their historical branches/evidence.
4. Implement Reliability Lab v2 from current `main`; do not merge the old experimental Reliability Lab PR wholesale.
5. Preserve every real compiler failure as a deterministic regression reproducer.

## Out of scope

The 1.1 track does not automatically authorize:

- Stage1 V4 or another full self-host reconstruction;
- promotion of experimental Gen3/self-host trains;
- Quantum, Accelerator, Embedded, or Agent Memory experiments;
- a new backend or widened platform claim;
- PyPI publication;
- performance claims unsupported by equivalent measurement evidence.

Full self-hosting may re-enter only through the design-first criteria in `docs/selfhost/REENTRY_CRITERIA.md` and a separate explicit decision.

## Infrastructure note

At track selection time GitHub Actions jobs were still failing before any step was assigned (`runner_id=0`, empty step list). That condition is infrastructure/provisioning debt, not a demonstrated compiler regression, and must not be hidden by weakening workflows.

## Next operational step

Complete R0 on the dedicated contract branch, then start R1 from the merged R0 contract. R1 must implement the isolated subprocess worker and prove that a genuinely hung child can be killed and reaped.
