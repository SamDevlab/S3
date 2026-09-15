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
S3_1_1_PHASE=R1_ISOLATED_RUNNER
```

S3 `v1.0.0` is the stable GitHub release of the current reference toolchain line. The stabilization campaign is complete and the active bounded objective is **S3 1.1 — Reliability & Maintenance**.

The 1.1 track strengthens the existing compiler before another broad capability train. Reliability Lab v2 is being built from current `main` with deterministic generation, real subprocess isolation and killable timeouts, differential execution, replay, minimization, and structured triage.

See [`s3-1.1-reliability-maintenance.md`](s3-1.1-reliability-maintenance.md).

## Stable baseline

```text
V1_0_0_FROZEN_SOURCE=7b3c4a56599fc545b30d81ed2956399a31de0223
V1_0_0_FULL_LINEAGE_T4=393/393 PASS
V1_0_0_RELEASE_BLOCKERS=0
```

The annotated `v1.0.0` tag targets the exact frozen source that received the final one-shot full-lineage T4. That tag remains immutable while post-1.0 development continues on `main`.

## Current 1.1 state

R0 is integrated and froze the reliability schemas, taxonomy, deterministic identity rules, worker protocol, parent watchdog contract, and default resource policy.

R1 implements the isolated worker/parent boundary. Linux-local focused probes verify a genuinely hung child and its descendant process tree can be terminated and the direct child reaped. Real repository integration tests are checked in; GitHub-hosted execution remains blocked by the independent runner-provisioning issue #284, and Windows process-tree runtime evidence remains explicit rather than being fabricated.

## Immediate priorities

1. Complete R1 integration without broadening compiler behavior.
2. Begin R2 deterministic valid/malformed generation only from the merged R0/R1 contracts.
3. Restore GitHub Actions runner execution and then protect `main` with required checks (#284).
4. Preserve every real compiler failure as a deterministic regression reproducer.
5. Keep historical Reliability Lab PR #238 as prototype evidence only; do not merge it wholesale.

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

GitHub Actions jobs continue to fail before any step is assigned (`runner_id=0`, empty step list). That condition is infrastructure/provisioning debt, not a demonstrated compiler regression, and must not be hidden by weakening workflows.

## Next operational step

Merge R1 after review of the focused isolation evidence, then start R2: deterministic grammar-aware valid generation, malformed generation/mutation, source hashing, case metadata, and explicit coverage accounting.
