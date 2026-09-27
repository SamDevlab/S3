# Memory Transformation Experiments

## Scope and controls

These are research-only transformations. None is called from the compiler's
production optimization pipeline. Each candidate was produced from the same
O1 IR as its control, checked by the IR verifier and initialization analysis,
and compared against the reference and exact baseline native output before
timing. The Linux runs used x86-64, Python 3.14.4, Ubuntu `cc` 15.2.0, three
warmups, 21 paired samples of 1,000 calls, and alternating paired order with
seed 3110. The 95% percentile interval is a 10,000-resample bootstrap over
paired baseline/candidate ratios, using the existing 1.9 summary function.
The materiality band is 5%. PMU is unavailable by policy
(`perf_event_paranoid=4`); these timings are characterization only.

The S3 control is `e27dff1e712e50271df9f860669cd714e28f4ce7`. Workload source
identities are the canonical LF hashes already pinned by the 1.9 profile:

| Workload | Source SHA-256 |
| --- | --- |
| energy | `a146f2ec7bd7f9bf72ea35c04026174874012acdb31541d805bf5f0a4a613c84` |
| point cloud | `59e752e91159ece4e3a813bc8586f338544ddac52e4b5e755a219d85779238e9` |
| raster | `6d5d8081991d05e7f89ebe6965bb6664b8f11c33595e062c1b165b0a44c9763e` |

## EXP-S3-110-STORE-LOAD-001

The bounded exact-cell dataflow found 12, 39, and 18 forwardable loads for
energy, point cloud, and raster respectively. The experiment copies each
proven stored SSA value into a fresh temporary at every reaching store and
replaces eligible loads. It does not alter production lowering.

| Workload | Eligible | `.text` bytes | Instructions | Memory refs | Stack refs | Frame bytes | Branches | Paired ratio and 95% CI | Classification |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| energy | 12 | 36,304 → 35,546 | 2,754 → 2,718 | 953 → 1,001 | 907 → 955 | 2,144 → 2,160 | 789 → 771 | 1.0297 [1.0199, 1.0351] | NO_MATERIAL_CHANGE_WITHIN_5_PERCENT |
| point cloud | 39 | 58,112 → 55,105 | 4,732 → 4,609 | 1,601 → 1,604 | 1,536 → 1,539 | 3,648 → 3,728 | 1,367 → 1,305 | 1.1110 [1.0729, 1.1252] | MATERIAL_IMPROVEMENT |
| raster | 18 | 68,491 → 68,054 | 5,666 → 5,614 | 1,898 → 2,126 | 1,821 → 2,049 | 4,192 → 4,240 | 1,715 → 1,689 | 1.0367 [1.0193, 1.0652] | INCONCLUSIVE |

Only point cloud crossed the predefined material threshold. This does not
support general promotion: all three candidates increased static memory and
stack references, including raster by 228. Raw result SHA-256:
`8b5d6efbe71a5122987e3b5adcd9ab7ab7b22e071926e75add7e02c4b32c616a`.

## EXP-S3-110-LOAD-001

The distinct LOAD→LOAD analysis considers only direct exact-cell loads whose
previous loaded SSA value is available on every reachable CFG path and whose
source is in another block. May-alias stores, calls, indirect writes, and
unclassified effects invalidate availability. Divergent incoming SSA values
do not qualify. Same-block-only sites are excluded.

| Workload | Direct load sites | Cross-block sites | Profile-hot sites | Logical destination-block visits |
| --- | ---: | ---: | ---: | ---: |
| energy | 44 | 10 | 6 | 505 |
| point cloud | 91 | 25 | 11 | 684 |
| raster | 85 | 22 | 11 | 620 |

The visit sum is a join to the correctness-checked 1.9 logical block profile,
not hardware counts or a claim that each opportunity saves a native memory
operation. The reproducible discovery artifact has SHA-256
`744bd98e66ed4cd08975d7e81c0bf5fcd8eba2ab77161065eaae09cf4fcbdc7d`.

Native candidate results:

| Workload | Reused loads | `.text` bytes | Instructions | Memory refs | Stack refs | Frame bytes | Branches | Paired ratio and 95% CI | Classification |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| energy | 10 | 36,304 → 35,894 | 2,754 → 2,760 | 953 → 966 | 907 → 920 | 2,144 → 2,208 | 789 → 783 | 0.9877 [0.9641, 1.0062] | NO_MATERIAL_CHANGE_WITHIN_5_PERCENT |
| point cloud | 25 | 58,112 → 57,149 | 4,732 → 4,767 | 1,601 → 1,619 | 1,536 → 1,554 | 3,648 → 3,840 | 1,367 → 1,355 | 0.9613 [0.8675, 1.0442] | INCONCLUSIVE |
| raster | 22 | 68,491 → 68,782 | 5,666 → 5,708 | 1,898 → 2,168 | 1,821 → 2,091 | 4,192 → 4,368 | 1,715 → 1,709 | 0.7963 [0.7861, 0.8622] | MATERIAL_REGRESSION |

Although Assembly `TLOAD` count fell by 10/25/22, the emitted native
memory-reference count rose by 13/18/270. This is the key result: source-level
load elimination did not imply machine-level memory traffic reduction. Raw
timing/object result SHA-256:
`64bc3855513231978d151379ff7f8b1e4a7acb090f9790ce9e668c6e7e62085b`.
Post-hoc paired analysis SHA-256:
`fa9db977332a51b82b0a38780da166313eeab9026bd849b7ba25eeac83dcf83e`.

## Profile-hot ablation: EXP-S3-110-LOAD-HOT-001

To test whether cold sites were driving the cost, the same transformation was
restricted to candidate loads in blocks with nonzero visits in the pinned 1.9
logical profile. This reduced selected sites from 10/25/22 to 6/11/11, but did
not remove the native cost:

| Workload | Reused loads | `.text` bytes | Instructions | Memory refs | Stack refs | Frame bytes | Branches | Paired ratio and 95% CI | Classification |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| energy | 6 | 36,304 → 36,214 | 2,754 → 2,772 | 953 → 971 | 907 → 925 | 2,144 → 2,192 | 789 → 789 | 1.0286 [0.9976, 1.0440] | NO_MATERIAL_CHANGE_WITHIN_5_PERCENT |
| point cloud | 11 | 58,112 → 57,915 | 4,732 → 4,773 | 1,601 → 1,620 | 1,536 → 1,555 | 3,648 → 3,760 | 1,367 → 1,367 | 1.0365 [1.0113, 1.0995] | INCONCLUSIVE |
| raster | 11 | 68,491 → 69,107 | 5,666 → 5,699 | 1,898 → 2,127 | 1,821 → 2,050 | 4,192 → 4,304 | 1,715 → 1,715 | 0.8584 [0.8298, 0.9137] | MATERIAL_REGRESSION |

Hot-only raster still adds 229 static memory references and remains a material
regression. Raw result SHA-256:
`86ff049889c165220f3ec9d19dd197a6d1bb16f9cbadd86230d20378481a9192`.
Paired analysis SHA-256:
`08d4a90ef8ed45da47fa00d971763655017f326209d2abcaa31a6d994b47d0c5`.

## Dominating SSA-value substitution: EXP-S3-110-LOAD-SSA-001

The temporary-copy implementation extended liveness and substantially
increased stack traffic. A second lowering strategy was therefore tested: use
the same conservative availability facts, but remove a repeated LOAD only
when its unique source SSA LOAD dominates the target, source/target IR
register definitions are unique, and the target value has no phi use. The
rewrite maps the target SSA def-use chain to exact original IR operands; phi
mediated sites, ambiguous register identities, unknown effects, and
non-dominating sources remain unchanged. This avoids the general SSA-to-IR
conversion, whose memory-observable phi expansion was independently rejected
by the normal verifier for undefined values.

The deterministic test corpus proves that the loop-carried target with a phi
use is not rewritten, while a non-phi exit target is removed. The mutating
control continues to retain its reload. IR verification, initialization
analysis, and hosted execution all pass. On the three pinned kernels, 2/2/6
loads were eligible for this stricter rewrite.

| Workload | Forwarded | `.text` bytes | Static instructions | Memory refs | Stack refs | Frame bytes | Branches | Paired ratio and 95% CI | Classification |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| energy | 2 | 36,304 → 35,954 | 2,754 → 2,728 | 953 → 943 | 907 → 897 | 2,144 → 2,128 | 789 → 781 | 1.1399 [1.0036, 1.2075] | INCONCLUSIVE |
| point cloud | 2 | 58,112 → 57,762 | 4,732 → 4,706 | 1,601 → 1,591 | 1,536 → 1,526 | 3,648 → 3,632 | 1,367 → 1,359 | 1.0098 [0.9445, 1.1386] | INCONCLUSIVE |
| raster | 6 | 68,491 → 67,549 | 5,666 → 5,588 | 1,898 → 1,895 | 1,821 → 1,818 | 4,192 → 4,144 | 1,715 → 1,691 | 0.9635 [0.8597, 1.0938] | INCONCLUSIVE |

All three exact native outputs matched both the baseline and reference before
timing. Static text, instruction, memory-reference, and frame counts fell in
each workload; raster nevertheless increased allocator stack-resident
virtuals from 6 to 22 and peak live values from 11 to 12. The paired timing
intervals overlap 1 and all three classifications are inconclusive. PMU is
unavailable, so this is not a runtime speedup or microarchitectural claim.
The results show that avoiding the fresh temporary reverses the previous
native-memory-reference regression (10/10/3 fewer references than baseline),
but strict phi/register eligibility sharply limits coverage and the raster
allocator cost remains visible.

Raw native evidence SHA-256 `283fd652336b9ea3751ae0d46781969de1d7c673c7a860c00005ba94f21e5a4c`
(18,757 bytes); paired analysis SHA-256
`18dc3d3ea67c9186b170afb191f95c631476bf179ea02ee6827d6c951871fe1c`.

## Allocator and value-residency evidence

The static codegen/allocation report matches the reported native frame sizes.
The relevant figures are:

| Workload | Candidate | Virtual regs | Stack-resident virtuals | Peak live | Frame bytes |
| --- | --- | ---: | ---: | ---: | ---: |
| raster | baseline | 432 | 6 | 11 | 4,192 |
| raster | STORE→LOAD | 437 | 139 | 14 | 4,240 |
| raster | LOAD→LOAD all | 451 | 138 | 14 | 4,368 |
| raster | LOAD→LOAD hot | 443 | 117 | 13 | 4,304 |
| point cloud | baseline | 368 | 0 | 7 | 3,648 |
| point cloud | LOAD→LOAD all | 387 | 1 | 11 | 3,840 |
| point cloud | LOAD→LOAD hot | 379 | 0 | 10 | 3,760 |
| energy | baseline | 211 | 0 | 10 | 2,144 |
| energy | LOAD→LOAD hot | 217 | 5 | 11 | 2,192 |

This supports a static allocator/materialization cost as a likely explanation
for the increased native memory references, particularly for raster; it does
not prove dynamic spills or a microarchitectural cause. The report explicitly
records `dynamic_spills=null` and must not be interpreted as a spill count.
Allocator report SHA-256:
`7dfc553ce802e5cca58f02f3c85325e895c1bd251ab491c3d340422329d3cb23`.

## EXP-S3-110-FUZZ-001: bounded optimizer and metamorphic checks

The deterministic generator uses seeds 3100–3111 and creates forward/reversed
independent writes for each seed (24 programs total). Every program is checked
against the S3 reference execution and both O0 and O1 IR execution. The
research-only STORE→LOAD and cross-block LOAD→LOAD candidates are then executed
and compared with the same expected result. Each generated O1 function must
also contain at least one proof-reported eligible site for each transformation,
and the transformation counts must match their analysis reports exactly.

All 24 programs passed. All 12 independent-write ordering pairs were
metamorphically equivalent; there were no failures. This is bounded generated
coverage, not a replacement for directed or full-suite validation. The raw
JSON evidence has SHA-256
`bed0c61df82849543979a5a41d4bf5fe662e97c01e40115c8bbeb2a0a2ca7e6e`.

## Decision

- Cross-block exact-cell availability is proven for a bounded model and
  useful as a diagnostic/proof input.
- The research-only STORE→LOAD prototype has nonzero sites and one material
  workload result, but raises memory traffic on every workload; no production
  promotion is justified.
- The research-only LOAD→LOAD prototype is not generally beneficial. A
  hot-only restriction does not resolve the raster regression.
- The direct SSA-value substitution variant reduces static native memory
  references and code size, unlike the temporary-copy version, but its
  workload timing is inconclusive and its strict no-phi/unique-register gate
  accepts only 2/2/6 sites. It is research evidence, not production authority.
- The measured raster residency increase remains a concrete allocator
  interaction signal, but does not justify allocator redesign or Machine IR:
  the dynamic cost is unproven, PMU is unavailable, and no general material
  runtime benefit was established.
- No transformation is enabled by default or wired into the production
  optimizer.
