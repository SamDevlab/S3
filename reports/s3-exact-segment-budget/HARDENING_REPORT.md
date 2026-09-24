# Exact Segment Budget Hardening

## Pre-implementation feasibility audit

Audit base: S3 documentation head `e814f5457c2fdd346d85f3b8a6321e96b2bc759f`; frozen P2 source `1a76e341098b54a639fec22eecea362cc243c46f`.

The current `_emit_budgeted_segment()` emits the fast guard and precharge, the fast instruction sequence, a jump around the inline slow copy for nonterminating segments, and then the scalar slow sequence with per-instruction accounting. The segment planner itself partitions at calls, branches, and returns. The proposed hardening leaves that planner and both instruction-sequence emitters unchanged.

| Strategy | E0 preservable | P0 byte identity preservable | No new per-instruction hot cost | Existing emitter structure | Fail closed | Classification |
| --- | --- | --- | --- | --- | --- | --- |
| A. Cold-outline duplicated slow path | Yes: emit the same scalar slow sequence and failure sites; only relocate it and preserve its continuation edge | Yes: applies only to `EXACT_SEGMENT`; default `PER_INSTRUCTION` emission is untouched | Yes: the fast path retains its guard/precharge and can fall through instead of jumping over the duplicate | Yes: collect existing slow instruction sequences and place them in an ELF cold text section; branch/continuation labels remain explicit | Yes: assembly, link, E0, and FFI gates must all pass; otherwise retain P2 | `ELIGIBLE`, selected as the one candidate |
| B. Structurally shared exact slow path | Not with the existing unique instruction bodies without changing execution representation | Potentially, but irrelevant to P0 | No credible body sharing is available without per-instruction dispatch/calls or a generic interpreter | No: a shared executor would add a new execution mechanism, not factor existing emitter structure | Not applicable | `REJECTED_COMPLEXITY` |
| C. Current inline duplication | Already proven by the P2 gates | Yes | Yes | Yes | Yes | Control; no implementation |

Strategy A is a layout experiment, not presumed code-size compression. It moves unique scalar copies from `.text` to `.text.unlikely`. We will report `.text` separately from total executable text (`.text` plus `.text.unlikely`); no total-byte reduction or runtime benefit is claimed in advance. The fast path must not gain per-instruction work. Slow replay retains the existing exact accounting, diagnostic contexts, terminators, and continuation behavior.

`plan_budget_segments()` and all segment weights, barriers, and eligibility remain unchanged. The `PER_INSTRUCTION` branch is not edited. P0 identity remains an explicit gate, not an assumption. If ELF sectioning, function metadata, standalone linking, FFI artifacts, E0 behavior, or any predeclared threshold fails, P2 remains the candidate and no second hardening design will be attempted.

## Hypotheses

`H12`: the exact slow path can be outlined while preserving E0 and P0 and improving hot layout without material performance degradation. `UNDER_TEST`.

`H12A`: placing exact scalar replay copies in a cold executable section reduces the hot code footprint without degrading P2 timing. `UNDER_TEST`.

No H12B is opened because structural body sharing was rejected before implementation. No new budget architecture is proposed.

The preceding ledger is unchanged: H1 `CONFIRMED`; H2 `CONFIRMED_CAUSAL_XSBENCH`; H3 `NOT_CONFIRMED`; H4 `OPEN`; H5 `OPEN`; H6 `WEAKENED`; H7 `CONFIRMED_GENERAL`; H8 `CONFIRMED_SAFE_NOT_MATERIAL`; H9 `CONFIRMED_EXACT_MAPPING`; H10 `CONFIRMED`; H11 `CONFIRMED_MATERIAL`. Final H12 is `SAFE_NOT_STRUCTURALLY_MATERIAL`; H12A is `NOT_CONFIRMED`. The predeclared hot-layout materiality threshold is 25%; no measured cell reached it. Evidence Score remains 89/100 under the existing rubric, and `QUALIFIED_PERFORMANCE_INDEX=NOT_AVAILABLE`.

## Evidence log

Implementation, focused tests, source freeze, full-suite evidence, Linux native validation, benchmark validation, and final disposition are recorded below. Existing P2 timing and full-suite evidence remain historical controls and are not relabeled as P2H results.

## Final hardening evidence

Candidate: P2H source `6f320242e3c1ebbb0d2ac5d6d85272ab375e5333`; baseline P2 source `1a76e341098b54a639fec22eecea362cc243c46f`; control source `e07d0b5464bf472b2ca18993f3e196a234ff0fc5`. The benchmark runner was frozen at `c5b35775b62847bf2f535d61ea68db4a774bf838`. No S3 executable source changed after the final P2H gates.

The required S3 focused group passed (230 tests). Compileall, diff check, Linux native validation, E0, call order, synchronous callback reentry, repeated FFI, failure-context equivalence, and non-budget failure regression gates passed. Concurrent FFI entry remains NOT_QUALIFIED. The one full Linux x86-64 S3 suite at P2H SHA `6f320242...` completed with exit 0: 4,375 passed, 1 skipped, 0 failed. Transcript: `/home/vboxuser/tmp/s3-full-suite-p2h-6f320242.log`; SHA-256 `7949a455d2784f5196372e77a484758ff913c6d414aac37b083cfe4bf028e26a`. The benchmark runner and its 124-entry immutable raw manifest were subsequently preserved from the unique run `segment-budget-20260923-225935-431096547`.

P2H passed the P2 E0 corpus, all workload correctness oracles, reproducibility, P0 byte identity, and exact P2/P2H segment-plan identity. Its fast-path native instruction counts were unchanged or lower by one instruction, while slow-path counts increased by one; total static native instruction counts matched P2 in every cell. No `.text.unlikely` bytes were identified: cold executable text was zero for all variants. P2H total executable text was 28–283 bytes larger than P2, and added-text/hot-text recovery was negative in every cell. Therefore H12A is `NOT_CONFIRMED`, H12 is `SAFE_NOT_STRUCTURALLY_MATERIAL`, and the outcome is `CURRENT_P2_RETAINED`; no second hardening design is authorized.

| Workload | Opt | P2H/P2 | Added-text recovery | P2H budget-excess recovery |
| --- | --- | ---: | ---: | ---: |
| JSMN | O0 | 1.001516 | -0.1568% | 91.7987% |
| JSMN | O1 | 1.007682 | -0.1557% | 91.3202% |
| RMSD | O0 | 0.972085 | -0.3689% | 105.0707% |
| RMSD | O1 | 1.013410 | -0.3689% | 104.6673% |
| XSBench | O0 | 0.982988 | -0.1139% | 99.5955% |
| XSBench | O1 | 0.979516 | -0.1052% | 97.1546% |

All six runtime ratios are within the predeclared 1.05 limit and all six retained budget-recovery ratios exceed 0.50. The structural target did not improve, so this does not qualify as a cold-layout win or a code-size win. Full measurements, ELF/Assembly hashes, per-cell sizes and timings are in the benchmark validation report and machine-readable result.

The full benchmark suite was executed once at benchmark source `c5b35775b62847bf2f535d61ea68db4a774bf838`; its transcript reports `106 passed, 1 skipped in 1.48s`. The pytest summary is successful, but the outer wrapper failed after pytest while parsing an invalid shell `exit` expression, so a distinct pytest exit code was not captured. Transcript SHA-256: `55903d3cccb2355b2890d3c22ff01e5381f421a208645a86c6178d2ad6d1026a`. No rerun was made.

GitHub Actions at S3 HEAD `6f320242...` remain classified `CI_PRE_STEP_CAUSE_UNIDENTIFIED`: the three workflows completed in approximately 3–5 seconds and all jobs reported `steps=[]`; no logs identify a source failure or infrastructure cause. No workflow rerun was requested or made. PR #310 remains OPEN/DRAFT/UNMERGED. Production readiness remains false and is the next separate review; this hardening result does not promote P2 or P2H.
