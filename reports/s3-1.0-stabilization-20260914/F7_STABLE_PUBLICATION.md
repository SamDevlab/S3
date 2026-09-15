# F7 Stable Publication — S3 v1.0.0

Date: 2026-09-15

## Authorization and publication boundary

The user explicitly authorized stable GitHub publication of S3 `v1.0.0`, including the required merges, creation of the `v1.0.0` tag, and GitHub Release publication.

PyPI publication was explicitly excluded from that authorization and remains not performed.

## Certified source identity

```text
FROZEN_SOURCE_SHA=7b3c4a56599fc545b30d81ed2956399a31de0223
FINAL_T4_ATTESTATION_SHA=b64156f9298f74e99c87caf36bc409cf1fb99fbb
FULL_LINEAGE_T4=PASS
T4_SELECTED=393
T4_PASSED=393
T4_FAILED=0
T4_TIMED_OUT=0
UNRESOLVED_RELEASE_BLOCKERS=0
```

The annotated release tag targets the exact frozen source SHA that received the final one-shot T4 certification.

## Integration

The stabilization policy PR #280 was merged to `main`.

The release-candidate PR #281 was then retargeted to `main`, marked ready for review, and merged. Its merge commit is:

```text
PR_281_MERGE_SHA=b2c01f1a34916968ab89d45db7a3ebcf218d8328
```

The later merge/report commits do not replace the certified source identity; `v1.0.0` intentionally targets the frozen source commit rather than a post-certification documentation merge commit.

## Tag

```text
TAG=v1.0.0
TAG_TYPE=ANNOTATED
TAG_OBJECT_SHA=c2dfc158db851ad779095ecf8329db58c36ce80d
TAG_TARGET_SHA=7b3c4a56599fc545b30d81ed2956399a31de0223
TAG_CREATED=YES
```

## GitHub Release

```text
GITHUB_RELEASE_NAME=S3 v1.0.0
GITHUB_RELEASE_TAG=v1.0.0
GITHUB_RELEASE_ID=389402520
GITHUB_RELEASE_PUBLISHED_AT=2026-09-15T19:07:34Z
GITHUB_RELEASE_PRERELEASE=NO
GITHUB_RELEASE_DRAFT=NO
GITHUB_RELEASE_ASSET_COUNT=0
GITHUB_RELEASE_CREATED=YES
```

## Registry state

```text
PYPI_AUTHORIZED=NO
PYPI_PUBLISHED=NO
OTHER_PACKAGE_REGISTRY_PUBLICATION=NO
```

## Terminal F7 state

```text
F0=PASS
F1=PASS
F2=PASS
F3=PASS
F4=PASS
F5=PASS
F6_FREEZE=PASS
FULL_LINEAGE_T4=PASS
F7_STABLE_GITHUB_PUBLICATION=PASS
S3_V1_0_0_GITHUB_RELEASED=YES
UNRESOLVED_RELEASE_BLOCKERS=0
PYPI_PUBLISHED=NO
```

The S3 1.0 stabilization campaign is complete for GitHub publication. Future work starts from a post-1.0 maintenance / roadmap-selection state. Full compiler self-hosting remains a deferred research frontier and does not automatically re-enter the critical path.
