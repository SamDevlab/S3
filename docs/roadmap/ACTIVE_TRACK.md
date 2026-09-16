# Active S3 project track

Last reviewed: 2026-09-16.

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
S3_1_1_PHASE=R5_TECHNICALLY_COMPLETE_RELEASE_DECISION_PENDING
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

R1 is integrated and provides a fresh killable worker process per executable case with parent-side timeout enforcement, process-tree termination and bounded structured output. Linux dependency-isolated probes demonstrated real hung-child termination. Windows process-tree mechanics were later exercised during the R3 hardening validation; GitHub Actions runner provisioning remains separately unavailable under #284.

R2 is integrated and provides deterministic valid, malformed and mutated source generation, exact source hashing, case metadata and explicit feature/family coverage accounting. Multi-source module generation remains deliberately deferred until a source-bundle transport contract exists.

R3 is complete on hardened `main` source `f16d4a8117dd6d7ceee84b691d6d9bfa1031b390` (tree `ab48220ee35baf88f2f27bdec832af0261517d54`). The post-hardening Linux x86-64 campaign `r3-linux-post-hardening-20260916` ran exactly once with seed `20260915`: 128/128 cases PASS, including hosted O0/O1 for all 128 cases and native O0/O1 for the bounded 16-case shard. Focused reliability validation was 91/91 PASS and the hardening-specific regression selection was 11/11 PASS. There were zero `MISCOMPILE`, `NONDETERMINISM`, `RESOURCE_LIMIT`, `HARNESS_ERROR`, `TIMEOUT`, or `CRASH` outcomes, and no source mutation occurred during execution.

The authoritative post-hardening campaign report SHA-256 is `f749d501a01d7f6f2b13e60d934b0c17dfac3cd3ccafe932ab27bd3e419e54d1`; the evidence manifest SHA-256 is `90ad0bc165d5b3d4fad93aabf5b553ae15c584100cd39dc39472f33196cd1952`. The previous successful Attempt 2 evidence on `a3aa7bd...` is retained as pre-hardening history and is not used as the final R3 certification.

R4 is complete on the dedicated maintenance branch `feat/s3-1.1-r4-r5-reliability-closure-20260916` at implementation head `774849b1303e3fb726c2c4972457bfa88ba3247d`. The deterministic minimizer preserves the exact outcome and failure signature under the frozen 10,000-evaluation bound. Replay bundles are hash-verified before separate minimized output is written. Failure groups, canonical JSON, and Markdown reports use one deterministic ordering model. The focused R4 selection passed, and the full `python -m pytest -q` gate completed with exit code 0. No compiler/runtime semantics changed.

R5 is technically complete on candidate `d277a862223e8d07b39fd9a687dd1ce0651af63b` after one bounded Linux x86-64 campaign: 256/256 PASS, hosted O0/O1 for all 256 cases, and native O0/O1 for the bounded 32-case shard. The campaign report, stdout summary, and empty stderr were preserved with hashes in [`R5_MAINTENANCE_CLOSURE.md`](../../reports/s3-1.1-reliability-20260916/R5_MAINTENANCE_CLOSURE.md). The Windows full regression evidence is reused from the preceding implementation commit because the final commit changed documentation only. Historical v1.0.0 `393/393 PASS` remains a separate immutable baseline. Release and merge decisions are pending and no new release is implied.

The GitHub Actions runs for the branch remain an independent infrastructure failure under issue #284: all 12 jobs ended before any workflow step with empty step lists. No rerun or workflow weakening was performed.

## Immediate priorities

1. Preserve the completed post-hardening R3 evidence and keep issue #283 synchronized with the exact execution provenance.
2. Keep GitHub Actions runner restoration and `main` protection tracked independently under #284; do not weaken workflows to obtain a green status.
3. Obtain an explicit release decision for the technically complete R5 candidate; preserve historical v1.0.0 evidence as a separate baseline.
4. Keep the v1.0.0 tag and release immutable; no PyPI publication or self-host re-entry is implied by R5 completion.

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

GitHub Actions jobs have been failing before any step is assigned (`runner_id=0`, empty step list). That condition is infrastructure/provisioning debt, not a demonstrated compiler regression, and must not be hidden by weakening workflows. The successful R3 certification came from explicit Windows-authenticated source verification plus exact-commit/tree execution on the Ubuntu x86-64 VM, not from GitHub Actions.

## Next operational step

R3 is closed. R4 and R5 are technically complete on the dedicated branch. Release and merge remain separate decisions pending explicit authorization.
