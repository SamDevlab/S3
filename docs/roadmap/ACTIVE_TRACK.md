# Active S3 project track

Last reviewed: 2026-09-25.

## Active track

```text
ACTIVE_TRACK=S3_1_4_SCIENTIFIC_OPTIMIZER_AND_DOMAIN_COMPUTE_EXPANSION
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
S3_1_4_STATE=IN_PROGRESS_LOCAL_CANDIDATE
S3_1_4_BRANCH=feat/s3-1.4-scientific-optimizer-domain-compute
S3_1_4_BASE=13a5a8308064e8277887fecc6052cde6b22115f3
S3_1_4_DRAFT_PR=NOT_CREATED
S3_1_4_FUNCTIONAL_SOURCE_FREEZE=NOT_FROZEN
S3_1_4_LINUX_NATIVE=NOT_YET_QUALIFIED
LOOP_HYBRID_AVAILABLE=YES_EXPLICIT
EXACT_SEGMENT_DEFAULT=NO
```

S3 `v1.0.0` remains the public stable release of the Python reference toolchain. PR #313 is merged; its cumulative source baseline brings the #301–#309 capabilities into `main`. This does not change the reference compiler or establish full self-hosting.

The active development track is **S3 1.4 — Scientific Optimizer and Domain Compute Expansion**. S3 1.3 is integrated through PR #316 at `da6efaf0a97c8cef08aea2f196aca37199311332`; its certified Linux full suite and 33/33 scientific checksum record remain historical evidence. The selected P2 and `s3.v1.science` are in `main`; `PER_INSTRUCTION` remains the default.

The 1.4 candidate is being developed on `feat/s3-1.4-scientific-optimizer-domain-compute`, based on `13a5a8308064e8277887fecc6052cde6b22115f3`. Local work includes conservative natural-loop/induction/range facts, proof-gated vector BCE, scaled addressing for proven accesses, metadata-only ordered reduction recognition, and the experimental `s3.v1.geometry` module. Kernel-scope native measurement and expanded PER/EXACT/HYBRID section characterization are being prepared; neither has final Linux evidence yet. This is a local, unmerged candidate with no source freeze or PR at this checkpoint. These branch-only changes do not alter public defaults or the main-branch capability claim.

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

GitHub Actions remains blocked before workflow steps by the account billing/quota condition reported for PR #313; no Actions rerun or workflow weakening was performed. Issue #284 remains OPEN and also tracks the unprotected `main` branch and absent required checks.

## Immediate priorities

1. Complete and locally validate the 1.4 candidate, including BCE negative cases and geometry contracts.
2. Freeze functional source before Linux native, fair kernel-scope, code-size, and full-suite evidence.
3. Publish one Draft PR for human review only; no merge, release, tag, PyPI publication, or default promotion is authorized by the campaign.
4. Keep `PER_INSTRUCTION` as default; revisit budget policy only with broader comparable workload evidence and a separately reviewed decision.

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

The post-#313 and PR #316 integration is the current `main` baseline. Do not treat historical Draft state for PRs #302–#312 as a missing integration prerequisite; they are superseded or informational provenance and should be closed by a maintainer when convenient, not used as blockers. The 1.4 optimizer/geometry work remains branch-only until a future reviewed merge; local evidence and documentation must not imply that it is already in `main`.
