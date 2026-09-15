# Post-1.0 repository hygiene and S3 1.1 foundation

Date: 2026-09-15

## Stable baseline

```text
PUBLIC_STABLE=v1.0.0
FROZEN_SOURCE=7b3c4a56599fc545b30d81ed2956399a31de0223
FULL_LINEAGE_T4=393/393 PASS
REFERENCE_COMPILER=PYTHON
PYPI_PUBLISHED=NO
```

## Documentation/state cleanup

- README updated from stale `s3-bootstrap 0.7.0` language to the actual `v1.0.0` stable state.
- Installation text now avoids implying PyPI availability.
- The stale root `CAMPAIGN_STATE_RESUME.json` was retired as a compatibility redirect.
- Its exact historical roadmap-1.39-1.50 content was archived under `reports/historical/roadmap-1.39-1.50/`.
- `docs/roadmap/ACTIVE_TRACK.md` now selects `S3_1_1_RELIABILITY_AND_MAINTENANCE`.

## Self-host policy preservation

The durable self-host policy from historical PR #278 was rebased onto current post-1.0 history rather than merging the stale/conflicted PR.

Preserved:

- `docs/selfhost/STATUS.md`
- `docs/selfhost/LESSONS.md`
- `docs/selfhost/REENTRY_CRITERIA.md`
- `docs/selfhost/FUTURE_ARCHITECTURE.md`
- updated `selfhost/README.md`
- deferred-roadmap transition report

Terminal policy:

```text
SELFHOST_STATUS=DEFERRED_RESEARCH_FRONTIER
SELFHOST_BLOCKS_NORMAL_DEVELOPMENT=NO
FULL_SELFHOST_CANONICAL_CANDIDATE=NONE
STAGE1_V4=NOT_AUTHORIZED
```

## Issue cleanup

Closed as implemented:

- #130 — per-loop repeatability analyzer
- #131 — official per-loop repeatability analyzer

The current repository already contains the official analyzer, CLI, deterministic publication, validation, scope separation, noise-aware comparison, and regression tests requested by those issues.

## Pull-request cleanup

Closed as obsolete/review-only/historical without merge:

```text
#5
#227
#228
#229
#249
#259
#267
#268
#269
#270
#271
#273
#274
#275
#276
#277
#278
```

Their branches/history remain preserved. Closing the PRs does not delete the research evidence.

Retained open as explicit research portfolio:

```text
#190 Native policy optimization research
#232 Quantum foundation
#238 Reliability Lab prototype
#240 Accelerator foundation
#242 Embedded foundation
#272 Agent Memory external benchmark laboratory
```

PR #238 is retained only as prototype evidence. S3 1.1 Reliability Lab v2 starts from current `main` and does not merge #238 wholesale.

## Infrastructure debt

Issue #284 tracks two P0 infrastructure tasks:

1. restore GitHub-hosted Actions runner assignment;
2. protect `main` with required checks once runners execute normally.

Current no-step runner failures must not be misclassified as compiler failures or fixed by weakening workflows.

## S3 1.1 foundation

Issue #283 is the new execution ledger.

Selected track:

```text
S3_1_1=RELIABILITY_AND_MAINTENANCE
IMPLEMENTATION_STARTED=NO
PRIMARY_DELIVERABLE=RELIABILITY_LAB_V2
```

The new roadmap requires a real killable subprocess watchdog, deterministic generation, replay, minimization, hosted O0/O1 differential testing, bounded Linux x86-64 differential execution, structured failure taxonomy, and explicit resource limits.

## Production impact

This hygiene/foundation branch changes documentation and project-state metadata only. It does not change compiler semantics, runtime behavior, IR, Assembly, backend code, dependency behavior, or the immutable `v1.0.0` tag.
