# S3 Post-1.0 Repository Review

Date: 2026-09-15
Base reviewed: `main` at `5a6fee9d30ef37bf94c861cb3a264c45514fe39f`
Stable release: `v1.0.0`
Certified frozen source: `7b3c4a56599fc545b30d81ed2956399a31de0223`

## Executive conclusion

S3 1.0 is technically mature enough to serve as a stable baseline. The next project risk is no longer missing core compiler functionality; it is repository/infrastructure entropy and choosing the next capability too broadly.

The recommended first post-1.0 development track is **Reliability & Maintenance**, not self-hosting and not another large capability train.

Proposed first 1.1 objective:

```text
S3_1_1_OBJECTIVE=RELIABILITY_AND_MAINTENANCE
LANGUAGE_SEMANTICS_CHANGE=NO
FORMAT_BUMP_REQUIRED=NO
SELFHOST_REENTRY=NO
EXPERIMENTAL_TRAIN_BULK_MERGE=NO
```

The work should first restore trustworthy automation and repository truth, then productionize a deterministic Reliability Lab v2 from the useful ideas in PR #238 using a fresh implementation from current `main`.

## 1. Stable baseline health

The v1.0.0 release is backed by unusually strong evidence for an experimental language project:

- final full-lineage T4: `393 selected / 393 passed / 0 failed / 0 timed out`;
- Python 3.11 / 3.12 / 3.13 matrix closed before release;
- Linux x86-64 required native gate closed;
- package/install/reproducibility and supply-chain gates closed;
- stable GitHub tag targets the frozen candidate rather than a later documentation merge;
- Python remains the reference/default compiler.

Assessment:

```text
CORE_COMPILER_BASELINE=STRONG
RELEASE_PROVENANCE=STRONG
TEST_ARCHITECTURE=STRONG
NATIVE_X86_64_EVIDENCE=STRONG
PACKAGE_SURFACE=STABLE
```

## 2. Immediate repository hygiene findings

### 2.1 README is stale after 1.0

The current README still says the publishable package is `s3-bootstrap 0.7.0` and describes 1.x as an internal line. The actual package metadata is `1.0.0` and the stable GitHub release now exists.

The self-host section also still reads as an incremental active direction rather than explicitly reflecting the deferred research-frontier decision.

Classification:

```text
README_RELEASE_STATE=STALE
SEVERITY=HIGH_DOCUMENTATION
```

### 2.2 General roadmap contains obsolete historical current-state text

`docs/roadmap.md` preserves valuable historical milestones but also includes sections whose "current" state predates work that is already in `main`, including old 0.8/E3 wording.

Historical material should remain, but the document needs a clear distinction between historical milestone narrative and current active state.

Classification:

```text
ROADMAP_HISTORY=VALUABLE
ROADMAP_CURRENT_STATE=PARTIALLY_STALE
```

### 2.3 Root campaign resume file is stale

`CAMPAIGN_STATE_RESUME.json` still describes the old `roadmap-1.39-1.50` / M1.49 state. It must not be used as the current project resume authority.

Recommended action: retire it, rename it as historical evidence, or replace it with a minimal pointer to `docs/roadmap/ACTIVE_TRACK.md` and current post-1.0 state.

Classification:

```text
ROOT_CAMPAIGN_STATE_RESUME=STALE_AND_POTENTIALLY_MISLEADING
```

### 2.4 GitHub Actions remains operationally unavailable

The latest main workflow still fails before any repository step runs:

```text
steps=[]
runner_id=0
runner_name=""
```

This is the same pre-runner provisioning failure class seen during the 1.0 campaign. It is not evidence of a source regression, but it is now the most important infrastructure problem because post-1.0 development should not depend indefinitely on manual local certification.

Classification:

```text
CI_CODE_RESULT=NOT_OBTAINED
CI_OPERATIONAL_HEALTH=BLOCKED_PRE_RUNNER
POST_1_0_PRIORITY=P0
```

### 2.5 Main is not protected

GitHub currently reports `main` as unprotected with required status checks disabled.

For a repository that now has a stable release baseline, this is too permissive.

Recommended policy once Actions is usable again:

- require PRs for production-code changes;
- block force pushes/deletion of `main`;
- require the normal test/native gates when the runner is operational;
- preserve an emergency release/admin path without weakening ordinary development.

Classification:

```text
MAIN_BRANCH_PROTECTION=ABSENT
POST_1_0_PRIORITY=P0
```

## 3. Issue review

There are four open non-PR issues.

### #130 and #131 — repeatability analyzer

These appear complete in current main. The repository now contains:

- `benchmarks/s3bench/repeatability.py`;
- `tools/s3bench_analyze.py`;
- `tests/test_s3bench_repeatability.py`;
- documented repeatability-analysis workflow.

The tests explicitly cover per-loop normalization, O0/O1 with different loop counts, kernel/process separation, duplicate/missing rows, checksum/stdout/stderr validation, STABLE/USABLE/UNSTABLE classification, and conclusive-vs-noise behavior.

Recommendation:

```text
ISSUE_130=CLOSE_COMPLETED
ISSUE_131=CLOSE_COMPLETED_DUPLICATE
```

### #230 — Gen3 review debt

Keep as research/deferred debt, but do not treat it as an active 1.1 blocker. Some entries were already closed for the 1.0 product line (for example the release campaign obtained vetted crypto/provider evidence), while others belong specifically to the unpromoted Gen3/self-host trains.

Recommendation: reframe or relabel as deferred research debt before any selective Gen3 promotion.

### #171 — Zettelkasten compiler research lab

Keep open as a durable research locator. It is correctly isolated from production promotion.

## 4. Pull-request inventory

The repository still has a large number of open historical/research PRs. They are useful as evidence archives but make the active development surface difficult to read.

### A. Self-host / Stage1 review snapshots — archive/close, do not merge

The following are historical research/review surfaces and should not remain candidates for ordinary promotion:

- #227, #228, #229;
- #249, #259;
- #267, #268, #269, #270, #271;
- #273, #274, #275, #276, #277.

Their evidence can remain in Git history/closed PRs. Closing them does not delete branches or discussion.

### B. Self-host deferment policy — preserve content, replace stale PR

PR #278 contains valuable policy documents (`STATUS`, `LESSONS`, `REENTRY_CRITERIA`, `FUTURE_ARCHITECTURE`) but is now based on the pre-1.0 main and is not cleanly mergeable.

Recommended action:

1. port those documents onto a fresh branch from post-1.0 `main`;
2. reconcile wording with the published v1.0 state;
3. merge the fresh policy-only PR;
4. close #278 as superseded.

### C. Experimental labs — keep isolated, do not bulk merge

- #190 native policy search;
- #232 quantum foundation;
- #238 Reliability Lab;
- #240 accelerator foundation;
- #242 embedded foundation;
- #272 Agent Memory external benchmark lab.

These should remain independent experimental sources. Future production work should rebase/reimplement narrowly from current `main`, not merge the old branches wholesale.

### D. Obsolete historical development PR

PR #5 predates the much later implementation history and should be closed as superseded.

## 5. Experimental work ranking for post-1.0 value

### Rank 1 — Reliability Lab v2

The idea in #238 has the best fit for the first post-1.0 engineering track because it strengthens confidence without changing language semantics.

However, #238 itself should **not** be merged as-is. Its prototype checks timeout only after synchronous execution returns, so it cannot actually stop a hung compiler case. Its valid generator is also intentionally tiny.

A production Reliability Lab v2 should add:

- isolated subprocess execution per case;
- real watchdog termination;
- deterministic seed/corpus identity;
- grammar-aware valid generation across existing 1.0 constructs;
- bounded malformed mutations;
- O0/O1 hosted differential checks;
- native differential subset where appropriate;
- stable failure classification;
- automatic reproducer persistence and deterministic minimization;
- a fast PR smoke shard plus larger scheduled/local campaigns;
- no public performance claims.

Assessment:

```text
VALUE=VERY_HIGH
SEMANTIC_RISK=LOW
IMPLEMENTATION_SCOPE=BOUNDED
REUSE_OLD_PR_DIRECTLY=NO
REIMPLEMENT_FROM_MAIN=YES
```

### Rank 2 — Native backend policy research (#190)

Technically promising, especially Compact EA, but it remains performance research. It still needs trustworthy timing, current-main rebase, current certification and an explicit production candidate. This should follow reliability hardening, not precede it.

### Rank 3 — Selective Gen3 capabilities

The M2.41-M2.70 trains contain useful infrastructure/capabilities, but their breadth and review debt make whole-train promotion inappropriate. Future work should extract one capability at a time from current main with new tests/evidence.

### Rank 4 — Embedded / Accelerator / Quantum

Interesting laboratories, but all expand product scope dramatically. They should remain experiments until the core compiler/tooling line has a clear post-1.0 development cadence.

### Rank 5 — Full self-hosting

Remain deferred. Do not start Stage1 V4 from milestone pressure. Re-entry requires the generic architecture and representability criteria already identified by the self-host postmortem.

## 6. Recommended S3 1.1 track

Name:

```text
S3 1.1 — Reliability & Maintenance
```

### Phase A — repository truth

- update README to v1.0.0 reality;
- distinguish historical roadmap from current roadmap;
- retire/replace stale root campaign resume state;
- close completed benchmark issues #130/#131;
- triage historical PRs;
- port self-host deferment policy from #278 onto a fresh post-1.0 branch.

### Phase B — automation recovery

- resolve GitHub-hosted runner provisioning outside the source tree;
- once operational, require the existing Python/native/differential gates for production PRs;
- add branch protection after CI is trustworthy.

### Phase C — Reliability Lab v2

Implement from current main with no language/IR/Assembly version bump.

Initial acceptance target:

```text
DETERMINISTIC_REPLAY=PASS
REAL_TIMEOUT_ENFORCEMENT=PASS
HOSTED_O0_O1_DIFFERENTIAL=PASS
MALFORMED_INPUT_FAIL_CLOSED=PASS
MINIMIZATION=PASS
PERSISTED_REPRODUCER=PASS
PR_SMOKE=PASS
LARGE_CAMPAIGN=PASS
NEW_LANGUAGE_FEATURES=0
```

The large-campaign count should be chosen after measuring local runtime; do not pick a large number merely for appearance.

### Phase D — next capability decision

Only after Reliability & Maintenance is closed, choose between:

1. native backend performance candidate;
2. one narrow Gen3 capability;
3. platform/runtime expansion.

Do not start all three in parallel.

## 7. Recommended immediate priority order

```text
P0_1=FIX_CI_RUNNER_PROVISIONING
P0_2=PROTECT_MAIN_AFTER_CI_RECOVERY
P1_1=DOCUMENTATION_AND_STATE_HYGIENE
P1_2=CLOSE_OR_ARCHIVE_STALE_ISSUES_AND_PRS
P1_3=PORT_SELFHOST_DEFER_POLICY_ON_FRESH_MAIN
P2_1=IMPLEMENT_RELIABILITY_LAB_V2
P3_1=REVIEW_NATIVE_POLICY_RESEARCH_FOR_FUTURE_PROMOTION
P4=SELECTIVE_GEN3_OR_NEW_PLATFORM_WORK
SELFHOST=DEFERRED
```

## Final assessment

S3 should not react to reaching 1.0 by immediately maximizing feature count. The project already has substantial capability breadth. The highest-value post-1.0 move is to reduce state ambiguity, recover automated enforcement, and build a stronger adversarial reliability layer around the stable compiler.

That creates a much safer base for every later choice, including performance work, Gen3 promotion, new targets, and eventual self-host re-entry.
