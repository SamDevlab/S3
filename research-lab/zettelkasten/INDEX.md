# S3 Zettelkasten Index

## Notes

| ID | Type | Status | Atomic idea |
|---|---|---|---|
| [[S3-ZK-0001]] | PERMANENT | SUPPORTED | Preserve location flexibility before physical allocation. |
| [[S3-ZK-0002]] | BRIDGE | SUPPORTED | Materialization is a decision, not a default logical-value state. |
| [[S3-ZK-0003]] | HYPOTHESIS | OPEN | Value representation may admit a useful residence lattice. |
| [[S3-ZK-0004]] | HYPOTHESIS | OPEN | Separate representation facts may compose better as a reduced product domain. |
| [[S3-ZK-0005]] | HYPOTHESIS | OPEN | Restricted materialization placement may reduce to min-cut/min-cost flow. |
| [[S3-ZK-0006]] | PERMANENT | SUPPORTED | RA cannot fix value identity already destroyed upstream. |
| [[S3-ZK-0007]] | HYPOTHESIS | OPEN | Tiny-CFG exact optimization can provide an optimality oracle. |
| [[S3-ZK-0008]] | QUESTION | OPEN | Restricted feasible resident sets may exhibit matroid-like exchange structure. |
| [[S3-ZK-0009]] | ARCHITECTURE | OPEN | Compiler quality can be studied as preservation/loss of future representation choices. |
| [[S3-ZK-0010]] | BRIDGE | OPEN | Approximation should be introduced only where it buys convergence/cost. |
| [[S3-ZK-0011]] | PERMANENT | SUPPORTED | Fixed-point convergence strategy is an engineering precision/cost parameter. |
| [[S3-ZK-0012]] | QUESTION | OPEN | Residence benefit may be submodular in useful restricted domains. |
| [[S3-ZK-0013]] | PERMANENT | SUPPORTED | Current RA already consumes whole-function CFG liveness/cross-block vregs; RA OFF vs ON is a critical control. |
| [[S3-ZK-0014]] | HYPOTHESIS | OPEN | Lazy materialization may require dual forward-availability and backward-necessity analyses. |
| [[S3-ZK-0015]] | HYPOTHESIS | OPEN | Shared register-capacity coupling may be relaxed into priced per-value min-cut subproblems. |
| [[S3-ZK-0016]] | ARCHITECTURE | OPEN | Ternary semantics should precede physical encoding. |
| [[S3-ZK-0017]] | BRIDGE | OPEN | Representation flexibility generalizes location flexibility. |
| [[S3-ZK-0018]] | HYPOTHESIS | OPEN | Search for a cost-optimal ternary operation basis. |
| [[S3-ZK-0019]] | HYPOTHESIS | OPEN | Minimize semantic finite/ternary control states before binary branch lowering. |
| [[S3-ZK-0020]] | BRIDGE | OPEN | Partition information can lower-bound future-state dependencies. |
| [[S3-ZK-0021]] | HYPOTHESIS | OPEN | Measure compiler information loss, not only emitted instructions. |
| [[S3-ZK-0022]] | ARCHITECTURE | OPEN | Preserve useful optimization facts as explicit bounded proof/fact objects. |
| [[S3-ZK-0023]] | HYPOTHESIS | OPEN | A ternary virtual ISA may preserve semantic operations before x86 lowering. |
| [[S3-ZK-0024]] | HYPOTHESIS | OPEN | Ternary representation selection may be a conversion-graph optimization problem. |
| [[S3-ZK-0025]] | HYPOTHESIS | OPEN | A bounded compiler proof language may preserve useful facts cheaply. |
| [[S3-ZK-0026]] | PERMANENT | SUPPORTED | Demonstration success is not technology maturity. |
| [[S3-ZK-0027]] | BRIDGE | OPEN | Lowering should retain information that downstream optimization still needs. |
| [[S3-ZK-0028]] | PERMANENT | SUPPORTED | A configuration/default can itself be the earliest information-loss boundary. |
| [[S3-ZK-0029]] | PERMANENT | SUPPORTED | Keep causal structural, absolute runtime and external-relative performance metrics distinct. |
| [[S3-ZK-0030]] | HYPOTHESIS | SUPPORTED_BY_P4_RESIDUAL | Memory-state metadata is a distinct optimization state space from ordinary value residency. |
| [[S3-ZK-0031]] | PERMANENT | SUPPORTED | Allocator enablement and allocator algorithm quality are different causal variables. |
| [[S3-ZK-0032]] | PERMANENT | SUPPORTED | The byte-frame metadata metric is physically broader than metadata and includes trit payload bytes. |
| [[S3-ZK-0033]] | NEGATIVE_RESULT | SUPPORTED_FOR_CORPUS | SSA/phi staging is not dominant in the P4 JSMN residual because the corpus has no phis or edge copies. |
| [[S3-ZK-0034]] | BRIDGE | SUPPORTED_AS_RESEARCH_MODEL | Initialization state and physical residence interact as separate dimensions under the emitter's snapshot rules. |

## Cluster A — Global value residency after P4

```text
                       S3-ZK-0007 Exact Oracle
                              |
                              v
S3-ZK-0005 Min-Cut ---> S3-ZK-0002 Materialization <--- S3-ZK-0001 Location Flexibility
       |                      |                                   |
       |                      v                                   v
       |              S3-ZK-0014 Forward/Backward          S3-ZK-0006 RA downstream
       |                      |                                   |
       v                      v                                   v
S3-ZK-0015 Lagrangian -> S3-ZK-0003 Lattice              S3-ZK-0009 Information Loss
                              |                                   |
                              v                                   v
                       S3-ZK-0004 Product                 S3-ZK-0013 Current RA fact
                                                                  |
                                                                  v
                                                        S3-ZK-0028 Config boundary
                                                                  |
                                                                  v
                                                        S3-ZK-0031 Enablement != quality
```

P4 production evidence resolved one major branch of this graph: the existing RA mechanism was present, but native default-off configuration forced an avoidable early collapse into frame canonicalization.

## Cluster B — Ternary virtualization

```text
                  S3-ZK-0016 Semantic Trit
                         |
                         v
               S3-ZK-0017 Representation Flexibility
                  /          |             \
                 v           v              v
       S3-ZK-0018 Basis  S3-ZK-0023 V-ISA  S3-ZK-0024 Conversion Graph
                 \           |              /
                  \          v             /
                   ---- S3-ZK-0019 State Minimization
                               |
                               v
                        S3-ZK-0020 Partitions
```

## Cluster C — Information/proof preservation

```text
S3-ZK-0009 Information Loss
        |
        +--> S3-ZK-0021 Information-Loss Metrics
        |          |
        |          +--> S3-ZK-0029 Causal Metric Hierarchy
        |          |
        |          v
        |    S3-ZK-0027 Lossless-Lowering Contract
        |          |
        |          +--> S3-ZK-0028 Config Boundary
        |          |
        |          v
        |    S3-ZK-0030 Metadata State Space
        |
        v
S3-ZK-0022 Proof Facts ---> S3-ZK-0025 Bounded Fact Language
```

## Post-P4 causal facts

```text
P4 selected transformation:
register allocation becomes native default

RA algorithm redesign:
NO

frame loads:
1549 -> 491

frame stores:
1520 -> 471

metadata accesses:
5638 -> 5638

residual:
REPEATED_MEMORY_STATE_MATERIALIZATION
```

This means ordinary global value residency and memory-state metadata are now separate research targets.

## Three flexibility dimensions

```text
LOCATION_FLEXIBILITY
REPRESENTATION_FLEXIBILITY
PROOF_KNOWLEDGE_FLEXIBILITY
```

Working long-term question:

> Can S3 delay irreversible decisions across all three dimensions until semantic, resource or ABI constraints actually require collapse?

P4 gives one positive data point for this philosophy, but does not prove the broader architecture.

## Promotion queue after P4

Current highest-value experiments:

1. `S3-EXP-0014` memory-state metadata provenance;
2. `S3-EXP-0015` SSA destruction vs metadata staging;
3. `S3-EXP-0013` compiler information-loss boundary audit, refocused after P4;
4. `S3-EXP-0009` exact current S3 trit semantics/lowering map;
5. `S3-EXP-0010` exhaustive ternary primitive-basis oracle;
6. `S3-EXP-0012` ternary representation conversion graph vs exact oracle;
7. `S3-EXP-0011` semantic state minimization before branch lowering;
8. `S3-EXP-0001` binary materialization min-cut vs exact oracle;
9. `S3-EXP-0003` Lagrangian capacity relaxation vs exact multi-value oracle;
10. `S3-EXP-0008` forward-availability/backward-necessity frontier.

`S3-EXP-0002 RA OFF vs RA ON` is now `SUPPORTED_BY_P4` rather than unresolved.

No production P5 implementation should be selected until metadata provenance and SSA-destruction attribution are quantitatively separated.

## P5-PREWORK additions

| ID | Title | Status |
|---|---|---|
| S3-ZK-0035 | Dynamic frequency changes the value of metadata evidence | SUPPORTED_FOR_JSMN_AND_FOCUSED_CORPORA |
| S3-ZK-0036 | Proven initialization checks are a bounded elision population | SUPPORTED_FOR_EXACT_JSMN_CORPUS |
| S3-ZK-0037 | Phi relevance is conditional on materialization | SUPPORTED_AS_REFINED_MODEL |
| S3-ZK-0038 | TADDR blocks complete hosted differential closure | NEGATIVE_RESULT |

P5-PREWORK did not establish a full required/avoidable partition. Only 324
static checks and 356 JSMN dynamic checks are directly proven; the residual
population remains UNKNOWN/UNMEASURED. The campaign decision is
MORE_RESEARCH_REQUIRED.

## P5-RESEARCH-CLOSURE additions

| ID | Title | Status |
|---|---|---|
| S3-ZK-0039 | Reset trace coverage is not semantic deadness coverage | SUPPORTED_NEGATIVE_RESULT |
| S3-ZK-0040 | Memory reset byte weighting must square object length | SUPPORTED_FOR_JSMN_TRACE |
| S3-ZK-0041 | Temporary TADDR closure is an emulator experiment, not production support | SUPPORTED_FOR_O0_CORPUS |
| S3-ZK-0042 | O1 slice optimizer verifier failure remains an independent limitation | NEGATIVE_RESULT |
| S3-ZK-0043 | Frame metadata slot reuse was not observed | OPEN_NEGATIVE_RESULT |

P5-RESEARCH-CLOSURE reproduced 14367 allocated-memory reset bytes and found
13340 direct required bytes, 1024 overwrite candidates and 3 lifetime-end
candidates. Alias, call, failure, phi/loop and exact-oracle closure remain
open; promotion is not authorized.

## CI/P5 autonomous campaign additions

`S3-ZK-0044` records that trigger duplication, rather than missing correctness
gates, was the dominant measured Actions cost. The research branch alone
consumed 3716.766667 job minutes; 197 same-SHA push/PR pairs proved
8068.350000 redundant push-side minutes. PR #173 applies trigger precision,
PR-only cancellation, pip caching and a narrow Docker path without deleting
coverage.

`S3-ZK-0045` records the O1 slice finding: metadata loss in SSA-to-IR lowering
was a real verifier/correctness bug, fixed in PR #172 and merged as
229811359948cf8e12848036882edaa89108a9fa. The old limitation must not remain
in future P5 reports.

`S3-ZK-0046` records the post-P4 reprofile. Eight workloads passed emulator and
Linux native execution; JSMN dominates current code size and compile time, but
no sound dynamic per-value attribution or semantic reset-deadness proof exists.
The correct promotion decision is `NO_VALID_TARGET_YET`, not a speculative P5.

`S3-ZK-0047` records the fresh P5 v2 rebase. Across 15 workloads, repeated
x86-64 emitter materialization of the bounded instruction limit was isolated as
a small sound transformation boundary. A signed imm32 compare removed the
per-instruction `movabs r11` while preserving the wide-limit fallback; the
prototype reduced aggregate O1 native instructions by 4.748% and text by
1.694%. PR #174 merged this capability. This does not establish spill,
initialization deadness, SSA, or generic RA optimization.

`S3-ZK-0048` records the P6 simplicity-first result. Across the same 15-workload
post-P5 corpus, 7351 static one-use non-F64 constant materializations were
observed and 7347 were signed-imm32 eligible; the dynamic eligible population
was 200250. The smallest sound fix reused the existing destination writer to
lower eligible `TCONST` values directly, preserving initialized-state marking
and retaining the wide/F64 fallback. PR #175 merged the capability with an
exact-head full-suite exit of 0 and green natural CI. The result is a local
instruction-selection simplification, not evidence for generic operand-form
optimization, register-allocation redesign, bounds elimination, or
initialization-state weakening.

`S3-ZK-0049` records the P7 direct-consumer result. A `TCMP` value is
conditionally accidental when an adjacent same-block `TBR3` consumes it and
liveness proves no successor observer; otherwise the materialization remains
necessary. Fresh evidence found 566 static and 66 dynamic eligible pairs. PR
#176 merged the local emitter fusion with the conservative fallback intact.

## P8.1 local-evidence additions

| S3-ZK-0050 | First useful work is measured at the process boundary | SUPPORTED_BASELINE |
| S3-ZK-0051 | Initialization state is an observed native commitment boundary | SUPPORTED_OBSERVER_BOUNDARY |
| S3-ZK-0052 | P8.1 found no valid production target yet | NEGATIVE_RESULT |
| [[S3-ZK-0053]] | Workflow provenance is execution provenance | SUPPORTED_BOUNDED_MODEL |

| [[S3-ZK-0054]] | A possibility ledger does not by itself authorize a rewrite | NEGATIVE_RESULT |

## P8.3 path-complete memory-state necessity

`S3-ZK-0055` records that path-complete necessity and dynamic hotness are
separate evidence layers. A bounded definite register-init-check population was
measured, but it is emulator-only, has no native structural effect, and lacks a
proof-bearing Assembly/runtime contract with checked fallback. P8.3 is
`NO_VALID_TARGET_YET`.

## P8 final production closure

`S3-ZK-0056` records the merged P8 result: a bounded fail-closed native
recomputation can consume validated Assembly facts without adding forgeable
public proof metadata. PR #178 removed only proven redundant native
initialization checks, preserved the checked fallback, and passed the exact
candidate Linux full suite. Runtime and compile-time measurements remain
unavailable under a comparable protocol.

## P9 causal frame and representation attribution

| [[S3-ZK-0057]] | Observed frame residency is not established spill causality | NEGATIVE_RESULT |

`S3-EXP-0032` records the P9 selection experiment. A validated
`MODELLED_NATIVE_DYNAMIC_COUNT` sidecar model covered 15 workloads without
rerunning the frozen external benchmark. Direct indexed addressing falsified
the current fixed-array base-reload hypothesis, while 5431 observed
stack-resident frame-value events were only 3.793895956018% of the O1 model
and did not establish spill causality. P9 therefore closes as
`NO_VALID_TARGET_YET`; the next smallest experiment is proof-bearing
loop-carried bounds/validity analysis with checked fallback and failure-order
controls.

## P9.1 bounds and validity contract attribution

| [[S3-ZK-0058]] | A hot safety family can still have no sound optimization target | NEGATIVE_RESULT |

`S3-EXP-0033` reproduced the P9 model exactly across 15 workloads. Explicit
safety realization was 65224 modelled dynamic x86 lines, but the minimum
local-constant, success-edge, loop and same-object check-reuse models found no
proven eligible site. Bounds and memory initialization remain material;
`AVOIDABLE_DYNAMIC=0`. P9.1 closes as `NO_VALID_TARGET_YET`.
