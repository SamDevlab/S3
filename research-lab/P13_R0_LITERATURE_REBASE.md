# P13.R0 — Literature and Zettelkasten Rebase

```text
DATE=2026-08-15
STATUS=COMPLETE
P12_18_STARTED=NO
PRODUCTION_CHANGED=NO
MAIN_CHANGED=NO
RESEARCH_BRANCH=research/zettelkasten-lab-20260812
```

## Mission

Rebase the S3 research literature around the correctness and compiler-foundation problems actually exposed by P12, without restarting compact-state micro-decomposition and without turning book statements into untested S3 claims.

## Confirmed five-source technical set

```text
1. SSA-based Compiler Design
   Fabrice Rastello / Florent Bouchez Tichadou
   ROLE=SSA_PHI_RECONSTRUCTION_LIVENESS_LOOP_DESSA_RA

2. Static Program Analysis
   Anders Møller / Michael I. Schwartzbach
   ROLE=LATTICE_DATAFLOW_FIXPOINT_MAY_MUST_INITIALIZATION_SOUNDNESS

3. Principles of Abstract Interpretation
   Patrick Cousot
   ROLE=ABSTRACT_SEMANTICS_FIXPOINT_SOUNDNESS_REDUCED_PRODUCT

4. Advanced Compiler Design and Implementation
   Steven S. Muchnick
   ROLE=PASS_ORDER_IR_LEVEL_SCCP_LICM_CODEGEN_RA

5. Computer Systems: A Programmer's Perspective, 3e
   Randal E. Bryant / David R. O'Hallaron
   ROLE=X86_64_BINARY_SYSTEMS_RUNTIME_COST_MEMORY_BRANCH_LINKING
```

The supplied `Engineering Education — Aims & Goals for the Eighties` PDF is not *Engineering a Compiler* and is excluded from the compiler corpus.

## Why the rebase matters now

P12 did not merely test a performance idea. It exposed correctness and architecture pressure around:

```text
SSA
PHI
CFG
SCCP
LICM
FIXPOINT
PROVENANCE
SSA_RECONSTRUCTION
LOWERING_STAGE_PLACEMENT
RUNTIME_COST_INTERPRETATION
```

The new corpus aligns directly with those failure modes.

## Literature-derived corrections to research posture

### A. Phi semantics become a first-class correctness subject

P4-era evidence once said SSA/phi staging was not dominant for a corpus that had no phis/edge copies. That result remains valid only for that corpus.

P12.10–P12.14.2 supplied later evidence that phi and reconstruction semantics are correctness-critical in other workloads.

Therefore:

```text
OLD_SCOPE:
SSA/phi not dominant in P4 JSMN residual

NEW_SCOPE:
true for that corpus only

GLOBAL_CONCLUSION:
NOT AUTHORIZED
```

Do not delete `S3-ZK-0033`; narrow its interpretation by using the newer notes.

### B. SCCP is an abstract-domain contract, not a bag of constant-folding cases

For P13, SCCP must be audited in terms of:

```text
ABSTRACT_STATES
ORDER
JOIN
EXECUTABLE_EDGE_SEMANTICS
TRANSFER
FIXPOINT
UNKNOWN_POLICY
```

The P12.14.2 partially-known-phi bug is evidence that this abstraction contract matters.

### C. LICM must reason about loop-carried state

A loop phi cannot be discarded from invariance reasoning merely because it appears as merge syntax.

P13.1 should isolate and validate the generic loop-phi repair independently from compact-state code.

### D. Initialization proof is definite-path proof

The Static Program Analysis corpus supports the interpretation already suggested by P8:

```text
INITIALIZATION
PROPERTY_OF_PAST=YES
DIRECTION=FORWARD
PROOF_KIND=MUST
```

Future check elimination requires proof on all relevant paths.

### E. Pipeline placement becomes part of causal attribution

Muchnick and the SSA corpus reinforce P12.10/P12.14:

```text
PASS_ORDER
IR_LEVEL
SSA_RECONSTRUCTION
LOWERING_BOUNDARY
```

are research variables.

Future performance studies should search for the first stage where information or work materially changes.

### F. Binary systems competence is a primary S3 requirement

CS:APP is included specifically to prevent the research program from over-centering ternary representation.

S3 should be good at ordinary binary systems work:

```text
i64/f64
x86-64
branches
calls
stack/registers
arrays
memory hierarchy
object files/linking
Linux services
```

Ternary remains a semantic domain, not an absolute machine model.

### G. Runtime remains independent from structural metrics

P12.17 is now a permanent methodological anchor:

```text
DYNAMIC_STRUCTURAL_X86=-28.6103%
RUNTIME_COMPACT=+13.2079% slower
WORK_EQUIVALENCE=PASS
TIMED_REGION_EQUIVALENCE=PASS
```

Therefore:

```text
LESS_IR != FASTER
LESS_STATIC_X86 != FASTER
LESS_DYNAMIC_STRUCTURAL_X86 != FASTER
```

This is not a microarchitectural diagnosis.

## New Zettels

```text
S3-ZK-0063
Partial phi knowledge is not constant proof
STATUS=SUPPORTED

S3-ZK-0064
Loop phis are loop-carried state, not ignorable merge syntax
STATUS=SUPPORTED

S3-ZK-0065
Analysis facts need explicit abstract semantics
STATUS=SUPPORTED_AS_RESEARCH_REQUIREMENT

S3-ZK-0066
Definite initialization is a forward must proof
STATUS=SUPPORTED

S3-ZK-0067
Pass order and IR level are causal variables
STATUS=SUPPORTED

S3-ZK-0068
Structural instruction count is not a runtime oracle
STATUS=SUPPORTED

S3-ZK-0069
SSA reconstruction is a correctness boundary
STATUS=SUPPORTED
```

## P13 priority map after literature rebase

### P13.1 — known correctness extraction

Primary sources:

```text
SSA-based Compiler Design
Static Program Analysis
Muchnick
```

Questions:

```text
Can Correction A be separated cleanly?
Can Correction B be preserved unchanged?
Can LICM loop-phi correctness be extracted independently?
Can SCCP partial-phi correctness be extracted independently?
```

No performance optimization in this phase.

### P13.2 — O1 contract hardening

Primary sources:

```text
Static Program Analysis
Principles of Abstract Interpretation
SSA-based Compiler Design
Muchnick
```

Audit:

```text
PASS_PRECONDITIONS
PASS_POSTCONDITIONS
SSA_PRESERVATION
CFG_CHANGE
PHI_CHANGE
ANALYSIS_INVALIDATION
FIXPOINT
UNKNOWN_POLICY
PASSRESULT_CHANGED_TRUTHFULNESS
```

No replacement pass manager unless the existing architecture is proven insufficient.

### P13.3 — differential stress

Literature role:

Use the formal models to generate discriminating CFG/phi/loop cases; do not translate textbook examples blindly.

High-value generated families:

```text
partial phis
unreachable predecessors
loop-carried phis
multiple loop phis
nested loops
merge after initialization
SCCP↔LICM interactions
SSA reconstruction after CFG mutation
```

### P13.4 — maturity baseline

Freeze the correctness-hardened compiler only after:

```text
FULL_SUITE=PASS
NATIVE=PASS
DIFFERENTIAL_STRESS=PASS
DETERMINISM=PASS
KNOWN_RELEVANT_CORRECTNESS_BUGS=0
```

### P14 — broad runtime rebase

Primary systems sources:

```text
CS:APP
Muchnick
Computer Architecture: A Quantitative Approach (existing corpus)
```

Use static/dynamic structure diagnostically; runtime selects winners.

Do not claim cache/branch/IPC causes without direct evidence.

## Zettelkasten Epoch 2 rule

From P13 onward, every literature-derived note should carry a provenance distinction:

```text
SOURCE_CLAIM=
S3_INFERENCE=
S3_EVIDENCE=
SCOPE=
FALSIFIER=
LATEST_STATUS=
```

Old notes remain historical artifacts. Do not rewrite a valid old corpus result into a global claim. Add a later narrowing or superseding note instead.

## Anti-accumulation rule

Do not add books merely to increase library size.

A source becomes active only when it can answer an active S3 research question.

```text
QUESTION
→ SOURCE
→ BRIDGE
→ FALSIFIABLE CLAIM
→ EXPERIMENT
→ STATUS UPDATE
```

## Final research decision

```text
P13_R0_RESULT=LITERATURE_REBASE_COMPLETE
FIVE_TECHNICAL_SOURCES_CONFIRMED=YES
ACCIDENTAL_ENGINEERING_EDUCATION_SOURCE=EXCLUDED
P12_COMPACT_STATE_LINE=REMAINS_CLOSED
P12_18=NOT_STARTED
NEXT_PHASE=P13.0_PROJECT_REALITY_AND_COMPILER_REBASE
```
