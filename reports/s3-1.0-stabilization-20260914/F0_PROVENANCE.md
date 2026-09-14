# F0 — provenance and source-line classification

Date: 2026-09-14

## Anchors

```text
RC2_CERTIFICATION_ANCHOR=db5f4bf10e2066f52bf144d23e6f7db56154e298
MAIN_AT_STABILIZATION_START=ad719f9cf16b5e0de8c084e7f9dbe88db5b39e6c
MAIN_AHEAD_OF_RC2=3
MAIN_BEHIND_RC2=0
```

The exact Git comparison from the RC2 anchor to `main` reports only these paths:

| Path | Class | Production behavior changed? |
|---|---|---|
| `README.md` | documentation | no |
| `CONTRIBUTING.md` | documentation | no |
| `SECURITY.md` | documentation | no |

The three commits are:

1. `044e032a65756686d6aa85bd35e0a7a10781ab61` — `docs: sharpen S3 positioning, architecture and contributor entry points`
2. `b5421c549690e368c1bf99daf94c772a0c0645e9` — `docs: add contribution and validation guide`
3. `ad719f9cf16b5e0de8c084e7f9dbe88db5b39e6c` — `docs: add security reporting policy`

## Classification

```text
POST_RC2_PRODUCTION_DELTA=NONE
POST_RC2_TEST_DELTA=NONE
POST_RC2_TOOLING_DELTA=NONE
POST_RC2_DOCUMENTATION_DELTA=YES
RC2_PRODUCTION_SOURCE_STILL_CANONICAL_IN_MAIN=YES
```

No M2.41+ / Gen3 / experimental self-host train can have entered canonical `main` after RC2 without appearing in this comparison. The actual RC2-to-main delta is documentation-only.

This conclusion applies to production source identity only. The stable-release preparation itself introduces release-scope metadata changes and therefore creates a new final-candidate SHA that must receive its own impact qualification before publication.

## Stabilization branch lineage

Policy branch:

`docs/s3-1.0-final-stabilization-20260914`

Candidate-preparation branch:

`release/s3-1.0.0-candidate-prep-20260914`

The candidate-preparation branch is stacked on the policy branch so that the release execution diff remains explicit and reviewable.

## F0 status

```text
F0_RC2_MAIN_PROVENANCE=PASS
F0_POST_RC2_DELTA_CLASSIFIED=YES
F0_EXPERIMENTAL_TRAIN_IMPORT_DETECTED=NO
F0_FINAL_CANDIDATE_FROZEN=NO
```

`F0_FINAL_CANDIDATE_FROZEN` remains `NO` because release metadata, packaging evidence and any justified release-scope repairs must finish before the one-shot final candidate freeze.
