# Post-P7 lab hardening reconciliation

## Purpose

PR #177 hardened the long-lived research lab: provenance rules, explicit
source-of-truth precedence, missing durable notes, experiment references, a
historical roadmap label, and structural/provenance validation. It was created
before P7 finished, so the old snapshot was reconciled against the current P7
research checkpoint instead of being merged blindly.

## Final anchors

```text
P7_IMPLEMENTATION_HEAD=b118917ec5a5284899d27b1838712b2e04364caf
P7_MERGE=631b51e70562a33183ac14d0be5bbe2ddd140779
PR177_ORIGINAL_HEAD=c9b06a30e831ad6a5bf468efb0c7c0a4b7cc97dd
PR177_RECONCILED_HEAD=1232feceac24b2dfe5d3f6538da9151dc2e7d4cc
PR177_MERGE_COMMIT=1bae2ec50ea8868b9c5e4c6be2ce3b72672f56cc
RESEARCH_HEAD_AFTER_PR177=1bae2ec50ea8868b9c5e4c6be2ce3b72672f56cc
TARGET_MAIN_SHA=631b51e70562a33183ac14d0be5bbe2ddd140779
```

The PR was merged normally into `research/zettelkasten-lab-20260812`, never
into `main`. The eight paths changed by the P7 checkpoint had empty file
intersection with the original 17 PR #177 paths.

## Restored and preserved

Restored Zettels: `S3-ZK-0032` through `S3-ZK-0038` and `S3-ZK-0044` through
`S3-ZK-0048`, 12/12. P7 `S3-ZK-0049` and `S3-EXP-0026` were preserved.
`S3-EXP-0016-dynamic-observer-aware-initialization.md` was restored with bounded
status `SUPPORTED_FOR_OBSERVABILITY / NECESSITY_OPEN`.

Post-merge census: 49 note files, 49 unique indexed IDs, 0 missing, 0
duplicates. The experiment registry has 11 explicit references and 0 missing
files. `STATE.json` now accurately records `zettel_count=49`.

## Validation

```text
POST_MERGE_STRUCTURAL_VALIDATION_EXIT=0
POST_MERGE_PROVENANCE_VALIDATION_EXIT=0
TARGET_HEAD_MATCH=YES
VALIDATOR_NEGATIVE_CONTROLS=A-E PASS
STATE_SEMANTIC_CONSISTENCY=PASS
P7_STATE_PRESERVED=YES
P8_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
```

The validator self-audit found one narrow defect: structured INDEX duplicate
rows were not checked because all ID occurrences were collapsed into a set. It
was corrected without changing the note schema; disposable controls for
missing notes, duplicate note files, malformed STATE, missing experiment
references, and wrong production SHA all returned non-zero.

## Scope boundary

No production code, tests, workflows, `main` commit, or main PR was changed.
The research branch's `bootstrap/` remains explicitly non-authoritative for
current production. P8 was not started and shutdown remains unauthorized.
