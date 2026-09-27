# S3 1.10 — Final Campaign Report

## Outcome

The campaign produced a bounded memory/value-locality analysis model, three
research-only transformation experiments, deterministic fuzz/metamorphic
evidence, a machine-readable proof contract, and independent pinned-SHA replay
through S3 1.10. The evidence does **not** justify enabling any transformation
in the production optimizer, changing defaults, or claiming a native runtime
speedup. The scientific foundation is complete for review; multiple research
questions remain open or partial.

```text
CAMPAIGN=S3_1_10_MEMORY_INTELLIGENCE_VALUE_LOCALITY_VERIFIED_TRANSFORMATIONS_AND_COMPILER_SCIENCE_EXPANSION
S3_CAMPAIGN_BASE=e27dff1e712e50271df9f860669cd714e28f4ce7
S3_CONTROL_SHA=e27dff1e712e50271df9f860669cd714e28f4ce7
S3_FUNCTIONAL_SOURCE_FREEZE=856bf0cd60c3da6ba701adec73c7858d063739a7
S3_FUNCTIONAL_SOURCE_TREE=5d7c179ac9df64fad99b7ec140f69571c48b866f
S3_BRANCH=feat/s3-1.10-memory-intelligence-value-locality
PER_INSTRUCTION_DEFAULT=YES
PER_SEMANTICS_PRESERVED=YES
STRICT_FP_PRESERVED=YES
SOURCE_CHANGED_AFTER_FREEZE=NO
```

The candidate is research-scoped: the availability analysis and rewrites are
not called by the production optimizer. The only pre-existing test-file edit
is a line-ending-portable canonical source hash check; no fixture was changed.

## Validation

The focused S3 gate passed with `53 passed, 9 skipped`; `python -m compileall
bootstrap/s3 tools` passed; `git diff --check` passed. The required complete
Linux suite was run on the exact frozen SHA using Python 3.14.4 on Linux
x86-64. Its first attempt completed with one environmental failure because
Zig wrote its cache to the full root filesystem (`NoSpaceLeft`). The focused
failing test passed after redirecting Zig's local/global caches to `/tmp`,
then one final full suite completed with exit code zero:

```text
FULL_SUITE_HEAD=856bf0cd60c3da6ba701adec73c7858d063739a7
FULL_SUITE_START_UTC=2026-09-27T20:47:39.038723+00:00
FULL_SUITE_END_UTC=2026-09-27T22:03:29.843132+00:00
FULL_SUITE_TERMINAL=YES
FULL_SUITE_EXIT=0
NATIVE_LINUX=PASS
```

The final suite transcript and status are retained on the Linux guest under
`/tmp/s3-1.10-full-856bf0cd/full-suite-final.log` and
`/tmp/s3-1.10-full-856bf0cd/full-suite-final-status.txt`. No production or
test logic changed after the tested source freeze; only reports and lab
evidence followed.

## Memory and Transformation Findings

Storage identity and availability are bounded to known memory objects and
exact constant/SSA indices. The analysis uses CFG dataflow and conservative
alias/effect kills; divergent values, uncertain loop-carried state, may-alias
writes, and unknown calls fail closed. This is useful proof input, not general
MemorySSA or unrestricted alias analysis.

Three research-only transformations were evaluated:

| Experiment | Eligible energy / point-cloud / raster | Result |
| --- | --- | --- |
| STORE→LOAD forwarding | 12 / 39 / 18 | Point cloud crossed the 5% timing materiality threshold, but static memory references increased in all workloads (raster +228); not suitable for promotion. |
| Cross-block LOAD→LOAD via temporary copies | 10 / 25 / 22; hot-only 6 / 11 / 11 | Raster was a material native regression. Static memory references rose by 13 / 18 / 270 (hot-only raster +229). Rejected as a general transform. |
| Dominating SSA-value substitution | 2 / 2 / 6 | Correctness passed and static `.text`, instructions, and memory references fell for all three workloads; all paired timing intervals overlap 1, so runtime result is inconclusive. Raster stack-resident virtuals rose 6→22 and peak live 11→12. Research-only. |

For the SSA-value substitution, `.text` changed `36,304→35,954`,
`58,112→57,762`, and `68,491→67,549` bytes. Static memory references
changed `953→943`, `1,601→1,591`, and `1,898→1,895`. Paired timing
classifications were `INCONCLUSIVE` for all workloads. PMU counters were
unavailable by policy (`perf_event_paranoid=4`); no cycle, retired-operation,
or microarchitectural cause is claimed.

The exact-cell same-block mutable-load hypothesis remains
`REJECTED_NO_ELIGIBLE_REPEATED_MUTABLE_LOADS` (0/220 eligible sites). The
temporary-copy LOAD→LOAD raster regression is a separate measured negative
result. Neither should be relabeled as the stricter direct SSA rewrite.

## Compiler and Observatory Status

| Capability | Final status | Evidence / limit |
| --- | --- | --- |
| Memory-origin analysis | PARTIAL | Bounded memory-object/index facts; unknown origins remain conservative. |
| Storage identity | BOUNDED | Exact known-object and index identities; no unrestricted pointer identity. |
| Memory versioning | PARTIAL | Store/effect kill reasoning in the bounded availability analysis; no general MemorySSA. |
| Value availability / cross-block dataflow | PARTIAL | CFG joins and kill conditions are tested; ambiguity fails closed. |
| Alias analysis | PARTIAL | Known exact cells distinguished; may-alias/unknown cases conservatively invalidate. |
| Effect analysis | PARTIAL | Relevant writes/calls conservatively invalidate; unknown calls are not assumed pure. |
| Interprocedural effects | OPEN | No general summaries/propagation established. |
| Escape and lifetime | OPEN | No general escape/lifetime authority established. |
| Transformation authority | EXPERIMENTAL_RESEARCH_ONLY | Three proof-gated contracts; none is production-wired. |
| Native move/control attribution | PARTIAL | Broad categories only; no semantic/ABI/allocator move split or dynamic edge classification. |
| Native Observatory | v4, inherited | Whole-object attribution: 2,506/7,239 instructions mapped and 4,733 unmapped. Profiled-block joins are a different scope. |
| Dynamic structural profile | PASS_INHERITED_1.9 | Logical block-entry counts; not hardware event counts. |
| Register pressure/value residency | PARTIAL | Static allocator reports; stack-resident values are not called spills. Allocator redesign is not justified. |
| Vector legality | PARTIAL | 5 UNKNOWN, 0 proven vectorizable, 0 proven illegal; SIMD not justified. |
| MemorySSA / Machine IR | DEFERRED_WITH_EVIDENCE | Current bounded proof/rewrite works without either; no representation blocker demonstrated. |
| Fuzz / metamorphic | PASS_BOUNDED | 24 deterministic programs, 12 independent-write pairs, 0 failures. Not broad coverage. |
| Optimization contracts | PASS_RESEARCH_ONLY | Required facts, proof checks, rewrite, postconditions, and fallback are machine-readable; production optimizer does not consume them. |
| Cost model | OPEN | Three workloads are insufficient for a predictive model. |
| Agent-native experiment | NOT_STARTED | No pinned real agent-generated corpus. |
| Compute profile / execution context | DEFERRED | Existing facts do not justify new runtime/context machinery. |
| Parallel legality | UNKNOWN | No runtime parallel execution or complete dependence authority. |
| Portability | NOT_JUSTIFIED | No second target consumer established. |

The inherited hot-region structural weights are broad MOVE 33.3–36.6% and
CONTROL_FLOW 31.4–33.7%, with UNKNOWN 20.5–21.5%. These are weighted static
machine-syntax estimates joined to logical block entries, not shares of
runtime or hardware work. Full values and provenance are in
`MOVE_CONTROL_CHARACTERIZATION.md`.

## Independent Bench Replay

Bench PR #27 is merged at
`b11526443b9f2ac50f2ffdd3c4a6c1d0a2471152`. The independent Bench executor
replayed exact S3 SHAs 1.5–1.10 on Linux x86-64; all six versions passed all
three workload correctness gates. The 1.5–1.9 historical group and 1.10
single-SHA replay were run separately. Host, toolchain, workload inputs,
protocol, and output identities are checked by the compatibility index, but
the groups were not interleaved, so cross-version timing is descriptive only.

```text
S3_1_10_REPLAY=PASS
S3_1_10_REPLAY_SHA=856bf0cd60c3da6ba701adec73c7858d063739a7
CROSS_VERSION_COVERAGE=1.5_TO_1.10
BENCH_MEASUREMENT_CLASS=CHARACTERIZATION_ONLY
NATIVE_SPEEDUP_CLAIM=NO
```

The six-version index is
`reports/s3-1.10-memory-intelligence-lab/CROSS_VERSION_COMPATIBILITY_INDEX.json`.
Its SHA-256 is `f25d0165d8a3be2f1fa04793cb5107b19f9235af1b0ab5b3441c49908a3fd38b`.
Bench's final full-suite result and PR head are recorded in that repository's
`FINAL_REPORT.md` and PR metadata.

## Research Questions and Next Frontier

RQ1–6, RQ8–13 are partial; RQ7 and RQ14–16 remain open; RQ17–19 are
deferred with evidence; RQ20 remains open. Per-question evidence is in
`RESEARCH_QUESTIONS.md`. Historical Bench PRs #15, #23, and #24 were reviewed
read-only and each is recommended `KEEP_OPEN_WITH_REASON`; none was changed.

```text
MEMORY_OPTIMIZATION_NEXT=YES — only bounded proof-gated experiments; native timing remains inconclusive.
MACHINE_IR_NEXT=NO — no current representation blocker.
MEMORY_SSA_NEXT=NO — bounded exact-cell facts suffice for measured candidates.
REGISTER_ALLOCATOR_NEXT=NO — pressure signal exists, but no causal runtime evidence.
VECTOR_EXECUTION_NEXT=NO — no proven vectorizable loop.
PORTABLE_BACKEND_NEXT=NO — no second-target consumer.
EXECUTION_CONTEXT_NEXT=NO — no experiment requires it.
PARALLEL_COMPUTE_NEXT=NO — dependence proof and runtime are absent.
ACCELERATOR_RESEARCH_NEXT=NO — no grounded consumer.
AGENT_NATIVE_NEXT=NO — no controlled generated corpus.
COMPILER_AUTONOMY_NEXT=NO — explanations/contracts exist; automatic source change or promotion remains unauthorized.
NEXT_CAMPAIGN=UNSELECTED
```

## Evidence Hygiene and Publication

The S3 campaign report directory currently contains 16 files totaling 181,933
bytes before this final report. The largest experiment records are compact
structured JSON; no large binary snapshots were committed. The retention
policy is in `EVIDENCE_POLICY.md`. The Bench lab's final evidence-size
inventory is recorded in its final report.

No transformation was promoted, no compiler default changed, and no historic
PR was altered. The two campaign branches are intended for Draft PRs against
`main`; this report does not authorize merge, release, tag, PyPI publication,
or a preselected 1.11 campaign.
