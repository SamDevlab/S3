# S3 1.9 Native Observatory and Optimization Discovery

## Scope and provenance

This report closes the S3 1.9 native-observatory continuation, building on the
integrated S3 1.8 research line. The compiler source was frozen at commit
`211b1aecec756be42516322429720018f54001e7`, tree
`08289d214832e856d46e14ef941239649e9f4063`. The branch adds research tools,
tests, and evidence; no tracked compiler, runtime, standard-library, or
production optimization source was changed. The campaign does not promote a
budget mode or compiler optimization.

S3-Benchmarks 1.9 independently used that same clean source commit/tree. The
independent run and its raw provenance are in
`SamDevlab/S3-Benchmarks:reports/s3-1.9-native-observatory-lab/experiments/EXP-S3-19-NATIVE-OBS-001.json`.

## Evidence summary

The native Observatory v4 accounts for every `.text` byte as attributed,
unmapped, or undecoded. Instruction-origin coverage remains partial:

| Workload | `.text` bytes | Instructions mapped | Mapped fraction | Attributed / unmapped / undecoded bytes |
| --- | ---: | ---: | ---: | ---: |
| point cloud | 58,106 | 4,216 / 11,151 | 37.8083% | 22,864 / 35,242 / 0 |
| raster | 68,482 | 5,125 / 13,034 | 39.3202% | 27,721 / 40,761 / 0 |
| energy | 36,295 | 2,506 / 7,239 | 34.6180% | 13,525 / 22,770 / 0 |

These are structural reports from the standalone native code-generation path,
not dynamic instruction or cycle counts. The point-cloud repeat reproduced
the same `.text` hash, machine rows, function rows, and plain object hash.
DWARF-containing object files were not byte-identical; debug metadata is not
part of that determinism claim.

The separate correctness-checked logical-block profile counts block entries
and weights them by static native instruction rows. Memory-origin categories
contribute about 48-52% of this estimated structural weight. This is not a
hardware retired-instruction count and does not establish a causal runtime
bottleneck. PMU access was unavailable by policy (`perf_event_paranoid=4`).

Three matched native workload runs used the same Linux x86-64 host, pinned S3
source, datasets, correctness gates, FFI timing scope, 3 warmups, 21 samples,
1,000 iterations per sample, paired order seed 1501, and 10,000 bootstrap
resamples. Point-cloud EXACT_SEGMENT and LOOP_HYBRID classifications repeated
as material; raster EXACT_SEGMENT repeated as material while HYBRID remained
inconclusive. Energy classifications differed between runs and remain
inconclusive. O0/O1 differences were not material in this sample; Compact-EA
was not applied to these kernels. This is characterization only. PER remains
the default and no speedup or policy-promotion claim is made.

Reference reports model 8 references across the three pinned workloads: all
8 have known origins and `NO_ESCAPE`, 3 are mutable, and no unknown effect was
reported in this modeled set. These diagnostic facts explicitly do not
authorize a transformation. The bounded exact-cell same-block load-forwarding
experiment preserved correctness but found 0 eligible loads among 220; the
tested rule is rejected for these workloads, while broader memory-origin
analysis remains open.

The v4 static allocation records cover 1,024 virtual registers, 6
stack-resident virtuals in one function, and a maximum peak-live value of 11.
Dynamic spills were not measured. Static stack residence is not a runtime
spill counter or proof that register allocation causes the measured workload
cost; allocator replacement is not selected.

The current vector-legality reports cover 5 loops: 0 proven vectorizable, 0
proven illegal, and 5 `UNKNOWN`. All five lack proof of canonical affine
induction, access range/immutable origin, and general inter-iteration memory
dependence. No SIMD or parallel transformation was attempted.

## Capabilities and maturity

| Area | Result |
| --- | --- |
| Reference, effect, escape analysis | `PARTIAL`; current workload facts are diagnostic, not transformation authority |
| Alias and memory model | `PARTIAL`; conservative where alias/dependence proof is absent |
| Codegen provenance and native report | `PARTIAL`; complete byte accounting, roughly 35-39% mapped instruction origins |
| Optimization explanation and discovery ranking | `PARTIAL`; v3 validates pinned evidence and ranks hypotheses, but does not authorize edits |
| Pass-effect metrics | `PARTIAL`; bounded experimental candidate has 0/220 eligible loads; no production pass delta |
| Machine IR and verifier | `DEFERRED_WITH_EVIDENCE`; no concrete representation blocker was established |
| Machine optimizer / allocator rewrite | `NOT_STARTED`; static pressure evidence does not establish runtime cause |
| Vector legality | `PARTIAL`; all 5 loops remain unknown |
| SIMD | `NOT_JUSTIFIED` by current legality evidence |
| Target model, ARM64, WASM | `NOT_STARTED`; no alternate-target toolchain qualification in this campaign |
| Differential native correctness | `PARTIAL`; pinned workload/reference correctness gates passed, but no experimental machine pipeline exists |
| Metamorphic testing and fuzzing | `NOT_STARTED` in this campaign |
| Agent-generated code analysis/feedback | `NOT_STARTED` |
| Execution context and execution certificate | `DESIGN` / `NOT_STARTED`; no evidence requires a new context prototype |
| Binary metrics | `PARTIAL`; static object/function reports are available |
| Compile-time metrics | `NOT_MEASURED` |

`PER_INSTRUCTION_DEFAULT=YES`. `PER_SEMANTICS_PRESERVED=YES` and
`STRICT_FP_PRESERVED=YES`: compiler semantics were not changed. Native
structural generation passed on Linux x86-64. No hardware-counter, dynamic
spill, SIMD, alternate-target, or universal speedup claim is made.

## Research questions

| ID | Status | Evidence in one line |
| --- | --- | --- |
| RQ1 | PARTIAL | v4 accounts for `.text` bytes; 34.6-39.3% of whole-object instructions map to origins, with no established material gain over 1.8. |
| RQ2 | PARTIAL | Correctness-checked logical block counters identify hot blocks, not hardware events or cycles. |
| RQ3 | PARTIAL | Memory origins are 48-52% of structural weight, with substantial control, constants, moves, and compute. |
| RQ4 | PARTIAL | Budget-policy observations repeat on selected workloads; no general compiler transformation with measured impact is established. |
| RQ5 | PARTIAL | 8/8 modeled references are known-origin and no-escape, but transformation authority remains false and forwarding eligibility is 0/220. |
| RQ6 | PARTIAL | EXACT repeats for point cloud/raster; HYBRID repeats for point cloud; energy remains cross-run inconclusive. |
| RQ7 | PARTIAL | One exact pinned S3 SHA was independently checked out, built, and correctness-validated by the lab executor. |
| RQ8 | OPEN | No cross-version replay under a common preserved protocol was performed. |
| RQ9 | OPEN | All 5 continuity loops remain vector-legality unknown; no richer analysis was added. |
| RQ10 | PARTIAL | Static allocation facts do not correlate individual values with runtime memory cost; dynamic spills remain unmeasured. |
| RQ11 | OPEN | Three workloads and one replication do not establish structural-metric/runtime correlation. |
| RQ12 | OPEN | No new bounded fuzzing or metamorphic campaign ran. |
| RQ13 | OPEN | No pinned agent-generated corpus or controlled feedback trial exists. |
| RQ14 | OPEN | Current evidence does not establish a need for an ExecutionContext architecture. |
| RQ15 | OPEN | Effects, dependence, portability, and resource facts are insufficient for a qualified compute profile. |
| RQ16 | DEFERRED_WITH_EVIDENCE | No verified Machine IR blocker, vectorizable loop, allocator-dominant cost, second-target correctness, or parallel contract selects those frontiers. |

## Negative results and next frontier

- Exact-cell mutable-load forwarding was rejected for the tested workloads:
  0/220 loads satisfied its exact same-block preconditions. This does not
  reject broader alias-aware or cross-block memory-origin analysis.
- SIMD is not justified while all five loops lack induction, range/origin, and
  dependence proofs.
- Machine IR and allocator replacement are not selected without a concrete
  representation limitation or causal runtime evidence.
- EXACT/HYBRID remain characterization results; PER remains the default.
- PMU, dynamic spill, compile-time, ARM64, and WASM measurements are
  unavailable or not performed, not zero.

The next primary research direction is a bounded, evidence-driven
memory-origin/value-locality investigation, with native move/control lowering
as a secondary question. Ranking v3 places these hypotheses after the
repeated budget-policy signal; the exact local forwarding rule remains
rejected. Any new candidate must first state a falsifiable rule and show
eligible operations on a pinned workload before native timing. Do not infer
PMU or causal benefit from current structural weights.

## Validation and publication boundary

- S3 focused Windows campaign tests: 27 passed, 1 skipped.
- S3 focused Linux campaign tests: 28 passed.
- Full Linux suite, Python 3.13.15: 4,518 passed, 1 skipped, 0 failed;
  exit 0; elapsed 4,958 seconds. HEAD was the exact source freeze above.
- Targeted `compileall` and `git diff --check`: passed.
- The immutable terminal status and transcript are preserved under
  `evidence/validation/`.
- Full-suite transcript SHA-256:
  `3976975fb32cc1c045789e0fcaf3e695eaa83fb2e311e3d3c1a20c9e6df58a5b`;
  terminal status SHA-256:
  `6dcb58715eb5afb0542a0fef2b1bf101dca48fb7f738ebabd4f7e6b62c2a86ba`.
- S3 1.7 PR #321 and Benchmarks 1.7 PR #25 are integrated. Historical
  Benchmarks PRs #15, #23, and #24 remain separate open Drafts; this campaign
  does not modify or stack them.

This is a research-only Draft PR. No merge, tag, release, PyPI publication,
default promotion, production compiler edit, or automatic S3 1.9 successor
campaign is authorized by this report.
