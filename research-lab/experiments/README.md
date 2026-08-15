# Experiment Registry

Every serious hypothesis should receive a durable experiment record before production promotion.

Permanent IDs:

```text
S3-EXP-0001
S3-EXP-0002
...
```

## Queue and status

### S3-EXP-0001 — Binary min-cut vs exact oracle

STATUS=PLANNED

File: `S3-EXP-0001-mincut-vs-oracle.md`

Related: `S3-ZK-0005`, `0007`.

Cross-check binary materialization min-cut against exhaustive deterministic tiny problems.

### S3-EXP-0002 — RA OFF vs RA ON causal control

STATUS=SUPPORTED_BY_P4 / TOP_LEVEL_QUESTION_RESOLVED

File: `S3-EXP-0002-ra-off-vs-on.md`

Related: `S3-ZK-0006`, `0009`, `0013`, `0028`, `0031`.

P4 provided production-scale causal evidence. The existing liveness-aware whole-function allocator was not established as a poor algorithmic primary cause; the native backend defaulted `register_allocation=false`, causing location flexibility to collapse into emitter frame canonicalization. Making the existing allocator the native default reduced direct frame loads `1549 -> 491` and stores `1520 -> 471`.

Do not repeat this as an unresolved top-level experiment unless a future allocator change invalidates the causal control.

### S3-EXP-0003 — Lagrangian shared-capacity decomposition

STATUS=PLANNED

File: `S3-EXP-0003-lagrangian-capacity.md`

Related: `S3-ZK-0005`, `0007`, `0015`.

Compare priced independent min-cut subproblems with exact tiny multi-value capacity optimization.

### S3-EXP-0004 — Residence-domain laws

STATUS=PLANNED

Related: `S3-ZK-0003`, `0004`, `0011`.

Exhaustively verify order/join/meet laws and transfer monotonicity.

### S3-EXP-0005 — S3 location-flexibility loss histogram

STATUS=PARTIALLY_RESOLVED_BY_P4 / CONTINUE_FOR_METADATA_BOUNDARIES

Related: `S3-ZK-0001`, `0006`, `0009`, `0013`, `0028`.

P4 identified a major early loss boundary: `X8664Backend.register_allocation default false`. Continue this experiment only where needed to trace the residual metadata/SSA state that P4 did not remove.

### S3-EXP-0006 — Matroid exchange counterexample search

STATUS=PLANNED

Related: `S3-ZK-0008`.

Search restricted residence systems for hereditary/exchange violations.

### S3-EXP-0007 — Submodularity counterexample search

STATUS=PLANNED

Related: `S3-ZK-0012`.

Enumerate subsets and test submodular inequalities/diminishing returns.

### S3-EXP-0008 — Forward availability + backward memory necessity

STATUS=PLANNED_RESEARCH

Related: `S3-ZK-0002`, `0003`, `0014`.

Derive materialization frontiers and compare them with the exact placement oracle. P4 did not establish this model as necessary for production; keep it research-only until residual evidence supports it.

### S3-EXP-0009 — Current S3 ternary semantics/lowering map

STATUS=PLANNED

File: `S3-EXP-0009-ternary-semantics-map.md`

Related: `S3-ZK-0016`, `0017`, `0023`.

Establish exact S3 trit truth tables/operations and find the first physical-encoding layer.

### S3-EXP-0010 — Ternary operation-basis synthesis oracle

STATUS=PLANNED

File: `S3-EXP-0010-ternary-basis-oracle.md`

Related: `S3-ZK-0007`, `0018`, `0023`.

Exhaustively search small primitive bases over exact S3 trit semantics and compare target-lowering costs.

### S3-EXP-0011 — Semantic state minimization

STATUS=PLANNED

File: `S3-EXP-0011-ternary-state-minimization.md`

Related: `S3-ZK-0019`, `0020`, `0023`.

Test whether finite/ternary control states can be minimized before x86 branch lowering while preserving effects/failure behavior.

### S3-EXP-0012 — Ternary representation conversion graph

STATUS=PLANNED

File: `S3-EXP-0012-ternary-representation-graph.md`

Related: `S3-ZK-0017`, `0024`, `0007`.

Compare deterministic greedy representation choice with exact shortest-path/DP solutions on bounded trit computations.

### S3-EXP-0013 — Compiler information-loss boundary audit

STATUS=SUPPORTED_FOR_INITIAL_CORPUS / CROSS_WORKLOAD_OPEN

File: `S3-EXP-0013-information-loss-boundaries.md`

Related: `S3-ZK-0009`, `0021`, `0022`, `0027`, `0028`, `0030`.

Across a real value/state corpus classify logical identity, type/trit semantics, equivalence, location flexibility, representation flexibility, range, provenance, memory validity, initialization state, liveness and rematerializability as `PRESERVED`, `DERIVABLE`, `LOST`, `INTENTIONALLY_DISCARDED` or `UNKNOWN` at compiler boundaries.

P4 means the audit must include **configuration/pass enablement** as a boundary category, not only IR transformations. P5-AUDIT found that the exact P4 JSMN candidate preserves the physical identity of all 5638 byte-frame lines, but semantic necessity and dynamic weighting remain open.

### S3-EXP-0014 — Memory-state metadata provenance

STATUS=SUPPORTED_FOR_P4_JSMN_STATIC_ORIGIN / DYNAMIC_CLASSIFICATION_PARTIAL

File: `S3-EXP-0014-memory-state-metadata-provenance.md`

Related: `S3-ZK-0004`, `0021`, `0022`, `0027`, `0030`.

P4 measured metadata accesses unchanged at `5638 -> 5638`. P5-AUDIT reproduced the count and decomposed it into `4589` register-initialization accesses, `837` memory-initialization accesses and `212` trit payload accesses included by the lexical metric. P5-PREWORK added dynamic observer-aware counters. Physical origin is complete, but only 324 static and 356 JSMN dynamic checks have directly proven semantic outcomes; the remainder is UNKNOWN/UNMEASURED.

### S3-EXP-0015 — SSA destruction vs memory-state metadata staging

STATUS=SUPPORTED_NEGATIVE_FOR_P4_JSMN_CORPUS / PHI_HEAVY_REFINED

File: `S3-EXP-0015-ssa-destruction-metadata-staging.md`

Related: `S3-ZK-0006`, `0009`, `0027`, `0030`, `0031`.

Quantitatively separate ordinary value traffic, phi/loop staging, SSA-destruction metadata, initialization/memory-validity metadata, true RA spills and call/ABI traffic before selecting P5. P5-AUDIT found `0` emitted phi accesses and `0` critical edges in the P4 JSMN corpus. P5-PREWORK measured 712 internal O1 JSMN phis and 33 in a phi-heavy corpus; SSA is relevant when state reaches materialization, but the residual cannot be attributed to SSA alone.

### S3-EXP-0016 — Dynamic observer-aware initialization necessity

STATUS=SUPPORTED_FOR_OBSERVABILITY / NECESSITY_OPEN

File: `S3-EXP-0016-dynamic-observer-aware-initialization.md`

Related: S3-ZK-0035, 0036, 0037, 0038.

Temporary native instrumentation measured register/memory initialization and
trit payload reads/writes, observer class and dynamic site hotness across JSMN,
call-heavy, reference/address, slice, numeric and phi-heavy workloads. The
instrumentation is reverted. Exact JSMN dynamic weighting is reproducible, but
the remaining reset/store and observer populations are UNKNOWN/UNMEASURED.
Hosted emulator TADDR support is required before full reference/slice
differential closure.

## Current promotion order

```text
S3-EXP-0014 memory-state metadata provenance
        +
S3-EXP-0015 SSA destruction vs metadata staging
        +
S3-EXP-0016 dynamic observer-aware initialization necessity
        +
S3-EXP-0013 compiler-boundary information-loss audit
        ↓
P5 target selection
```

Parallel research remains:

```text
S3-EXP-0009..0012 ternary virtualization
S3-EXP-0001/0003/0004/0006/0007/0008 mathematical placement models
```

Do not let a speculative model displace the measured post-P4 bottleneck without causal evidence.

### S3-EXP-0034 - Explicit range-fact contract

STATUS=SUPPORTED_NEGATIVE

File: `S3-EXP-0034-p9-2-explicit-range-fact-contract.md`

P9.2 compared recomputation at the native consumer, a private verified fact
keyed by structural `InstructionSite`, and a public Assembly contract on the
stacked A+B correctness candidate. The old P9 model reproduced at `289500`;
the candidate measured `289512` as a correctness-only delta. Across 15
workloads, classification coverage was `1.0`, but
`AVOIDABLE_DYNAMIC=0` and `PROVABLY_REDUNDANT_SITES=0`. Model A was sufficient
to close the negative; Model B was not needed and Model C was not justified.
All invalidators retain checks. P9.2 is `NO_VALID_TARGET_YET` and did not
start production.

## Experiment template

```text
ID=
STATUS=PLANNED/RUNNING/SUPPORTED/REJECTED/INCONCLUSIVE
RELATED_ZETTEL=
MODEL=
INPUTS=
CONTROL=
MEASUREMENT=
FALSIFIER=
RESULT=
COUNTEREXAMPLE=
NEXT=
```

## Rule

When an experiment produces a counterexample, create a `NEGATIVE_RESULT` Zettel before changing the model so the failed hypothesis remains durable knowledge.

### S3-EXP-0017 - Reset identity, lifetime and observer closure

STATUS=SUPPORTED_FOR_JSMN_TRACE / GENERAL_PROOF_OPEN

The closure trace reproduces 14367 allocated-memory reset bytes. Direct
overwrite and lifetime candidates are measured, but aliases, calls, failure
paths and frame-layout identity remain conservative unknowns.

### S3-EXP-0018 - Hosted TADDR differential closure

STATUS=SUPPORTED_FOR_O0_FOCUSED_CORPUS / O1_LIMITATION

A disposable hosted reference representation matched native results on six O0
corpora. It was not promoted to production. O1 slice compilation currently
fails in the existing optimizer verifier before execution.

### S3-EXP-0019 - Exact reset necessity oracle

STATUS=PLANNED

The existing bounded placement oracle is not sound for S3 reset identity. A
future oracle must model typed validity, aliases, calls, failure exits and
frame lifetimes.

### S3-EXP-0020 - Failure, phi and loop reset proof

STATUS=OPEN

Focused contracts pass and phi-heavy evidence exists, but no path-complete
reset necessity proof is established.

### S3-EXP-0021 - GitHub Actions efficiency and test-area audit

STATUS=SUPPORTED_FOR_TRIGGER_DUPLICATION / CI_PR_173_PENDING

The 2026-08-12 audit measured 22356.616667 API-derived job minutes, 12274.700000
non-main push minutes, 3716.766667 research-branch minutes, 197 same-SHA
push/PR pairs, and 4740 duplicate pytest executions. The safe promotion is
trigger precision + PR-only cancellation + official pip caching, while native,
differential, SSA, Python compatibility, benchmark smoke and Docker gates stay.

### S3-EXP-0022 - O1 slice metadata transport

STATUS=SUPPORTED_AND_MERGED_PR_172

Valid O0 slice programs failed after SSA optimization because SSA-to-IR lowering
dropped reference target, mutability, slice and parameter length metadata. The
small correction preserved the contract and passed natural CI. This is a
correctness fix, not a P5 performance target.

### S3-EXP-0023 - Post-P4 whole-backend reprofile

STATUS=SUPPORTED_FOR_CURRENT_CHARACTERIZATION / P5_REJECTED

Eight workloads passed hosted IR and Linux native execution. JSMN remains the
dominant shape by native text/instruction count and compile time. The broad
memory-state metadata hypothesis remains unproven as removable; no production
P5 was selected.

### S3-EXP-0024 - P5 v2 immediate instruction-limit guard

STATUS=SUPPORTED_AND_MERGED_PR_174

The fresh 15-workload reprofile isolated repeated x86-64 emitter expansion of
the bounded instruction-limit guard. A signed imm32 compare removes the
per-instruction `movabs r11` while retaining the wider-limit fallback. The
prototype reduced aggregate O1 native instructions by 4.748% and text by
1.694%, with all Linux native workload results preserved. This is a bounded
emitter capability; it does not establish a spill, SSA, bounds, or
initialization-state optimization.

### S3-EXP-0025 - P6 direct non-F64 TCONST immediate

STATUS=SUPPORTED_AND_MERGED_PR_175

Post-P5 profiling found 7351 static O1 one-use constant materializations, with
7347 signed-imm32 eligible and 200250 dynamic eligible events. The minimum
sound emitter-local rewrite passes the immediate directly to the existing
destination writer, preserving initialized-state marking. It reduced O1 native
instructions by 7347 and `.text` by 146940 bytes against the post-P5 baseline.
All 15 Linux native workloads, the exact-head full suite, and natural CI passed.
This experiment does not justify generic operand-form optimization, RA
redesign, bounds elimination, or guard weakening.

### S3-EXP-0026 - P7 direct comparison-to-branch lowering

STATUS=SUPPORTED_AND_MERGED_PR_176

Fresh O1 triage found 566 adjacent `TCMP`/`TBR3` pairs whose comparison result
was not observed later in the same function corpus; 66 executed in the hosted
emulator. The result was classified conditional, not globally accidental. PR
#176 added same-block liveness-gated direct integer and ordered-f64 branches,
while retaining materialization for successor observers and preserving both
instruction-limit checks. Natural Linux CI passed. This is a local emitter
lowering result and does not prove broad memory-state or SSA staging removal.

### S3-EXP-0027 - P8.1 obligation frontier and first useful work

STATUS=COMPLETE_NO_VALID_TARGET_YET

File: `post_p7_obligation_profile.py` and `first_useful_work_profile.py`

Related: `S3-ZK-0050`, `S3-ZK-0051`, `S3-ZK-0052`.

The exact P7 production head was profiled locally with 12 representative
emulator/native workloads and nine tiny first-useful-work workloads. The
profile confirms a large repeated native materialization family, but failure,
memory-validity, instruction-limit, ABI and observer witnesses prevent a
blanket removal rule. The external first-output timer is a baseline only;
process/loader cost and S3-controlled cost are not yet separated.

Promotion result: `NO_VALID_TARGET_YET`. No production implementation was
started. The next useful experiment is path-complete observer-aware attribution
of initialization and memory-state commitments.

### S3-EXP-0028 - Exact-ref workflow-trigger containment

STATUS=COMPLETE_LOCAL_ONLY

File: `../tools/validate_remote_write.py` and `../tools/test_validate_remote_write.py`

Hypothesis: a bounded fail-closed local validator can distinguish the
branch-specific incident state from a repaired zero-run state using the
proposed workflow head, target ref, event, and changed paths without remote
execution.

Results:

- the historical research push `e4ea4ca -> 06ed794` classified as
  `ACTIONS_POSSIBLE` with one matching workflow;
- the local repaired candidate classified as `PROVEN_ZERO_ACTIONS` with zero
  possible push runs;
- controls A-F passed, including malformed and unsupported inputs returning
  `UNKNOWN` and non-zero;
- the repaired state was published at `d852a611` after repository-level
  Actions were disabled; no new run followed publication.

This is a research-infrastructure containment result, not a compiler
optimization or a production CI authorization.

### S3-EXP-0029 - P8.2 preserved possibilities and collapse points

`S3-EXP-0029` records the P8.2 negative result. A seven-entry possibility
collapse ledger was compared with direct producer/consumer rules. The ledger
is useful for organizing research witnesses, but no new collapse had a
path-complete safety proof and the only proven conditional control collapse is
already P7. No P8 production target was promoted.

File: `../reconciliations/POSSIBILITY_COLLAPSE_LEDGER_P8_2.json`

### S3-EXP-0030 - P8.3 path-complete memory-state necessity

STATUS=COMPLETE_NO_VALID_TARGET_YET

The exact P7 main head was analyzed with a simple CFG/use-def worklist fixed
point and a semantics-preserving emulator boundary tracker. The largest bounded
accidental subclass was definite `REGISTER_INIT_CHECK` in functions without
call/reference/slice visibility: 1660 dynamic events across 11 workloads. It
has no measured native effect, the public runtime proof transport is absent,
and TADDR remains unsupported by the existing emulator. No production target
was promoted.

Files: `p8_3_memory_state_necessity.py`,
`p8_3_memory_state_necessity.json`, and
`test_p8_3_memory_state_necessity.py`.

### S3-EXP-0031 - P8 final proof-guided native initialization-check elision

STATUS=SUPPORTED_AND_MERGED_PR_178

P8.4 was promoted after the exact candidate reproduced the P8.3 bounded safe
population and established a native effect. The selected implementation is
fail-closed native recomputation from existing CFG/use-def facts; it does not
transport a general proof through public Assembly. Across 24 Linux O0/O1 pairs,
semantics matched baseline and aggregate initialization checks changed from
550 to 148. PR #178 merged the three-file production diff as
`5dd6844607ba3a2d5830ed836fb9026eed86d0fb`.

The full suite ran once on exact candidate
`87eb49cd19a78570f07d66ce7982650c8b422210` and exited 0. Actions remained
disabled and no candidate-branch run existed. Runtime and compile-time results
were not measured under a comparable protocol.

### S3-EXP-0032 - P9 causal frame and representation attribution

STATUS=COMPLETE_NO_VALID_TARGET_YET

The validated Assembly-to-x86 sidecar model covered nine internal workloads
and six frozen JSMN fixtures using `MODELLED_NATIVE_DYNAMIC_COUNT`. External
correctness and sidecar identity passed. The O1 model total was 143151;
instruction-limit, bounds, frame, semantic-payload and memory-validity sites
dominated. Direct indexed addressing falsified the current fixed-array
base-reload hypothesis. Observed stack-resident frame-value events were 5431,
or 3.793895956018% of O1, and true spill causality was not established.

P9 closes with `NO_VALID_TARGET_YET`. No production compiler change, branch,
PR, benchmark rerun or Actions execution occurred. See
`S3-EXP-0032-p9-causal-frame-representation-attribution.md` and
`reconciliations/P9_TARGET_SELECTION_CAUSAL_FRAME_20260814.md`.

### S3-EXP-0033 - P9.1 bounds and validity contract attribution

STATUS=COMPLETE_NO_VALID_TARGET_YET

P9.1 reproduced the `MODELLED_NATIVE_DYNAMIC_COUNT` total of 289500 across 15
workloads. Explicit safety realization was 65224 modelled dynamic x86 lines;
bounds were 17464 and memory initialization was 6660. The bounded local
constant, success-edge, loop and same-object check-reuse models found zero
proven eligible sites. Focused native correctness passed for five candidate
workloads. No production compiler change, benchmark rerun or Actions run
occurred. See `S3-EXP-0033-p9-1-bounds-validity-contract-attribution.md` and
`reconciliations/P9_1_BOUNDS_VALIDITY_CONTRACT_ATTRIBUTION_20260814.md`.

### S3-EXP-0034 - P9.2 explicit range-fact contract

STATUS=COMPLETE_NO_VALID_TARGET_YET

P9.2 compared bounded recomputation, a private verified fact and a public
Assembly contract on the A+B correctness candidate. The old model reproduced
at 289500; A+B measured 289512 as a correctness-only delta. Classification
coverage remained 1.0, but no provably redundant site or dynamic event
survived the invalidator controls. See
`S3-EXP-0034-p9-2-explicit-range-fact-contract.md` and
`../reconciliations/P9_2_EXPLICIT_RANGE_FACT_CONTRACT_20260814.md`.

### S3-EXP-0035 - P9.3 UNKNOWN causal attribution

STATUS=SUPPORTED_NEGATIVE

P9.3 reproduced the A+B P9 sidecar at 289512 and reconciled the complete
26456-event UNKNOWN population. All events are exactly the existing P8
`REGISTER_INITIALIZATION_CHECK` class: 30096 static lines, 8892 structural
sites and six workloads. No P9-relevant UNKNOWN dynamic population remains,
so the maximum theoretical P9 avoidable dynamic is zero and the bounds/
validity line closes without a P9.4. See
`S3-EXP-0035-p9-3-unknown-causal-attribution.md` and
`../reconciliations/P9_3_RESULT.json`.

### S3-EXP-0036 - P10 global dynamic opportunity census

STATUS=COMPLETE_NO_VALID_TARGET_YET

P10 consumed the exact A+B P9 sidecar on 15 workloads and 30 O0/O1 runs. It
reproduced 289512 and established a complete one-primary-class partition.
Instruction-limit accounting was 99036 dynamic lines, bounds 56500, frame
canonicalization 39081, semantic payload 38050 and memory validity 29408.
The top non-semantic necessity ledgers found no proven removable population;
frame stack residency did not establish spill causality. No concrete avoidable
example was found, so `P10_SELECTION=NO_VALID_TARGET_YET` and no production
target was selected. See `S3-EXP-0036-p10-global-dynamic-opportunity-census.md`
and `../reconciliations/P10_GLOBAL_DYNAMIC_OPPORTUNITY_CENSUS_20260814.md`.

### S3-EXP-0037 - P10.1 frame representation causal decomposition

STATUS=COMPLETE_NO_VALID_TARGET_YET

P10.1 consumed the exact P10 sidecar on the frozen A+B correctness candidate
and reproduced `289512` across 15 workloads. The broad
`FRAME_CANONICALIZATION=39081` class reconciles exactly into logical
frame-value traffic `14795` and other frame representation `24286`. The
`10063` stack-resident frame-value events are an overlay and are not relabeled
as spill. Correction B's TMOV materialization is recorded separately at `240`
dynamic events and was not reopened.

The sidecar does not provide the causal facts needed for exact load/store
direction, liveness, pressure, frame slots, call-clobber survivors or a valid
counterfactual. True spill/reload and an avoidable non-spill example were not
proven; all unresolved frame events are `ATTRIBUTION_LIMIT_ONLY`. P10.1 closes
the frame line as `NO_VALID_TARGET_YET` with `FRAME_LINE_STATUS=CLOSE`. No
production code, benchmark, Actions run or shutdown occurred. See
`S3-EXP-0037-p10-1-frame-representation-causal-decomposition.md`,
`../reconciliations/P10_1_FRAME_REPRESENTATION_CAUSAL_DECOMPOSITION_20260814.md`,
and `../reconciliations/P10_1_RESULT.json`.
