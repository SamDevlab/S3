# S3 1.12 Capability Breakout - Final Report

## Status

This is a Draft-review candidate, not a merge or release. The campaign produced normal-pipeline compiler capabilities and passed the frozen Linux suite.

```text
S3_CAMPAIGN_BASE=a1ecc29908dfb42480376961927fd6c50552ecf3
S3_FUNCTIONAL_SOURCE_FREEZE=c89daae65aca69be775a395e971f3223ae3a21ce
S3_FUNCTIONAL_SOURCE_TREE=47e50dd14a5de0c8d329b1cd9b5e0a639bd0f6be
S3_FINAL_TESTED_HEAD=8d1bcfcad5930468b8b94bb7826e98b5ac7c3181
S3_FINAL_TESTED_TREE=85ddf72396dbc736cbf38b331a8a245dd32c39eb
```

The two commits after the source freeze contain test changes only. No production compiler source changed after `c89daae`.

## Capability Delta

- Same-color TMOV data movement is omitted in the production x86-64 emitter when two distinct virtual registers are proven to share the same non-stack physical register. Logical instruction/PER accounting, source initialization checks, and destination initialization metadata remain intact. Different-color and stack-endpoint moves retain the existing path.
- Loop analysis now carries a structured recurrence proof across relevant CFG continuations, uses loop-local update/store evidence instead of whole-function store counts, and distinguishes induction, ordered floating-point reduction, and unresolved carried state. Vector legality consumes the proof but still fails closed when memory-range or dependence evidence is missing.
- The historical research provenance check now distinguishes pinned experiment control identity from the checkout under test and accepts their SHAs being different while validating the pinned evidence.
- `docs/architecture.md`, `docs/roadmap.md`, and `docs/roadmap/ACTIVE_TRACK.md` were reconciled with the current register-allocation default and active compiler track.

```text
CI_PROVENANCE_FIX=PASS (focused regression; remote PR CI is separate)
CURRENT_REGISTER_ALLOCATION_DEFAULT=true
ARCHITECTURE_DRIFT_RECONCILED=YES
ACTIVE_TRACK_RECONCILED=YES
PRODUCTION_COMPILER_SOURCE_CHANGED=YES
NORMAL_PATH_BEHAVIOR_CHANGED=YES
SAME_COLOR_TMOV_ELISION=PRODUCTION_CANDIDATE
TMOV_ELISION_PRODUCTION_WIRED=YES
ANTI_LOOP_GATE=PASS
```

## Loop Findings

The five examined real-workload loops now classify as:

| Legality | Count | Reason |
| --- | ---: | --- |
| VECTORIZABLE | 0 | No complete range and inter-iteration dependence proof |
| NOT_VECTORIZABLE | 2 | Ordered strict-FP reductions cannot be reassociated |
| UNKNOWN | 3 | Access-range/dependence or call-effect facts remain unproven |

Continuation-aware recurrence recognition, loop-local store reasoning, and reduction classification are implemented and covered by generic cases. The bounded generated corpus covers 256 loop programs plus 64 metamorphic renamings with no failures. The remaining `UNKNOWN` results state missing proof obligations; they are not guessed safe.

```text
CONTINUATION_AWARE_LOOP_ANALYSIS=PASS
LOOP_LOCAL_STORE_REASONING=PASS
REDUCTION_ANALYSIS=PASS
DEPENDENCE_ANALYSIS=PARTIAL_FAIL_CLOSED
SIMD_PROTOTYPE=NOT_STARTED_NO_VECTORIZABLE_LOOP
```

## Independent Native Matrix

The independent Linux x86-64 candidate matrix is `EXP-S3-112-CANDIDATE-MATRIX-001`. Its spec and complete compact result are preserved in the S3-Benchmarks campaign report. Three pinned workloads passed reference and exact cross-variant output comparison.

The inspected AssemblyPrograms for the three workloads contained no eligible TMOV sites. Consequently BASE and CANDIDATE had identical binary hashes and identical `.text`, instruction, memory-reference, stack-reference, and frame metrics. All paired timing classifications were `INCONCLUSIVE`; this is not a speedup claim.

```text
STORE_LOAD_CAUSALITY=NO_ELIGIBLE_SITES_FOR_THIS_TRANSFORMATION_IN_THE_THREE_PINNED_WORKLOADS
STORE_LOAD_TIMING=INCONCLUSIVE
STORE_LOAD_PRODUCTION_CANDIDATE=NO
```

The earlier point-cloud STORE->LOAD timing signal was not causally explained by this matrix. No further repeat of that timing-only question is justified without a new discriminator.

## Validation

```text
WINDOWS_FOCUSED_GATE_AT_SOURCE_FREEZE=c89daae:152 passed, 153 skipped; later focused test additions passed separately
LINUX_FOCUSED_GATE=30 passed
GENERATED_LOOP_CASES=256 passed
METAMORPHIC_LOOP_CASES=64 passed
LINUX_FULL_SUITE_HEAD=8d1bcfcad5930468b8b94bb7826e98b5ac7c3181
LINUX_FULL_SUITE=4613 passed, 1 skipped, 0 failed, exit 0
```

The first Linux full-suite attempt exposed an environment-only Zig cache failure: `/` had no free blocks and Zig defaulted to `/home/vboxuser/.cache/zig`. The focused failing test passed after directing Zig caches to `/tmp`; the final full suite used that same isolated cache configuration and exited 0. No system cache was deleted or system disk policy changed. Transcript and exit marker remain outside the repository under `/tmp/s3-1.12-full-suite-final-confirm-8d1bcfca` and its `.log`/`.exit` files.

`PER_INSTRUCTION_DEFAULT=YES` and `STRICT_FP_PRESERVED=YES`.

## Closed and Deferred Lines

```text
STORE_LOAD_PRODUCTION_PROMOTION=REJECTED_FOR_NOW (no eligible sites in measured workloads; no causal timing claim)
SIMD=NOT_STARTED (no loop passed the full legality gate)
EXPERIMENTAL_OPTIMIZATION_MODE=NOT_JUSTIFIED (no generic non-O1-ready transform met its promotion contract)
LIFETIME_SHRINKING=NOT_TESTED
REMATERIALIZATION=NOT_TESTED
COLD_PATH_SPLITTING=NOT_TESTED
MACHINE_IR_JUSTIFIED=NO
MEMORY_SSA_JUSTIFIED=NO
ALLOCATOR_REDESIGN_JUSTIFIED=NO
PORTABLE_BACKEND_JUSTIFIED=NO
FRESH_STRUCTURALLY_DIFFERENT_WORKLOAD=NOT_RUN
```

The loop analysis is diagnostic-only and is not invoked by the normal compilation pipeline, so it adds no default compile-time work. The matrix did not separately time the x86-64 emission phase for the small same-color guard; compile-time overhead is otherwise unquantified. Do not infer it from native runtime timings.

## Campaign Summary

```text
PRODUCTION_FILES_CHANGED=3
NORMAL_PATH_BEHAVIOR_CHANGED=YES
NEW_COMPILER_CAPABILITIES=2 (same-color native move elision; structured loop recurrence classification)
RESEARCH_ONLY_TOOLS_ADDED=0
REPORT_FILES_ADDED=1
NEW_PRODUCTION_COMPILER_CAPABILITIES=
- Omit redundant same-physical-register TMOV data movement with S3 accounting preserved.
- Classify loop recurrences and strict-FP reductions in the normal compiler analysis path, reducing the five examined loops from five UNKNOWN to three UNKNOWN and two NOT_VECTORIZABLE.
```

`STOP_HUMAN_GATE=REVIEW_S3_1_12`. No merge, release, tag, PyPI publication, O1 default-policy change, or S3 1.13 work is part of this campaign.

```text
PRIMARY_NEXT_FRONTIER=General access-range and inter-iteration memory-dependence proof for the three remaining UNKNOWN workload loops.
SECONDARY_NEXT_FRONTIER=Find and independently measure eligible same-color TMOVs in a representative real workload before making a runtime claim.
```
