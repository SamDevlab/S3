# S3 1.8 Final Research Report

## Scope and provenance

Campaign: `S3_1_8_MACHINE_INTELLIGENCE_VERIFIED_OPTIMIZATION_PORTABLE_COMPUTE_AND_COMPILER_SCIENCE_LAB`.

| Item | Value |
| --- | --- |
| S3 campaign base | `f1342592aef1be7cc9fe0d390e0f3c6fc266af5a` |
| S3 functional source freeze | `b8f446a5ea2b24b948a263cb955f426c5d0f48ce` |
| S3 source tree | `ee71518080df40ff98c28fa07f7f9f8301d7943a` |
| Inherited S3 1.7 source candidate | `39dfbb5d19ecefc7df78da7dc8d3ea8e31d81df4` |
| Independent lab base | `2ca7b7802c630fec655e7826462e319fb773014c` |
| PER default | `PER_INSTRUCTION` (unchanged) |
| Strict FP | Preserved |

The 1.8 source additions are diagnostic/research tooling and an optional
emitter-origin sidecar. Default emitted output, optimization policy, resource
semantics and language behavior were not promoted or changed by these reports.
S3 `origin/main` remains the campaign base; this branch is intentionally not
merged.

## Final research questions

| ID | Status | Evidence / limit |
| --- | --- | --- |
| RQ1 | PARTIAL | 8/8 modeled reference values across the three workloads have known origins and `NO_ESCAPE`; analysis is diagnostic-only, not transformation authority. |
| RQ2 | PARTIAL | 34.6%-39.3% of parsed emitted assembly instruction lines map to Assembly-op spans; remaining lines are explicitly `UNMAPPED`. |
| RQ3 | DEFERRED_WITH_EVIDENCE | No concrete missed optimization required a new Machine IR; a new representation is not justified by abstraction preference alone. |
| RQ4 | PARTIAL | Static liveness, frame and stack-resident counts exist; no dynamic spills, PMU events or runtime effect were measured. |
| RQ5 | OPEN | Five natural loops were observed; all five remain `UNKNOWN` because induction, access and dependence proofs were not recognized. |
| RQ6 | INCONCLUSIVE | Historical EXACT/HYBRID work is not comparable to a matched 1.8 artifact/protocol. |
| RQ7 | OPEN | Agent-named checked-in kernels are deterministic human-authored samples; no LLM-generated paired normalization/equivalence trial occurred. |
| RQ8 | PARTIAL | Reference and loop facts are target-neutral at the current IR layer; no alternate target executed the same semantic corpus. |
| RQ9 | PARTIAL | Existing seeded O0/O1 differential tests passed; no new broad fuzz campaign or new miscompile was established. |
| RQ10 | OPEN | Static reports show attribution gaps, not a runtime bottleneck. No dominant runtime cause is claimed. |

## Semantic and memory analysis

- `REFERENCE_ANALYSIS=EXPERIMENTAL`; `ALIAS_ANALYSIS=PARTIAL`;
  `EFFECT_ANALYSIS=PARTIAL`; `ESCAPE_ANALYSIS=EXPERIMENTAL`;
  `MEMORY_MODEL=PARTIAL`.
- In the modeled continuity workloads, all eight reference values had known
  origins, complete local-function observations and `NO_ESCAPE` classifications.
- The analysis records local read/write uses and keeps unknown calls,
  interprocedural escape and unsupported effects conservative. It does not
  authorize register-initialization elision, alias relaxation, bounds removal,
  or any other transformation.
- Region-specific interprocedural effect summaries and a complete source
  lifetime model remain absent. A local `NO_ESCAPE` result is scoped to the
  analyzed workload/model, not a language-wide theorem.

## Machine-code intelligence

`CODEGEN_PROVENANCE=PARTIAL`; `MACHINE_CODE_ATTRIBUTION=PARTIAL`;
`CODEGEN_REPORT=EXPERIMENTAL`; `OPTIMIZATION_EXPLAIN=PARTIAL`;
`PASS_EFFECT_METRICS=PARTIAL`.

The optional sidecar links S3 Assembly operation indices to generated x86-64
assembly-text line spans. It does not map binary addresses or ELF `.text` bytes.
Generated runtime/prologue and other unmatched lines remain `UNMAPPED`.

| Workload | Assembly ops | Parsed emitted instruction lines | Attributed | Unmapped | Coverage | Generated assembly text bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Energy aggregation | 318 | 7,239 | 2,506 | 4,733 | 34.6180% | 368,721 |
| Point-cloud summary | 519 | 11,151 | 4,216 | 6,935 | 37.8083% | 595,343 |
| Raster-window statistics | 675 | 13,034 | 5,125 | 7,909 | 39.3202% | 718,517 |

These counts describe emitted assembly text, not machine binary instruction
counts. `machine_text_bytes` is unavailable because assembled object files were
not measured. Text byte counts are file/text size, not executable `.text` size.

The codegen report exposes function/block structure, static allocator metrics,
instruction categories, an optional origin sidecar, and explicit unknown
coverage. Compact-EA decisions carry concrete fallback reasons, but this is not
a uniform explain record for every optimization pass. Cross-pass before/after
effect accounting remains incomplete.

## Machine IR and machine optimization

- `MACHINE_IR=DEFERRED_WITH_EVIDENCE`; `MACHINE_IR_VERIFIER=NOT_STARTED`;
  `MACHINE_OPTIMIZER=NOT_STARTED`.
- Existing S3 Assembly already represents virtual registers and basic blocks;
  the new sidecar establishes an observable Assembly-to-emitted-text link.
- No measured candidate optimization was blocked by the current representation,
  and no dual-path experiment showed a concrete gain from a second IR. Therefore
  no Machine IR was implemented and none replaces the production path.
- Compact-EA was considered on the three workloads and applied zero sites.
  Reasons include missing indexed-memory opportunities, unproven index
  initialization and reference operations. No-op-move candidates were zero.
- `ADDRESS_LOWERING=PARTIAL`; `TEMPORARY_ELISION=EXPERIMENTAL`;
  `DEAD_MACHINE_OP_ELIMINATION=NOT_STARTED`; `COLD_PATH_LAYOUT=NOT_STARTED`.
  No production machine optimization or speedup is claimed.

## Register allocation

`REGISTER_PRESSURE_ANALYSIS=PARTIAL`; `REGISTER_ALLOCATOR_EXPERIMENT=EXPERIMENTAL`;
`COPY_COALESCING=NOT_STARTED`; `REMATERIALIZATION=NOT_STARTED`.

| Workload/function | Virtual registers | Peak static live | Stack-resident virtual values | Frame bytes | Dynamic spills |
| --- | ---: | ---: | ---: | ---: | --- |
| Point cloud / `point_cloud_summary` | 368 | 7 | 0 | 3,648 | Not measured |
| Raster / `raster_window_statistics` | 432 | 11 | 6 | 4,192 | Not measured |
| Energy / `energy_series_aggregation` | 211 | 10 | 0 | 2,144 | Not measured |

Stack-resident virtual values are not dynamic spills. An allocator-only
counterfactual allowing `r15` changes raster's static stack-resident count from
6 to 0, with no reduction in the other measured functions. This counterfactual
was not emitted or executed and conflicts with `r15`'s current per-instruction
budget role; it establishes neither runtime impact nor a reason to remove the
reservation. Same-register move counts and no-op move candidates were zero in
the measured records.

## Vectorization and portability

- `VECTOR_LEGALITY=PARTIAL`; `VECTORIZABLE_LOOP_COUNT=0` of five observed;
  `SIMD=LEGALITY_ONLY`.
- Five natural loops remain `UNKNOWN`; none was proven vectorizable or proven
  not-vectorizable. Canonical induction, vector bounds and general
  inter-iteration dependence are missing. Strict floating-point semantics were
  preserved; no SIMD was emitted.
- `TARGET_MODEL=PARTIAL`. Target-independent reference/loop facts are distinct
  from x86-64 emitter attribution, but no general cross-target target model was
  qualified.
- `ARM64_PROBE=PROTOTYPE`; `WASM_PROBE=PROTOTYPE`. Existing structural probes
  passed, but no equivalent S3 program was executed on a second native/portable
  backend. Neither is a qualified backend.

## Verification, generated programs and execution resources

- `DIFFERENTIAL_TESTING=PARTIAL`: the existing deterministic seeded O0/O1
  hosted differential cases passed; this is not a broad native fuzz oracle.
- `METAMORPHIC_TESTING=NOT_STARTED`; `FUZZING=NOT_STARTED`;
  `OPTIMIZATION_CONTRACTS=PARTIAL`.
- `AGENT_CODE_ANALYSIS=PARTIAL`; `AGENT_COMPILER_FEEDBACK=NOT_STARTED`. The
  checked-in agent-named examples are human-authored; no model-generated paired
  source/normalized sample or stylistic scoring was used.
- `EXECUTION_CONTEXT=DESIGN`; `MEMORY_BUDGET_RESEARCH=PARTIAL`;
  `EXECUTION_CERTIFICATE=NOT_STARTED`. Emulator instruction accounting is
  per-execute; frame limits are enforced per frame. No shared cross-call
  execution context, host-thread concurrency contract implementation, or
  execution certificate was prototyped in this campaign.
- `COMPILE_TIME_METRICS=NOT_MEASURED`; `BINARY_METRICS=NOT_MEASURED`.
  VM PMU counters were unavailable (`perf_event_paranoid=4`); no dynamic
  performance or spill data is inferred from static counters.

## Validation and cross-repository evidence

- S3 compileall: PASS.
- S3 focused semantic/codegen/vector and source-identity regressions: PASS.
- Linux native/backend and target structural focused gates: PASS.
- Full Linux suite at exact source HEAD `b8f446a5ea2b24b948a263cb955f426c5d0f48ce`:
  `4,490 passed, 1 skipped, 0 failed`, exit 0. The one skip is the optional
  `cryptography` package-signature test because the dependency is absent in the
  guest. Raw transcript and terminal status are preserved at
  `reports/s3-1.8-machine-intelligence-portable-compute/evidence/linux-full-suite-b8/`.
  Transcript SHA-256: `e271ee259d539c96adc9856abbe61e409acc25a2015fd1a88665f17a5aa37604`;
  status SHA-256: `652fdac1d806cc42fb56bd031f1ba31df775d4c8870e561bd2fd3aa38bd61fcb`.
- Nine baseline artifacts (three report families for each continuity workload)
  are pinned to S3 candidate HEAD `b8f446a5ea2b24b948a263cb955f426c5d0f48ce`.
  The independent lab validates artifact kind, path, SHA-256 and candidate
  provenance. Source identity hashes normalize CRLF to LF so Windows checkout
  conventions do not change canonical source identity.
- Historical budget records from Bench PRs #23 and #24 remain valid historical
  observations but are `NOT_COMPARABLE` with 1.8 absent a matched artifact and
  protocol. Current PER-vs-EXACT and PER-vs-HYBRID conclusions are inconclusive;
  the default remains PER.
- `S3_BENCHMARK_IMPACT=MINOR`: reporting hooks and independent evidence plumbing
  were added, but no benchmark default, compiler optimization policy or runtime
  semantics were changed.

## Rejected and negative results

- Compact-EA had zero applied sites across the three continuity workloads; the
  effective policy remained baseline.
- The measured Assembly programs had zero no-op-move candidates.
- None of the five natural loops was proven vectorizable; all remain unknown,
  not classified as inherently illegal.
- Assembly-origin spans cover only 34.6%-39.3% of parsed emitted instruction
  lines. Full machine-code attribution is not established.
- The `r15` allocation probe is static, non-executable evidence only.
- No matched current PER/EXACT/HYBRID experiment exists; historical results were
  not retroactively reinterpreted.
- No agent-generated corpus, broad fuzz result, runtime profile, binary `.text`
  measurement or second-backend execution was produced.

## Capability status

```text
REFERENCE_ANALYSIS=EXPERIMENTAL
ALIAS_ANALYSIS=PARTIAL
EFFECT_ANALYSIS=PARTIAL
ESCAPE_ANALYSIS=EXPERIMENTAL
MEMORY_MODEL=PARTIAL
CODEGEN_PROVENANCE=PARTIAL
MACHINE_CODE_ATTRIBUTION=PARTIAL
CODEGEN_REPORT=EXPERIMENTAL
OPTIMIZATION_EXPLAIN=PARTIAL
PASS_EFFECT_METRICS=PARTIAL
ATTRIBUTED_MACHINE_CODE=34.6%-39.3% OF EMITTED ASSEMBLY INSTRUCTION LINES
UNKNOWN_MACHINE_CODE=60.7%-65.4% OF EMITTED ASSEMBLY INSTRUCTION LINES
MACHINE_IR=DEFERRED_WITH_EVIDENCE
MACHINE_IR_VERIFIER=NOT_STARTED
MACHINE_OPTIMIZER=NOT_STARTED
REGISTER_PRESSURE_ANALYSIS=PARTIAL
REGISTER_ALLOCATOR_EXPERIMENT=EXPERIMENTAL
COPY_COALESCING=NOT_STARTED
REMATERIALIZATION=NOT_STARTED
ADDRESS_LOWERING=PARTIAL
TEMPORARY_ELISION=EXPERIMENTAL
DEAD_MACHINE_OP_ELIMINATION=NOT_STARTED
COLD_PATH_LAYOUT=NOT_STARTED
VECTOR_LEGALITY=PARTIAL
VECTORIZABLE_LOOP_COUNT=0_OF_5
SIMD=LEGALITY_ONLY
TARGET_MODEL=PARTIAL
ARM64_PROBE=PROTOTYPE
WASM_PROBE=PROTOTYPE
DIFFERENTIAL_TESTING=PARTIAL
METAMORPHIC_TESTING=NOT_STARTED
FUZZING=NOT_STARTED
OPTIMIZATION_CONTRACTS=PARTIAL
AGENT_CODE_ANALYSIS=PARTIAL
AGENT_COMPILER_FEEDBACK=NOT_STARTED
EXECUTION_CONTEXT=DESIGN
MEMORY_BUDGET_RESEARCH=PARTIAL
EXECUTION_CERTIFICATE=NOT_STARTED
COMPILE_TIME_METRICS=NOT_MEASURED
BINARY_METRICS=NOT_MEASURED
PER_INSTRUCTION_DEFAULT=YES
PER_SEMANTICS_PRESERVED=YES
STRICT_FP_PRESERVED=YES
FULL_SUITE=4490_PASSED_1_SKIPPED_0_FAILED_EXIT_0
NATIVE_LINUX=PASS
```

## Next frontier

```text
MACHINE_IR_NEXT=NO
REGISTER_ALLOCATOR_NEXT=NO
VECTOR_EXECUTION_NEXT=NO
PORTABLE_BACKEND_NEXT=NO
EXECUTION_CONTEXT_NEXT=NO
PARALLEL_COMPUTE_NEXT=NO
ACCELERATOR_RESEARCH_NEXT=NO
```

These are not permanent prohibitions. The evidence does not yet justify jumping
to those implementations. The primary next campaign should close
object-level/native instruction provenance and establish a matched, bounded
native measurement protocol: most emitted instruction lines are still unknown,
binary `.text` size was not recorded and no runtime bottleneck was measured.
Only then should the next machine/allocator/vector target be selected. PMU
unavailability remains an environmental limitation, not a reason to invent
counter data.

The planned expansion line remains:

```text
language -> verified execution -> scientific workloads -> bounded native
execution -> codegen intelligence -> reference/memory intelligence -> machine
representation -> verified optimization -> register/vector intelligence ->
portable compute -> deterministic parallelism -> accelerators
```

## Publication boundary

```text
S3_PR=322
S3_PR_BASE=main
S3_PR_STATE=DRAFT
```

This report is for [S3 PR #322](https://github.com/SamDevlab/S3/pull/322).
No merge, release, tag, PyPI publish,
default-policy promotion or S3 1.9 campaign is authorized by this work.
Human review decides integration and the next frontier.
