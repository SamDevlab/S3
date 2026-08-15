# P13.R0 — Literature and Zettelkasten Rebase V2

```text
DATE=2026-08-15
STATUS=COMPLETE_EXTENDED
TECHNICAL_SOURCE_COUNT=7
P12_18_STARTED=NO
PRODUCTION_CHANGED=NO
MAIN_CHANGED=NO
RESEARCH_BRANCH=research/zettelkasten-lab-20260812
SUPERSEDES_ONLY_SOURCE_SET_SUMMARY=P13_R0_LITERATURE_REBASE.md
```

## Reason for V2

The first P13.R0 closure was written after five technical sources were confirmed. Two intended compiler sources arrived afterwards:

```text
Engineering a Compiler, 2e
Keith D. Cooper / Linda Torczon

Optimizing Compilers for Modern Architectures
Randy Allen / Ken Kennedy
```

This V2 extends the literature map. It does not rewrite or invalidate the earlier P13.R0 evidence.

## Final seven-source foundation

```text
1. SSA-based Compiler Design
2. Static Program Analysis
3. Principles of Abstract Interpretation
4. Advanced Compiler Design and Implementation
5. Computer Systems: A Programmer's Perspective, 3e
6. Engineering a Compiler, supplied 2e
7. Optimizing Compilers for Modern Architectures
```

The accidental `Engineering Education — Aims & Goals for the Eighties` source remains excluded.

## What the two additional books change

### A. Optimization now has three explicitly separate research layers

From Cooper/Torczon plus the existing S3 evidence:

```text
SEMANTIC_SAFETY
        ↓
STRUCTURAL/CAUSAL_MECHANISM
        ↓
OBJECTIVE_SPECIFIC_PROFITABILITY
```

For runtime work:

```text
CORRECTNESS=necessary
STRUCTURAL_REDUCTION=mechanism evidence
RUNTIME=profitability evidence
```

This formalizes the lesson already observed in P12.13–P12.17.

### B. Value identity is promoted to a first-class P13.1 audit axis

Cooper/Torczon's distinction between value identity and name identity combines with S3 Correction A:

```text
HOST_OBJECT_IDENTITY != SEMANTIC_IDENTITY
TEXTUAL_NAME_IDENTITY != VALUE_IDENTITY
```

P13.1 should inspect semantic identity uses across SSA reconstruction, instruction sites and compiler state.

### C. Backend interactions become part of causal attribution

Instruction scheduling, register demand, renaming and allocation can influence one another. Therefore a local backend simplification cannot be assumed to improve end-to-end runtime.

This is a research model, not a diagnosis of P12.17.

### D. Dependence becomes an explicit conditional contract

Allen/Kennedy supports a fail-closed rule for transformations that reorder effects:

```text
PROVEN_INDEPENDENT -> transformation may be considered
DEPENDENT_OR_UNKNOWN -> preserve order / conservative fallback
```

Do not add a full new dependence subsystem without evidence that current S3 passes need one.

### E. Legality and profitability remain separate for loop/memory transformations

A loop transformation can be legal and still lose performance or useful parallelism.

Target architecture may determine the most profitable legal form.

For P14 this strengthens:

```text
TARGET_FINGERPRINT_REQUIRED=YES
MACHINE_INDEPENDENT_STRUCTURE_IS_NOT_RUNTIME_PROOF
```

### F. Opportunity accounting must deduplicate realizable savings

Analysis edges/events/candidate facts may overlap. Multiple pieces of evidence can correspond to one physical effect.

Future census should distinguish:

```text
RAW_EVIDENCE_COUNT
UNIQUE_SEMANTIC_SITES
UNIQUE_PHYSICAL_EFFECTS
PROVABLY_AVOIDABLE_EFFECTS
```

## New Zettels in the extension

```text
S3-ZK-0070
Safety and profitability are separate optimization gates
STATUS=SUPPORTED

S3-ZK-0071
A local compiler improvement can worsen downstream cost
STATUS=SUPPORTED_AS_RESEARCH_MODEL

S3-ZK-0072
Dependence uncertainty is a legality boundary
STATUS=SUPPORTED_AS_RESEARCH_REQUIREMENT

S3-ZK-0073
Profitability is target-architecture dependent
STATUS=SUPPORTED

S3-ZK-0074
Opportunity counts need unique realizable effects
STATUS=SUPPORTED_AS_RESEARCH_REQUIREMENT

S3-ZK-0075
Semantic value identity is not incidental object identity
STATUS=SUPPORTED
```

## Updated P13 priority map

### P13.1 — correctness extraction

Primary literature:

```text
SSA-based Compiler Design
Static Program Analysis
Engineering a Compiler
Muchnick
```

Additional audit axis:

```text
SEMANTIC_IDENTITY_CONTRACT
```

Still required:

```text
Correction A
Correction B
LICM loop-phi
SCCP partial-phi
```

No performance optimization.

### P13.2 — O1 contract hardening

Add to the existing audit:

```text
REORDERS_EFFECTS=
DEPENDENCE_PROOF_REQUIRED=
UNKNOWN_DEPENDENCE_POLICY=
LOCAL_PASS_OBJECTIVE=
DOWNSTREAM_ANALYSES_INVALIDATED=
```

Allen/Kennedy is activated only for passes whose semantics actually involve dependence/reordering.

### P13.3 — differential stress

Add bounded families where relevant:

```text
loop-carried dependencies
alias-sensitive reorderings
load/store ordering
control-dependent operations
call/failure barriers
```

Only if supported by current S3 language/compiler behavior.

### P14 — broad runtime rebase

The causal funnel now explicitly asks:

```text
IS_THE_TRANSFORMATION_LEGAL?
WHAT_LOCAL_MECHANISM_CHANGES?
WHAT_DOWNSTREAM_CONSTRAINTS_CHANGE?
IS_IT_PROFITABLE_ON_THIS_TARGET?
```

Do not infer profitability from code size or dynamic structural instruction count.

## Anti-expansion decision

The literature foundation is now sufficient for the planned P13/P14 campaign.

```text
ADD_MORE_BOOKS_NOW=NO
```

New sources should enter only when an active compiler question exposes a specific missing foundation.

## Final state

```text
P13_R0_RESULT=LITERATURE_REBASE_COMPLETE_EXTENDED
SEVEN_TECHNICAL_SOURCES_CONFIRMED=YES
NEW_ZETTELS=S3-ZK-0070..S3-ZK-0075
P12_COMPACT_STATE_LINE=REMAINS_CLOSED
P12_18=NOT_STARTED
NEXT_PHASE=P13.0_PROJECT_REALITY_AND_COMPILER_REBASE
```
