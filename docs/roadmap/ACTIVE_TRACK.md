# Active S3 project track

Last reviewed: 2026-09-14.

## Active track

```text
ACTIVE_TRACK=S3_1_0_FINAL_STABILIZATION
CURRENT_PUBLIC_STABLE=v0.7.0
CURRENT_PRERELEASE=v1.0.0-rc2
STABLE_V1_0_RELEASED=NO
REFERENCE_COMPILER=PYTHON
FULL_SELFHOST=DEFERRED_RESEARCH
NEW_FEATURE_TRAIN_BEFORE_V1_0=NO
```

The active goal is to convert the already-certified 1.0 release-candidate line into a deliberately reviewed stable 1.0 candidate, not to add another capability train.

See [`s3-1.0-final-stabilization.md`](s3-1.0-final-stabilization.md) for the release architecture and gates.

## Why

The repository already has an S3 `v1.0.0-rc2` prerelease with a clean 392/392 new-source T4 result, but no stable `v1.0.0` release. The Python distribution metadata still reports `s3-bootstrap 0.7.0`, so version-surface closure is part of the release work rather than something to hide behind the RC tag.

## Out of scope

This active track does not authorize:

- a new language/runtime milestone family;
- merging experimental Gen3/self-hosting trains;
- a Stage1 V4 self-host reconstruction;
- stable tag/release creation;
- PyPI publication;
- weakening native/security/environment deferments.

Those require separate decisions.

## Next operational step

Create a bounded 1.0 stabilization campaign from canonical `main`, freeze the exact candidate lineage, audit version surfaces, packaging and claims, and execute release certification according to repository policy. The final full-lineage T4 must be treated as a one-shot confirmation gate after source freeze.