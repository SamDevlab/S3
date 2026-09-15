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
S3_1_1_PHASE=R2_DETERMINISTIC_GENERATION
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

R1 is integrated and provides one fresh killable subprocess boundary per executable case, parent-side monotonic timeout enforcement, bounded output capture and structured worker results. Linux focused probes demonstrated termination of a genuinely hung child and its descendant process. Windows process-tree runtime evidence and real repository integration remain explicit infrastructure evidence debt while GitHub Actions runner provisioning is unavailable.

R2 implements deterministic valid, malformed and mutated source generation with explicit source hashes, case metadata and feature/family coverage accounting. Frozen identity vectors were independently reproduced. The generated valid syntax is taken from the stable 1.0 language surfaces rather than inventing a generator-specific dialect. Real `compile_source(...)` integration parametrizations are checked in and remain pending repository-capable execution because issue #284 is still open.

## Immediate priorities

1. Merge R2 after review of deterministic vectors, coverage accounting and explicit integration evidence debt.
2. Start R3 differential orchestration from merged R0/R1/R2 contracts: hosted O0 ↔ O1 first, then a bounded Linux x86-64 shard.
3. Restore GitHub Actions runner execution and then protect `main` with required checks (#284).
4. Preserve every real compiler failure as a deterministic replay bundle and regression reproducer.
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

Complete R2 integration, then implement R3 differential campaign orchestration using the isolated R1 worker. R3 result claims require real worker execution and may not be inferred from generator correctness alone.
