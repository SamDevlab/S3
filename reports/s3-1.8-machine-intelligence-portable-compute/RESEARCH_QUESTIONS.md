# S3 1.8 Research Questions and Baseline

## Provenance

- Campaign base: `f1342592aef1be7cc9fe0d390e0f3c6fc266af5a` (merge of S3 PR #321).
- Independent lab base: `2ca7b7802c630fec655e7826462e319fb773014c` (merge of S3-Benchmarks PR #25).
- S3 1.7 source candidate: `39dfbb5d19ecefc7df78da7dc8d3ea8e31d81df4`.
- S3 1.7 candidate tree/test snapshot: `f0c2963d` plus report commits `a4ae0d8d`, `f1d9d750`.
- Prior Linux suite evidence: 4,480 passed, 1 skipped, 0 failed; this is inherited evidence, not a 1.8 test run.
- PER default remains `PER_INSTRUCTION`; strict floating-point semantics remain unchanged.

## Initial Questions

| ID | Question | Final status | Evidence |
| --- | --- | --- | --- |
| RQ1 | Can reference-heavy functions be analyzed more precisely without weakening alias/reference safety? | PARTIAL | 8/8 modeled reference values had known origins and `NO_ESCAPE`; diagnostic-only and unknown calls remain conservative. |
| RQ2 | What fraction of residual native machine code can be attributed to compiler/runtime categories? | PARTIAL | 34.6%-39.3% of parsed emitted assembly instruction lines map to Assembly-op spans; the rest remain `UNMAPPED`. |
| RQ3 | Is Machine IR justified by concrete limitations of the current backend representation? | DEFERRED_WITH_EVIDENCE | No concrete missed optimization requiring a Machine IR was qualified; current Assembly-to-text lineage is partial. |
| RQ4 | How much residual stack/move traffic is allocator/liveness related? | PARTIAL | Static pressure, frame and stack-resident virtual-value counts exist; dynamic spills and runtime impact were not measured. |
| RQ5 | Which current loops are legally vectorizable under strict S3 semantics? | OPEN | Five loops were observed; all five remain `UNKNOWN`, with no recognized induction/bounds/dependence proof. |
| RQ6 | Does optimized PER materially change the historical EXACT/HYBRID conclusion? | INCONCLUSIVE | Historical PR #23/#24 data lack a matched 1.8 artifact and protocol. |
| RQ7 | Can the compiler reliably normalize verbose but correct agent-generated programs? | OPEN | Checked-in agent-named kernels are human-authored; no paired LLM-generated normalization experiment was run. |
| RQ8 | Which analyses are target-independent enough to support another backend? | PARTIAL | Reference and loop facts are IR-level; no second-target semantic execution or complete backend was qualified. |
| RQ9 | Can richer verification/fuzzing expose optimizer/backend bugs missing from existing tests? | PARTIAL | Existing deterministic O0/O1 differential cases passed; no new broad fuzz campaign or failure discovery. |
| RQ10 | What is the next dominant architectural bottleneck? | OPEN | Static attribution leaves most emitted assembly lines unmapped; no runtime profile identifies a dominant cost. |

## Inherited Baseline (S3 1.7)

The 1.7 register-initialization marker-elision experiment did not change the
selected real-world kernels' static assembly counts or paired runtime by a
material amount. The conservative proof tracked every register and admitted
zero safe reads in all three measured hot functions because they contain
reference targets:

| Workload | Registers tracked | Safe reads proven | Static instructions control/candidate | Result |
| --- | ---: | ---: | ---: | --- |
| `point-cloud-summary` | 368 | 0 | 4,746 / 4,746 | No material structural change |
| `raster-window-statistics` | 432 | 0 | 5,688 / 5,688 | No material structural change |
| `energy-aggregation` | 211 | 0 | 2,763 / 2,763 | No material structural change |

The independent paired benchmark found no material timing change within its
5% protocol threshold. This is evidence that the measured optimization was
ineligible on these kernels, not evidence that references are the sole cost
or that its safety gate should be relaxed.

## 1.8 Starting Capability Inventory

- Alias queries exist for memory IDs and frame-local cells; distinct symbolic
  index values conservatively remain `MayAlias`.
- Memory effects are opcode-level and calls are conservatively inferred from
  reference mutability. Region-specific interprocedural summaries are absent.
- Escape and reference-liveness summaries are absent.
- Codegen reports with source/IR/Assembly/native lineage and explicit unknown
  coverage are absent.
- A no-op-move candidate analysis exists, but it does not rewrite Assembly.
- Existing x86-64 and AArch64 pathways remain available; no backend default or
  PER policy is changed by this campaign.

## Guardrails

The first reference-analysis implementation is diagnostic-only. It must never
be used to relax initialization, alias, bounds, memory-effect, or vectorization
gates until a separate consumer-specific proof and regression suite qualify
that use.
