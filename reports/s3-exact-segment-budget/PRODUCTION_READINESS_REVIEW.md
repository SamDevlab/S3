# Exact Segment Budget: Production Readiness Review

**Status:** Review only; no production promotion is authorized.
**Campaign:** `S3_EXACT_SEGMENT_BUDGET_PRODUCTION_READINESS_REVIEW`
**Review date:** 2026-09-24

## 1. Executive Decision

P2 remains the selected successful experimental implementation. The independent
Linux x86-64 evidence is strong for the measured RMSD, XSBench, and JSMN
workloads, and the exact-segment path is opt-in at the backend-construction
layer; `PER_INSTRUCTION` remains the default. This does not establish universal
S3 speedup or production readiness.

The candidate is **conditionally technically ready for serialized Linux
x86-64 use**. New exact-limit tests close the numeric boundary gap. The current
public concurrency contract remains unspecified; a conservative serialized
entry scope is documented as a proposal but is not yet accepted by project
governance. The measured code-size increase also needs a product decision.
Release gates remain blocked by the unintegrated PR stack, S3 Actions failures
before any job steps, and disabled Actions in the benchmark repository.
Resolve the concurrency-scope decision before treating the candidate as a
supported native capability.

```text
P2_SELECTED=YES
P2H_SELECTED=NO
TECHNICAL_CANDIDATE_READINESS=CONDITIONAL
RELEASE_GATE_READINESS=BLOCKED
PROMOTION_READINESS=READY_PENDING_MULTIPLE_BLOCKERS
S3_PRODUCTION_CHANGE_READY=NO
MERGE=NO
DEFAULT_SWITCH=NO
```

This review does not merge, release, tag, switch defaults, close fallbacks, or
change executable source.

## 2. Candidate Identity and Provenance

| Identity | SHA | Decision |
| --- | --- | --- |
| Control P0 | `e07d0b5464bf472b2ca18993f3e196a234ff0fc5` | Per-instruction count-up implementation |
| Selected P2 | `1a76e341098b54a639fec22eecea362cc243c46f` | Exact-segment candidate under review |
| Rejected P2H | `6f320242e3c1ebbb0d2ac5d6d85272ab375e5333` | Hardening replacement rejected for lack of structural materiality |
| Current PR #310 head | `b2178088e0c17738058a92a64ea6c2971530d5cd` | Not the production-review candidate |
| PR #310 base | `d064c17ea811ab926df515cb90884e8c6efffb3d` | Head of open Draft PR #309 |

The P0-to-P2 tree delta is limited to the three x86-64 implementation files,
the exact-budget test module, and four experiment reports. No unrelated
executable source changes were found. The hash manifest is included below and
in `PRODUCTION_READINESS_RESULT.json`.

The current #310 tree differs from P2 in `emitter.py`,
`tests/test_exact_segment_instruction_budget.py`, and its validation/hardening
reports. Those executable differences are the P2H lineage; they must not be
silently attributed to P2. P2H's E0 and runtime non-regression results do not
make it a replacement: it failed the predeclared structural materiality gate,
with negative added-text and hot-layout recovery in all six cells.

### P2 file manifest

| Path | SHA-256 | Bytes | Role |
| --- | --- | ---: | --- |
| `bootstrap/s3/backends/x86_64/backend.py` | `236c36df0b528b2edb88b124a0b36b9da34ea77c8d69a3a793bc3173dd133ea9` | 9005 | Backend mode validation and native backend configuration |
| `bootstrap/s3/backends/x86_64/emitter.py` | `bcfb7f36728219d3b0e5847979b625574681be0007c8181ae3dfe52556ca52dc` | 91155 | x86-64 instruction and exact-segment emission |
| `bootstrap/s3/backends/x86_64/instruction_budget.py` | `ee124fb48caa9e6f7eff95ad6187141b1d5cc6f3a72eef0c7533471db1716015` | 6158 | Deterministic logical instruction segmentation and diagnostics |
| `tests/test_exact_segment_instruction_budget.py` | `588241bb60da005c5b082a6f63c4ba67f914b54e7c47f5578f1082490584d408` | 23582 | Structural and native E0 regressions |

The isolated review branch starts from the exact P2 tree. Its only additions
are review artifacts. The scientific-kernel report already exists on the PR
#309 base and is omitted from this branch so the review diff does not duplicate
that base-owned document. Executable source and test content remain identical
to P2.

## 3. Evidence Provenance

The semantic-closure branch adds tests only at
`c07b2c486b98e8408119f44ceedceb46c6d2549b`; backend implementation content
remains byte-identical to P2 `1a76e341098b54a639fec22eecea362cc243c46f`.
The focused Linux x86-64 native gate passed 75 tests in 3.05 seconds with
`S3_NATIVE_REQUIRED=1` (Python 3.14.4, pytest 9.1.1). One full S3 suite then
ran on a Git checkout with valid Git metadata at that exact test/evidence
commit: 4,390 passed, 1 skipped, 572 subtests passed, 0 failed, exit 0, in
3,698.92 seconds. The sole skip is the optional cryptography-dependent test.
Its raw transcript is preserved in the semantic-closure PR evidence at
`reports/s3-exact-segment-budget/evidence/full-suite-valid-c07b2c48-linux-x86_64.txt`
with SHA-256
`6ebbbdc645cb66b3fcfea5b5683b64c416acd15eff11181ab2a99f6473f0e8b0`.

An earlier full-suite attempt on a source archive without `.git` failed
renderer-golden and Git-metadata lookups. It is preserved and explicitly
classified as an invalid test environment, not as candidate evidence. The
valid full suite is the only qualifying full-suite gate for this closure.

The original P2 suite record in the S3 benchmark repository remains inherited
evidence; the newly preserved run independently validates the P2 backend plus
the test-only semantic-closure change. The raw transcript and its digest are
now locally available in the semantic-closure branch.

There is a stale record in S3 P2's own
`EXPERIMENTAL_VALIDATION.md`: it identifies earlier source `f4353c1b...` and
4,372 passed. The diff from `f4353c1b...` to P2 includes an emitter context
preservation fix and a focused regression test. Therefore the 4,372 result is
not the P2 full-suite result; the exact-source benchmark report is used for
P2's 4,373 result. The P2H result of 4,375 passed belongs to another SHA and is
not substituted.

Independent benchmark evidence is in S3-Benchmarks PR #24 and its
`FINAL_REPORT.md`. It records fixed-work Linux x86-64 runs, fresh processes,
balanced interleaving, two independent sessions, fixed CPU affinity, raw
manifests, host fingerprint, correctness, and reproducibility. The frozen
benchmark validation reports P2 excess recovery of 92.14%-104.56% over the
three specified workloads and six O0/O1 cells. No timing was rerun for this
review.

## 4. Semantic Contract and E0 Mapping

The accepted ADR-0014 contract counts logical S3 Assembly opcodes, not x86-64
instructions. P0 checks the counter before each opcode, fails before the
pending opcode can produce effects, then increments and executes. P2's fast
segment is valid only when the whole segment can fit; otherwise it takes the
exact per-instruction slow path.

| Contract | Supporting evidence |
| --- | --- |
| Check before the logical instruction; no over-budget instruction effects | `test_single_segment_w_minus_one_exact_and_w_plus_one_boundaries`; `test_side_effect_boundary_before_and_after_budget_exhaustion_matches_p0` |
| Exact `C + W <= L` fast-path admission and per-op fallback | `test_exact_segment_codegen_has_exact_precharge_and_scalar_slow_path`; `test_single_segment_w_minus_one_exact_and_w_plus_one_boundaries` |
| Plan is deterministic, block-local, and split at call/branch/return barriers | `test_planner_is_block_local_and_splits_after_calls_and_control`; `test_plan_diagnostics_apply_the_predeclared_fast_segment_threshold` |
| Loop, control flow, calls, and failing logical boundaries match P0 | `test_loop_calls_and_failure_boundaries_match_p0`; `test_non_budget_runtime_failure_inside_fast_path_matches_p0` |
| Same artifact's counter lifetime persists across serialized FFI calls | `test_repeated_serial_ffi_calls_preserve_process_budget_lifetime` |
| Synchronous callback re-entry sees a complete call segment | `test_foreign_callback_reentry_observes_a_complete_call_segment` |
| Fused `TCMP`/`TBR3` preserves logical accounting and guarded-read failure context | `test_fast_fused_compare_keeps_context_for_guarded_register_reads`; exact-segment structural tests |
| Maximum native unsigned 64-bit limit is accepted | `test_u64_limit_domain_is_accepted_by_the_planner`; `test_u64_maximum_budget_assembles_and_matches_p0` |
| Frame budget remains an independent guard | `test_frame_limit_independence` in `tests/test_instruction_limit_e3.py`; frame prologue checks remain in the emitter |
| Default remains per-instruction and preserves representative output bytes | `test_default_mode_matches_explicit_per_instruction_output`; `test_default_mode_matches_frozen_e07_native_assembly_bytes` |

The P2 focused native group and complete suite passed in the recorded Linux
x86-64 environment. E0 is qualified for serialized execution, repeated serial
FFI calls, and synchronous callback re-entry. It is not evidence for concurrent
host-thread entry.

### `max_instructions` domain

The native backend accepts integer limits in the inclusive range
`1..2^64-1`; the default remains 100,000. Zero and negatives are rejected,
booleans and other non-integers are rejected, and values above `2^64-1` are
rejected. The new Linux matrix builds, links, executes, and compares P0/P2 at
`0x7ffffffe`, `0x7fffffff`, `0x80000000`, `0x80000001`, 10,000,000,000, and
U64_MAX; the FFI artifacts also build and execute at each limit. Static checks
verify P0's direct-limit immediate/wide selection and P2's `L-W` precharge
encoding. For the tested P2 W=2 segment, the immediate precharge operands at
the signed boundary are `0x7ffffffd`, `0x7ffffffe`, and `0x7fffffff`; the
10-billion and U64_MAX cases exercise a wide remaining-budget value. Existing
loop/call tests cover real segment weights 3, 4, 5, 7, and 10 at small exact
limits, and a synthetic emitter check covers `W=U64_MAX-1`, `L=U64_MAX`, and
`L-W=1`. No limit-boundary bug was found. P2 compares the remaining budget
`L-W`, so its precharge immediate transition is not identical to the direct
`L` transition in P0.

The instruction budget is independent of `max_frames` and logical-memory
checks. Segment precharge changes only instruction-accounting state; each S3
instruction still goes through its normal emitter path, and slow-path failures
retain the baseline failure site and context.

## 5. Concurrency and Reentrancy

The instruction and frame counters are aligned writable `.bss` objects in the
loaded artifact instance. P0 uses ordinary memory `inc`/`dec`; P2 uses ordinary
memory `add` for fast-segment precharge and ordinary scalar `inc`/`dec`. Neither
uses a lock-prefixed read-modify-write or thread-local storage. Serial calls
share the loaded artifact's counter state, as covered by the repeated-serial
FFI test. Synchronous callback re-entry is qualified because a call is a
segment barrier and accounting is updated before host code is entered.

ADR-0008 and ADR-0014 contain no same-artifact concurrency promise, and no
concurrent-entry test was found. The current public contract is therefore
`UNSPECIFIED`, not explicitly supported or explicitly prohibited. The proposed
conservative scope is caller-serialized entry into one loaded artifact;
synchronous re-entry within a serialized call remains qualified. This is
documented in the proposed ADR but remains unaccepted pending project
governance. The same lack of synchronization exists in P0, so no pre-existing
concurrency guarantee was shown to be weakened by P2.

```text
SERIAL_EXECUTION=QUALIFIED
SYNCHRONOUS_CALLBACK_REENTRY=QUALIFIED
CONCURRENT_FFI_ENTRY=NOT_QUALIFIED
PROPOSED_SCOPE=NOT_SUPPORTED_UNLESS_EXPLICITLY_QUALIFIED
PROPOSED_SCOPE_ACCEPTED=NO
CONCURRENCY_READINESS=CONDITIONAL_PENDING_GOVERNANCE
```

No synchronization or concurrent qualification is implemented. Concurrent
tests are not required under the proposed serialized-only scope; they become
necessary only if governance requires same-artifact concurrent entry.

## 6. API, Default, and Compatibility

`InstructionBudgetMode` is not re-exported in the x86-64 package's `__all__`,
but `X8664Backend` is exported and has a public keyword-only
`instruction_budget_mode` field. The normal `generate_native_assembly` and
`generate_ffi_assembly` functions and CLI do not expose this mode. The mode is
therefore a semi-public backend configuration, not a stable end-user opt-in.

`None` continues to parse as `PER_INSTRUCTION`; P2 does not change the default.
No source syntax, Assembly format, IR format, public native symbols, FFI ABI,
calling convention, or artifact-loading format changes. The existing frozen
P0 corpus (linear, loop/calls, bounds failure) is byte-identical under P2's
default mode. E0 tests compare exit status, stdout, and stderr for the relevant
success/failure cases.

| Compatibility surface | Status | Scope |
| --- | --- | --- |
| Source language | PASS | No frontend or syntax changes |
| Assembly and IR | PASS | No persisted format changes |
| FFI ABI/calling convention | PASS | System V AMD64 remains unchanged |
| Diagnostics | PASS | P0/P2 equivalence tested for the E0 matrix; no new stable text promise |
| Existing backend call sites | PASS | Default remains `PER_INSTRUCTION`; public generation signatures unchanged |

Recommended next-campaign strategy: `KEEP_EXPERIMENTAL_INTERNAL`. A supported
opt-in would require an explicit stable API surface, a concurrency contract,
and release gates; do not add a CLI flag or switch defaults here.

## 7. Performance, Size, and Product Scope

On the frozen Linux x86-64 protocol and only for RMSD, XSBench, and JSMN, P2
recovered 92.14%-104.56% of measured P0-to-PNEG instruction-budget excess in
all six O0/O1 cells and beat P1 in those cells. Reported end-to-end reductions
versus P0 were approximately 62% for RMSD, 51%-55% for XSBench, and 50%-51%
for JSMN. These are workload- and protocol-specific results, not a universal
S3 speedup. PNEG is an unsafe diagnostic lower bound, never a production mode.

P2's measured `.text` growth is +39.17% for RMSD, +53.35%-53.57% for XSBench,
and +58.27%-58.54% for JSMN. The growth is established; instruction-cache or
runtime harm caused by it is not established. No explicit product binary/code
size cap was found in the reviewed documentation. Disk footprint, link time,
compile time, shared-library deployment impact, and constrained-device impact
were not measured.

```text
P2_CODE_SIZE_TRADEOFF=RMSD_+39_PERCENT_XSBENCH_+53_PERCENT_JSMN_+58_PERCENT
CODE_SIZE_READINESS=CONDITIONAL_NEEDS_PRODUCT_POLICY
QUALIFIED_PERFORMANCE_INDEX=NOT_AVAILABLE
```

The existing evidence score remains 89/100 as a research-evidence score only;
it is not a readiness score. QPI is unavailable and is not, by itself, a blocker.

P2H remains rejected as a hardening replacement: correctness, reproducibility,
P0 identity, and runtime guard passed, but it did not recover structural text
or hot layout. No further budget architecture search is recommended.

## 8. Portability and Dependencies

P2 is implemented in the Linux x86-64 native backend and was qualified on Linux
x86-64. ADR-0008 scopes that native backend to ELF/Linux x86-64; Windows tests
do not qualify Windows-native output. No P2 qualification exists for ARM64,
macOS, or another native backend.

```text
NATIVE_PLATFORM_SCOPE=LINUX_X86_64
PORTABILITY_READINESS=PASS_WITH_DOCUMENTED_SCOPE
```

This classification only applies if the production scope is explicitly
Linux x86-64. If product promotion implies other targets, reclassify as
conditional and qualify only the required target. P2 adds no third-party
runtime dependency; native generation continues to use the existing GNU
assembler/linker toolchain.

## 9. Dependency Stack and Live PR State

Live GitHub state on 2026-09-24:

- S3 #301-#309 are OPEN Draft PRs forming a dependency chain from #301 on
  `main` through #309 (`feat/s3-scientific-kernel-rmsd-v01`, head
  `d064c17e...`).
- S3 #310 is OPEN Draft, based on #309, with current head
  `b2178088...`; it is not the P2 source identity.
- S3-Benchmarks #24 is OPEN Draft and based on the #23-series research base;
  #23 also remains OPEN Draft. Neither is merged.
- This review PR is based on #309 so its candidate diff can be reviewed in
  that stack. No parent PR was merged or retargeted.
- Semantic-closure PR #312 is OPEN Draft, based on the same #309 lineage, at
  head `6a97b728db9d194f77f5dae15967591d0c4315a7`. It carries the test-only
  boundary additions and semantic evidence; it is unmerged and is not P2H.

At the tree level, the P2 delta against the #309 tree is limited to the budget
backend, its focused test, and experiment/review documentation. A clean
extraction is feasible, but was not performed. Integration still depends on
the parent stack being integrated or on a separately reviewed clean extraction.

```text
PR_STACK_STATUS=301->302->303->304->305->306->307->308->309->310; all open drafts
STACK_READINESS=STACK_READY_AFTER_PARENT_MERGES
CLEAN_EXTRACTION_FEASIBLE=YES
```

## 10. CI and Benchmark Automation

S3 repository Actions permissions report `enabled=true`. At the P2H-based #310
head, the latest observed S3 workflow runs (including run `35955746566`) failed
within seconds with every job reporting `steps=[]`; the API exposed no job
steps, and `gh run view --log` returned `log not found`. This is not a source
failure, but the cause cannot be attributed from available evidence.

The natural workflows on semantic-closure PR #312 head
`6a97b728db9d194f77f5dae15967591d0c4315a7` showed the same failure pattern:
Tests run `36001998655` (10 jobs), S3 1.0 candidate gates `36001998616` (2
jobs), and M1.38 Docker capability closure `36001998615` (1 job) all failed
before steps, with `steps=[]` on all 13 jobs. Root cause remains unidentified;
these results are not a CI pass, and no manual rerun was made.

```text
S3_CI_ROOT_CAUSE=UNKNOWN
S3_CI_READINESS=BLOCKED_INFRASTRUCTURE
```

S3-Benchmarks #24 reports no checks and no runs for its branch. Its workflow
file has `push`, `pull_request`, and `workflow_dispatch` triggers, while the
repository Actions-permissions endpoint reports `enabled=false`. This is
consistent with repository/org policy preventing the validation workflow from
running; do not call absent checks a pass.

The hardening run's benchmark wrapper printed `106 passed, 1 skipped`, then
failed parsing an invalid shell `exit` expression. A separate pytest exit code
was not captured. That run is P2H tooling evidence, not P2 benchmark evidence.
The P2 validation report independently records its benchmark suite as
97 passed, 1 skipped, exit 0. Keep these executions distinct.

```text
BENCHMARK_CI_STATE=NO_RUNS; NO_CHECKS_REPORTED
BENCHMARK_CI_ROOT_CAUSE=REPOSITORY_OR_ORG_POLICY (Actions enabled=false)
BENCHMARK_INFRA_READINESS=BLOCKED
BENCHMARK_WRAPPER_STATUS=P2H_POST_PYTEST_WRAPPER_FAILURE; PYTEST_EXIT_NOT_INDEPENDENTLY_CAPTURED
```

No manual rerun was made. Normal CI on this review PR is allowed; any
pre-step failure remains an infrastructure failure, not a pass or source
failure.

## 11. Safety, Observability, and Maintenance

The exact fast path first checks that the remaining budget can cover the whole
segment, then adds its logical weight before executing it. If the check fails,
the exact scalar sequence executes, preserving the baseline failing opcode and
context. The configured limit is at most U64_MAX, and admission compares
against `limit - weight`, preventing the fast-path add from exceeding the
limit. The scalar path increments only after confirming the pending opcode is
within the limit. Existing frame, register-initialization, bounds, and
memory-initialization checks remain in each instruction's emission path.

PNEG is benchmark-side diagnostic-only and does not appear in the production
bootstrap backend. No new telemetry is warranted. The generated artifact does
not carry an explicit budget-mode metadata field; future build records should
retain the selected mode and exact codegen configuration for reproducibility.

Maintenance complexity is **MODERATE**: P2 adds a planner/mode, duplicates
fast and exact slow emission for eligible segments, and requires a focused
native E0 suite alongside the established instruction-limit tests. Compilation
time and linking-cost impact were not measured. Do not infer that runtime
measurements establish them.

## 12. Proposed Rollout, Rollback, and Regression Guardrails

No rollout is executed here. A later proposal should first retain the current
internal-only mode, then consider a documented Linux x86-64 opt-in after the
concurrency scope, product size policy, clean integration lineage, and CI are
resolved. Only after release evidence should a default change be considered;
`PER_INSTRUCTION` remains a fallback.

Rollback is to regenerate/rebuild the artifact with
`PER_INSTRUCTION` and redeploy it. The mode is baked into emitted machine code;
an already-built artifact cannot be changed by toggling a runtime flag. No
language change or data migration is required. Proposed rollback triggers:
any E0/default-output regression, changed budget-failure context, FFI/re-entry
regression, native crash, a product-defined binary-size limit violation, or a
statistically supported major regression in release workloads.

Proposed permanent gates:

- exact budget boundary and zero/invalid configuration tests;
- logical calls, loops, branch/call barriers, fused `TCMP`/`TBR3` tests;
- serial repeated FFI, callback re-entry, side-effect boundary, and diagnostic
  context tests;
- U64 limit, frame-budget independence, and default P0 byte-identity tests;
- focused Linux x86-64 native smoke on PRs and the complete S3 suite before
  release;
- a small PR benchmark smoke, scheduled RMSD/XSBench/JSMN subset, and all three
  workloads at release qualification;
- define statistically justified release regression bands later; the research
  threshold `>=50% recovered excess` is not a release threshold.

This defines a proposed regression policy; it is not yet automated.

## 13. Accepted Limitations and Blockers

Known limitations are explicit: same-artifact concurrent FFI is unqualified and
its proposed caller-serialized scope is pending governance acceptance;
native evidence is Linux x86-64 only; `.text` grows 39%-59%; P2H did not
materially harden code size; QPI is unavailable; the S3 Actions failures have
no attributed root cause; benchmark Actions are disabled; the PR stack remains
unmerged; and the P2 S3 report contains a stale earlier full-suite entry.

| Blocking item | Evidence | Required resolution | Owner / next action |
| --- | --- | --- | --- |
| Concurrency contract governance | ADR-0008/0014 and public API do not define same-artifact concurrent entry; P0 and P2 counters are unsynchronized; caller-serialized scope is proposed, not accepted | Accept or revise the proposed scope; qualify concurrency only if required | S3 project; `S3_NATIVE_EXECUTION_CONCURRENCY_CONTRACT_DECISION` |
| Integration lineage | #301-#309 remain open Draft; #310 is stacked on #309 and not P2 | Integrate parent stack or review a clean P2 extraction | S3 maintainers; `S3_1_X_PR_STACK_INTEGRATION_CLOSURE` after contract decision |
| S3 release CI | #310 and #312 natural runs fail before steps; #312 has 13 jobs with `steps=[]`; root cause UNKNOWN | Obtain one real green run after attributable infrastructure/workflow diagnosis | S3 CI owners; `S3_CI_RELEASE_GATE_RECOVERY` |
| Benchmark CI | Actions permissions `enabled=false`, no run/checks | Re-enable/configure the benchmark repository gate and capture a valid run | S3-Benchmarks maintainers |
| Product code-size policy | measured `.text` growth, no documented cap found | Decide acceptable product scope/size limit; do not reopen budget architecture | S3 product maintainers |
| Limit-edge coverage | New Linux test-only matrix covers `0x7ffffffe` through `0x80000001`, 10 billion, and U64_MAX in both modes; P0/P2 results match | Closed for tested Linux x86-64 backend scope | Closed by semantic-closure evidence |

P2's successful performance result remains valid and is not invalidated by
these promotion blockers.

## 14. Readiness Matrix

The gate-by-gate matrix is in
`PRODUCTION_READINESS_MATRIX.md`. This is not a numeric readiness score.

## 15. Final Classification and Next Critical Path

```text
R1_SUPPORTED_CAPABILITY=CONDITIONAL
R2_INTEGRATION=CONDITIONAL
R3_RELEASE_AUTOMATION=BLOCKED
R4_SCOPE_CONTRACT=CONDITIONAL
R5_RESOURCE_TRADEOFF=CONDITIONAL

TECHNICAL_CANDIDATE_READINESS=CONDITIONAL
RELEASE_GATE_READINESS=BLOCKED
PROMOTION_READINESS=READY_PENDING_MULTIPLE_BLOCKERS
NEXT_CRITICAL_BLOCKER=CONCURRENCY_CONTRACT_GOVERNANCE_DECISION
NEXT_CAMPAIGN=S3_NATIVE_EXECUTION_CONCURRENCY_CONTRACT_DECISION

EVIDENCE_SCORE=89 (research rubric only)
QUALIFIED_PERFORMANCE_INDEX=NOT_AVAILABLE
S3_PRODUCTION_CHANGE_READY=NO
READY_FOR_MERGE=NO
MERGE=NO
TAG=NO
RELEASE=NO
DEFAULT_SWITCH=NO
```

Priority after the contract decision is integration lineage, then S3 CI and
benchmark CI recovery, then product code-size policy. No P3/P4/P5 architecture
search is recommended. The review stops before any human promotion decision.
