# Active S3 project track

Last reviewed: 2026-09-28.

## Active track

```text
ACTIVE_TRACK=S3_1_12_CAPABILITY_BREAKOUT_PRODUCTION_COMPILER_ADVANCEMENT_CAUSAL_OPTIMIZATION_LOOP_SEMANTICS_AND_COMPUTE_EXPANSION
CURRENT_PUBLIC_STABLE=v1.0.0
CURRENT_PRERELEASE=NONE
STABLE_V1_0_RELEASED=YES
REFERENCE_COMPILER=PYTHON
FULL_SELFHOST=DEFERRED_RESEARCH
PYPI_PUBLISHED=NO
MAIN_POST_313_INTEGRATION=YES
PR301_309_CAPABILITIES_IN_MAIN=YES
S3_1_1_TECHNICAL_CLOSURE=PASS_PR294_MERGED
S3_1_1_RELEASE_PREP=OPEN_DRAFT_PR295_CONFLICTING
S3_1_1_IMPLEMENTATION_STARTED=YES
S3_1_1_PHASE=R0_R5_TECHNICAL_CLOSURE_IN_MAIN_RELEASE_DECISION_PENDING
PR315_MERGED=YES
P2_IN_MAIN=YES
EXACT_SEGMENT_AVAILABLE=YES
S3_1_2_IMPLEMENTATION_STARTED=YES
S3_1_2_STATE=MERGED_PR315
P2_IN_CAMPAIGN_BRANCH=NO
P2_DEFAULT=NO
PER_INSTRUCTION_DEFAULT=YES
P2_STATUS=IN_MAIN_NOT_PROMOTED
P2_PARENT_STACK_BLOCKER=RESOLVED_BY_PR313
P2_PROMOTION_AUTHORIZED=NO
SCIENTIFIC_NUMERIC_FOUNDATION_IN_MAIN=YES
S3_1_3_IMPLEMENTATION_STARTED=YES
S3_1_3_STATE=MERGED_PR316
S3_1_3_MERGED_HEAD=da6efaf0a97c8cef08aea2f196aca37199311332
S3_1_3_FULL_SUITE=4399_PASSED_1_SKIPPED_EXIT_0_LINUX_X86_64
S3_1_3_LINUX_SCIENCE_VERIFY=33_OF_33_CHECKSUMS
S3_1_4_IMPLEMENTATION_STARTED=YES
S3_1_4_STATE=MERGED_PR317
S3_1_4_MERGE_COMMIT=506108a679f586b5786d0ab020de4e9f10f964f0
S3_1_5_IMPLEMENTATION_STARTED=YES
S3_1_5_STATE=MERGED_PR318
S3_1_5_BRANCH=codex/s3-1.5-real-world-compute
S3_1_5_BASE=506108a679f586b5786d0ab020de4e9f10f964f0
S3_1_5_FUNCTIONAL_SOURCE_FREEZE=c924148c6d95948778351c7dd1362259caff670c
S3_1_5_FULL_SUITE=4461_PASSED_1_SKIPPED_EXIT_0_LINUX_X86_64
S3_1_5_PR=318
S3_1_5_GITHUB_ACTIONS=REMOTE_CI_UNAVAILABLE_RUNNER_0_STEPS_0
S3_1_5_MERGE_COMMIT=92b59bd20d7a35103789fdbd3358faa18237977b
S3_1_6_STATE=MERGED_PR320
S3_1_6_MERGE_COMMIT=4ddc7a64a4c395460181db0e8957f085d8bb12a
S3_1_11_STATE=MERGED_PR325
S3_1_11_MERGE_COMMIT=a1ecc29908dfb42480376961927fd6c50552ecf3
S3_BENCH_1_11_STATE=MERGED_PR29
S3_BENCH_1_11_MERGE_COMMIT=d425aaca241549bae797d88d08fd7832ad221255
S3_1_12_IMPLEMENTATION_STARTED=YES
S3_1_12_STATE=IN_PROGRESS_PR_NOT_OPENED
S3_1_12_BRANCH=feat/s3-1.12-capability-breakout
S3_1_12_BASE=a1ecc29908dfb42480376961927fd6c50552ecf3
S3_1_12_MERGE_AUTHORIZED=NO
S3_1_12_REGISTER_ALLOCATION_DEFAULT=YES
S3_1_12_SAME_COLOR_TMOV_ELISION=IMPLEMENTED_FOCUSED_GATES_PASS_LINUX_CI_PENDING
S3_1_12_LOOP_ANALYSIS=CONTINUATION_RECURRENCES_PROVEN_5_OF_5_STRICT_F64_LOOPS_CLASSIFIED_2_NOT_VECTORIZABLE_3_UNKNOWN_NO_SIMD
S3_1_12_BENCH_BRANCH=research/s3-1.12-capability-breakout-lab
S3_1_12_BENCH_BASE=d425aaca241549bae797d88d08fd7832ad221255
REGISTER_ALLOCATION_DEFAULT=YES
REGISTER_ALLOCATABLE_POOL=11_CALL_AWARE_REGISTERS
LOOP_HYBRID_AVAILABLE=YES_EXPLICIT
EXACT_SEGMENT_DEFAULT=NO
```

S3 `v1.0.0` remains the public stable release of the Python reference toolchain. PR #325 integrates the 1.11 compiler-research campaign at `a1ecc29908dfb42480376961927fd6c50552ecf3`; S3-Benchmarks PR #29 is integrated at `d425aaca241549bae797d88d08fd7832ad221255`. The active post-1.11 campaign is S3 1.12 on independent branches based directly on those two `main` heads. This does not change the reference compiler or establish full self-hosting.

The current backend reality is that `X8664Backend.register_allocation` defaults to `True`, using a deterministic call-aware pool of eleven allocatable registers with stack fallback. The `PER_INSTRUCTION` budget mode reserves `r15` for its live budget counter; the public instruction-budget default remains `PER_INSTRUCTION`. The 1.12 branch elides same-color TMOV data movement in the production emitter while preserving logical initialization checks and budget instrumentation. Production loop analysis now proves one scalar recurrence update on every reachable backedge for all five pinned loops; two loops with ordered f64 reductions are classified `NOT_VECTORIZABLE`, while three remain `UNKNOWN` because vector range/dependence proofs are incomplete. No SIMD or vector transformation is authorized. Provenance-focused tests passed on Python 3.11, 3.12, 3.13, and 3.14; the combined TMOV, loop, allocation, budget, and backend focused gate passed on Python 3.13. Linux-native CI has not yet been observed.

S3 1.3–1.6 and the 1.5 source freeze remain historical evidence; their prior validation and performance claims are unchanged. S3 1.11's bounded research established candidates and rejected lines, but its report-only analyses are not treated as production capability. The 1.12 campaign is converting only proven generic results into the normal compiler path and will retain strict-FP and per-instruction budget defaults.

The 1.3 performance record remains unchanged: in its representative structural workload, the BASE-to-FINAL PER process median was effectively neutral (-1.98%) while assembly source and ELF grew about 119%; exact-segment `.text` overhead measured +55.4% versus PER for that workload. These results do not justify default promotion. The underlying PR #313 parent-stack blocker was resolved and is not being re-investigated.

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

R4's deterministic minimizer and replay/triage contracts were integrated through PR #294. Its historical implementation head was `774849b1303e3fb726c2c4972457bfa88ba3247d`; the evidence remains in the R4/R5 reports. The candidate hash is historical provenance, not the current `main` head.

R5's bounded Linux x86-64 campaign recorded 256/256 PASS, hosted O0/O1 for all 256 cases, and native O0/O1 for the bounded 32-case shard on candidate `d277a862223e8d07b39fd9a687dd1ce0651af63b`. The campaign report and output hashes remain in [`R5_MAINTENANCE_CLOSURE.md`](../../reports/s3-1.1-reliability-20260916/R5_MAINTENANCE_CLOSURE.md). R0–R5 technical closure is integrated through merged PR #294. PR #295 is a separate release-preparation Draft PR, currently conflicting with `main`; no new release is implied.

The runner/billing observations associated with PR #313 and issue #284 are historical infrastructure notes, not evidence that the current 1.12 candidate's workflows have run. No old workflow was rerun; the new candidate's natural checks will be observed after its Draft PR is opened.

## Immediate priorities

1. Continue converting 1.11 findings into generic production capabilities; same-color TMOV elision and continuation-aware recurrence facts are implemented, with correctness/eligibility boundaries still under review.
2. Add independent Bench execution capability only if it replaces one-off experiments with a reusable candidate/ablation runner.
3. Freeze behavior, validate on Linux, update concise evidence, and open Draft PRs only for substantive capability deltas.
4. Do not merge, release, tag, publish to PyPI, or change strict-FP or budget defaults in this campaign.

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

GitHub Actions jobs have been failing before any step is assigned (`runner_id=0`, empty step list); PR #313's runs carry the billing/quota annotation. This is infrastructure debt, not a demonstrated compiler regression, and must not be hidden by weakening workflows. The successful R3 certification came from exact-commit/tree execution on the Ubuntu x86-64 VM, not from GitHub Actions. The #313 delivery likewise used preserved local/Linux evidence under an explicit CI waiver; that does not make GitHub CI green or remove the infrastructure blocker.

## Next operational step

The S3 1.12 implementation worktree is based at `a1ecc29908dfb42480376961927fd6c50552ecf3`; its independent Bench worktree is based at `d425aaca241549bae797d88d08fd7832ad221255`. The campaign branches are not stacked on prior Draft PRs. Their planned PRs remain unopened until capability and validation gates warrant publication. No merge, release, tag, publication, or default promotion is authorized.
