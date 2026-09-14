# F6/F7 — final candidate freeze and publication boundary

Date: 2026-09-14

Status: **PREPARED / NOT AUTHORIZED FOR EXECUTION**.

This document defines the final release transition without executing it.

## Preconditions for F6

The candidate may not be frozen until all of the following have executable evidence:

```text
F3_PACKAGE_INSTALL_REPRO=PASS
F4_SECURITY_SUPPLY_CHAIN=PASS_OR_EXPLICIT_PROVIDER_DEFERMENT_WITH_FAIL_CLOSED_EVIDENCE
F5_FOCUSED_CURRENT_EQUIVALENT=PASS
F5_NATIVE_X86_64_REQUIRED=PASS_WHERE_REQUIRED_ENVIRONMENT_AVAILABLE
UNCLASSIFIED_FAILURES=0
```

Pre-step GitHub Actions runner failures do not satisfy or fail these source gates; they leave them unresolved.

## Freeze procedure

Once prerequisites are green:

1. record exact candidate commit SHA;
2. record complete candidate diff against the stabilization base;
3. record package/version surfaces;
4. record release workflow/test evidence identifiers;
5. verify no experimental Gen3/self-host lineage is imported;
6. mark candidate source immutable for the final confirmation run;
7. record final wheel/sdist identities and package inventory;
8. update draft release notes with the exact frozen SHA but do not publish.

The freeze report must contain:

```text
FINAL_CANDIDATE_SHA=
FINAL_CANDIDATE_DIFF_CLASSIFIED=YES
SOURCE_MUTATION_AFTER_FREEZE=NO
F3=PASS
F4=PASS_OR_ACCEPTED_DEFERMENT
F5=PASS
UNRESOLVED_RELEASE_BLOCKERS=0
```

## Final full-lineage T4

The final T4 is a confirmation gate, not a debugging loop.

It requires a separate explicit authorization after freeze.

When authorized, exactly one final full-lineage run is executed on the frozen candidate. Persist raw status/transcript evidence before interpreting the result.

If that run fails or times out:

- do not automatically retry to obtain green output;
- classify the factual failure;
- keep the candidate not-ready;
- if a source repair is justified, the repair creates a new candidate and invalidates the previous freeze;
- any later full-lineage confirmation requires a new explicit authorization after appropriate recertification.

Until such authorization exists:

```text
FULL_LINEAGE_T4=NOT_RUN
FINAL_T4_AUTHORIZED=NO
```

## Stable-readiness state

Only after the final confirmation passes may the campaign report:

```text
S3_1_0_FINAL_CANDIDATE=READY
FULL_LINEAGE_T4=PASS
UNRESOLVED_RELEASE_BLOCKERS=0
STABLE_RELEASE_AUTHORIZATION=PENDING_HUMAN_DECISION
```

`READY` is not publication.

## F7 publication boundary

Publication is a distinct human-authorized action. A readiness report or green CI must not automatically:

- merge the release candidate;
- create tag `v1.0.0`;
- create a GitHub Release;
- publish wheel/sdist to PyPI or another registry.

If stable publication is explicitly authorized later, execute in this order:

1. verify the authorized SHA still equals the frozen candidate;
2. merge only the reviewed release lineage required by the authorization;
3. create annotated tag `v1.0.0` on the authorized stable commit;
4. create GitHub Release `S3 v1.0.0` from the finalized release notes;
5. verify the public release points to the intended commit;
6. treat package-registry publication as a separately authorized step unless the user explicitly includes it in the same authorization.

## Current state

```text
F6_CANDIDATE_FROZEN=NO
F6_FINAL_T4_AUTHORIZED=NO
F6_FINAL_T4_RUN=NO
F7_STABLE_PUBLICATION_AUTHORIZED=NO
TAG_V1_0_0_CREATED=NO
GITHUB_RELEASE_V1_0_0_CREATED=NO
PYPI_PUBLISHED=NO
```
