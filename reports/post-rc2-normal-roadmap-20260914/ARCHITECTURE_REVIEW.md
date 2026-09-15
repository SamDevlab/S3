# Post-RC2 Normal-Roadmap Architecture Review — 2026-09-14

## Executive decision

The repository's next normal track should be **S3 1.0 final stabilization and publication readiness**, not another language/runtime feature train and not another self-host reconstruction.

```text
DECISION=S3_1_0_FINAL_STABILIZATION
NEW_FEATURE_TRAIN=DEFER_UNTIL_STABLE_DECISION
SELFHOST=DEFERRED_SEPARATE_RESEARCH
STABLE_RELEASE_CREATED=NO
```

## Evidence reviewed

### Main and RC2

Canonical `main` at review start:

`ad719f9cf16b5e0de8c084e7f9dbe88db5b39e6c`

The latest S3 1.0 prerelease is `v1.0.0-rc2`, targeting:

`db5f4bf10e2066f52bf144d23e6f7db56154e298`

Its release evidence records:

```text
T4_SELECTED=392
T4_PASS=392
T4_FAIL=0
T4_TIMEOUT=0
```

RC2 contains the bounded Windows toolchain probe repair and scoped heavy-native integration timeout policy.

### Earlier full-lineage RC gate

The M2.31-M2.40 release-candidate review recorded a frozen tested source, 390/390 full-lineage T4, no unresolved Critical/High findings, and explicit environment/capability deferments. That campaign declared S3 1.0 release-candidate readiness but did not publish stable 1.0.

### Public version surfaces

At review time:

- latest non-prerelease GitHub release: `v0.7.0`;
- prerelease line: `v1.0.0-rc1`, `v1.0.0-rc2`;
- `pyproject.toml`: `s3-bootstrap 0.7.0`;
- no stable `v1.0.0` GitHub release.

This mismatch is not treated as a bug by itself. It is a release-surface decision that must be closed deliberately before stable publication.

### Experimental development trains

The repository also contains later non-main review/development trains, including M2.41-M2.70 frontend/self-hosting work and related review debt. Those lines explicitly preserve Python as reference/default and prohibit implicit promotion to `main`.

They are therefore **not** selected as the normal stable-release lineage by this review.

## Architectural reasoning

S3 has already accumulated a broad language/toolchain surface and two 1.0 release candidates. At this point, adding another feature block before a stable decision would increase the compatibility surface while postponing the already-prepared release boundary.

The correct project move is a feature freeze around the certified RC2 production line and an explicit stable-release gate covering provenance, version surfaces, support claims, installation, reproducibility, security, native evidence and one final full-lineage certification.

This also cleanly separates three concerns:

1. **stable S3 1.0** — reference compiler and certified production surface;
2. **future normal language/runtime development** — starts after the stable decision;
3. **self-host research** — deferred and governed independently, never a release blocker.

## Release-blocking questions to close

Before stable publication, the campaign must answer factually:

1. What exact source commit is the final 1.0 candidate?
2. Are there production-code differences between RC2 and current `main`?
3. Will `s3-bootstrap` distribution metadata move from `0.7.0` to `1.0.0`?
4. Which syntax/IR/Assembly/diagnostic schema versions remain unchanged?
5. Which targets are runtime-certified versus structurally implemented/deferred?
6. Which crypto/TLS/provider claims are actually supported by execution evidence?
7. Do clean wheel/sdist builds install and run correctly?
8. Are release artifacts reproducible according to their existing contract?
9. Is the final security/supply-chain audit green or explicitly deferred where allowed?
10. Does the exact frozen candidate pass one final full-lineage T4 without hidden reruns?

## Deliberate non-goals

This review does not authorize:

- stable `v1.0.0` tag creation;
- GitHub stable release creation;
- PyPI publication;
- merge of Gen3/self-host review trains;
- new self-host implementation;
- M2.41+ feature promotion to canonical `main`;
- reclassification of structural target evidence as runtime support.

## Proposed execution order

```text
F0 provenance/source freeze
  -> F1 version surface closure
  -> F2 support/claim matrix
  -> F3 packaging/install/reproducibility
  -> F4 security/supply-chain review
  -> F5 focused + native impact certification
  -> F6 one final full-lineage T4
  -> F7 explicit human publication decision
```

A source change after F6 invalidates the final candidate and must not inherit the final T4 result.

## Relationship to self-host deferment

The self-host deferment architecture is intentionally independent. If its documentation PR is merged, stable 1.0 should reference that policy. If it is not yet merged, this release track still treats full self-hosting as non-blocking and does not import experimental self-host branches.

## Recommended post-1.0 policy

After stable publication:

- `1.0.x`: bugfix/security/compatibility only;
- review real user/CI/portability evidence during soak;
- plan the next normal feature release only after an explicit roadmap review;
- keep self-host research separate until its design-first re-entry criteria are independently satisfied.

## Result

```text
POST_RC2_REVIEW=COMPLETE
NORMAL_NEXT_TRACK=S3_1_0_FINAL_STABILIZATION
FEATURE_FREEZE_RECOMMENDED=YES
SELFHOST_RELEASE_BLOCKER=NO
STABLE_PUBLICATION_AUTHORIZED_BY_THIS_REVIEW=NO
```