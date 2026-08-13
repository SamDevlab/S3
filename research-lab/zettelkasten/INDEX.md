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
