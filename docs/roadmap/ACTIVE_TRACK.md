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
S3_1_1_PHASE=R3_DIFFERENTIAL_CAMPAIGNS
```

S3 `v1.0.0` is the stable GitHub release of the current reference toolchain line. The active bounded objective is **S3 1.1 — Reliability & Maintenance**.

Reliability Lab v2 is built incrementally from current `main`: deterministic identities and schemas (R0), killable process isolation (R1), deterministic source generation (R2), differential execution and replay (R3), minimization/triage (R4), then bounded maintenance closure (R5).

See [`s3-1.1-reliability-maintenance.md`](s3-1.1-reliability-maintenance.md).

## Stable baseline

```text
V1_0_0_FROZEN_SOURCE=7b3c4a56599fc545b30d81ed2956399a31de0223
V1_0_0_FULL_LINEAGE_T4=393/393 PASS
V1_0_0_RELEASE_BLOCKERS=0
```

The annotated `v1.0.0` tag remains immutable while post-1.0 development continues on `main`.

## Current 1.1 state

R0 is integrated and freezes reliability schemas, outcome taxonomy, deterministic identity rules, worker protocol, watchdog semantics and resource policy.

R1 is integrated and provides a fresh killable worker process per executable case with parent-side timeout enforcement, process-tree termination and bounded structured output. Linux dependency-isolated probes demonstrated real hung-child termination; Windows runtime mechanics and repository integration remain explicit evidence debt while GitHub Actions runner provisioning is unavailable.

R2 is integrated and provides deterministic valid, malformed and mutated source generation, exact source hashing, case metadata and explicit feature/family coverage accounting. Its checked-in compiler-integration tests remain pending repository-capable execution under #284 rather than being represented as an unexecuted PASS.

R3 implementation now owns differential orchestration. Hosted valid cases compare isolated O0 against O1 by canonical result hash. A bounded Linux x86-64 shard adds native O0/O1 through the same frozen worker protocol. Stable cross-path disagreement is `MISCOMPILE`; repeated same-path disagreement is `NONDETERMINISM`. Every non-PASS result can persist a bounded canonical replay bundle. These are implementation claims only until real repository worker campaigns execute.

## Immediate priorities

1. Land R3 differential/replay infrastructure without changing compiler semantics.
2. Execute the checked-in R1/R2/R3 integration suites when repository-capable runner access is restored.
3. Run a real hosted O0 ↔ O1 campaign and a bounded Linux x86-64 differential shard before marking the corresponding R3 evidence gates complete.
4. Restore GitHub Actions runner execution and protect `main` with required checks (#284).
5. Start R4 minimization only after the R3 failure signature/replay contract is integrated.

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

GitHub Actions jobs have been failing before any step is assigned (`runner_id=0`, empty step list). That condition is infrastructure/provisioning debt, not a demonstrated compiler regression, and must not be hidden by weakening workflows.

## Next operational step

Integrate R3 infrastructure, then obtain real hosted and Linux x86-64 campaign evidence. Only actual execution may close the two differential R3 gates; implementation alone is not sufficient.
