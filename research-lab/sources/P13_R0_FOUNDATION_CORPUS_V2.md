# P13.R0 — Compiler Foundation Literature Corpus V2

```text
CAMPAIGN=P13.R0
DATE=2026-08-15
STATUS=COMPLETE_EXTENDED
TECHNICAL_SOURCE_COUNT=7
PURPOSE=LITERATURE_REBASE_FOR_COMPILER_FOUNDATION
PRODUCTION_EFFECT=NONE
SOURCE_PDFS_STORED_IN_REPO=NO
SUPERSEDES_SOURCE_SET_SUMMARY=P13_R0_FOUNDATION_CORPUS.md
```

This file extends the first P13.R0 source-set summary after two additional compiler books were supplied. It does not invalidate the earlier five-source analysis or any historical Zettel.

Literature remains a hypothesis/correctness reference, not evidence that S3 behaves as a textbook describes.

## Technical corpus

### 1. Rastello & Bouchez Tichadou (eds.) — SSA-based Compiler Design

Primary role:

```text
SSA
PHI
SSA_CONSTRUCTION
SSA_DESTRUCTION
SSA_RECONSTRUCTION
LIVENESS
LOOPS
REGISTER_ALLOCATION
```

Primary S3 bridge:

Phi and SSA reconstruction are semantic/correctness boundaries. CFG-changing transformations require explicit SSA repair contracts rather than incidental provenance recovery.

Priority: `P0` for P13.1–P13.3.

---

### 2. Møller & Schwartzbach — Static Program Analysis

Primary role:

```text
CFG
LATTICES
MONOTONICITY
JOIN
FIXPOINT
DATAFLOW
MAY_MUST
INITIALIZATION
ABSTRACT_INTERPRETATION
```

Primary S3 bridge:

Analysis facts require an explicit abstract meaning. Definite initialization is a forward-must property; SCCP partial-phi behavior should be reasoned about as an abstract-domain/join question.

Priority: `P0` for P13.1–P13.3.

---

### 3. Patrick Cousot — Principles of Abstract Interpretation

Primary role:

```text
ABSTRACTION_CONCRETIZATION
GALOIS_CONNECTIONS
FIXPOINTS
CHAOTIC_ITERATION
SOUNDNESS
REDUCED_PRODUCTS
```

Primary S3 bridge:

Approximation and convergence strategy must preserve soundness. Combined compiler facts should not be called a lattice/product unless concrete semantics and interaction are defined.

Priority: `P0/P1` for P13.2.

---

### 4. Steven S. Muchnick — Advanced Compiler Design and Implementation

Primary role:

```text
PASS_ORDER
IR_LEVEL
SCCP
LICM
VALUE_NUMBERING
LOOP_OPTIMIZATION
CODEGEN
SCHEDULING
REGISTER_ALLOCATION
```

Primary S3 bridge:

Pass order and IR level are causal variables. Attribution should locate the first stage where information/work materially changes instead of assigning a generic `optimizer` cause.

Priority: `P0/P1` for P13 and P14.

---

### 5. Bryant & O'Hallaron — Computer Systems: A Programmer's Perspective, 3e

Primary role:

```text
BINARY_REPRESENTATION
X86_64
DATA_MOVEMENT
BRANCHES
CALLS
STACK_REGISTERS
PERFORMANCE
MEMORY_HIERARCHY
LINKING
LINUX_SYSTEMS
```

Primary S3 bridge:

S3 must be a competent conventional binary systems language. Static/dynamic structural instruction counts are diagnostic rather than sufficient runtime oracles.

Priority: `P0/P1` for P14 and native systems maturity.

---

### 6. Cooper & Torczon — Engineering a Compiler, supplied 2nd edition

Confirmed supplied edition:

```text
TITLE=Engineering a Compiler
EDITION=Second Edition
AUTHORS=Keith D. Cooper / Linda Torczon
COPYRIGHT=2012
```

The supplied second edition is sufficient for the current P13/P14 questions; no replacement is required merely to obtain a newer edition.

Relevant inspected material:

- compiler organization into front end / optimizer / back end;
- IR taxonomy and SSA;
- procedure/linkage and runtime structures;
- code shape, storage locations, arrays, branches, loops and calls;
- optimization safety and profitability;
- data-flow, dominance, phi placement and translation out of SSA;
- value identity versus name identity;
- choosing optimization sequences;
- instruction selection;
- instruction scheduling;
- register allocation, including SSA-based allocation and de-SSA copy pressure.

Source-derived guidance:

```text
SAFETY != PROFITABILITY
VALUE_IDENTITY != NAME_IDENTITY
LOCAL_BACKEND_IMPROVEMENT != GLOBAL_BACKEND_IMPROVEMENT
OPTIMIZATION_SEQUENCE_IS_A_VARIABLE
```

Primary S3 bridges:

1. A transformation needs an explicit semantic-safety proof and a separate objective-specific profitability gate.
2. Correction A gains a strong conceptual bridge: semantic value/site identity must not be confused with incidental host-object or textual-name identity.
3. Scheduling, register allocation, renaming and code shape interact; a local reduction can create downstream pressure or false dependencies.
4. Translation out of SSA can add copies and register demand, reinforcing `S3-ZK-0069` without proving de-SSA is the current runtime bottleneck.

What this source does **not** prove:

- it does not prove S3 should adopt any particular optimization sequence;
- it does not prove P12 runtime loss came from register pressure or scheduling;
- it does not make every Python object-identity comparison invalid; Correction A applies to semantic identity uses.

Priority: `P0` for P13.1/P13.2, `P1` for P14.

---

### 7. Allen & Kennedy — Optimizing Compilers for Modern Architectures: A Dependence-Based Approach

Confirmed supplied source:

```text
AUTHORS=Randy Allen / Ken Kennedy
FOCUS=dependence-based high-performance compilation
```

Relevant inspected material:

- compiler challenges for pipelines, superscalar/vector/parallel execution and memory hierarchy;
- dependence theory and dependence testing;
- conservative testing where exact dependence reasoning is expensive;
- loop-carried and loop-independent dependences;
- SSA/data-flow as preliminary transformations;
- legality and profitability of loop interchange;
- scalar expansion/renaming;
- loop fusion/distribution and ordering constraints;
- control dependence;
- register-usage improvement and scalar replacement;
- cache management and blocking;
- scheduling and interprocedural analysis.

Source-derived guidance:

```text
DEPENDENCE_INFORMATION_CAN_BE_A_LEGALITY_CONTRACT
UNKNOWN_DEPENDENCE_MUST_NOT_MEAN_INDEPENDENT
LEGAL_TRANSFORMATION != PROFITABLE_TRANSFORMATION
PROFITABILITY_CAN_BE_TARGET_ARCHITECTURE_DEPENDENT
RAW_DEPENDENCE_COUNT != UNIQUE_REALIZABLE_SAVING
```

Primary S3 bridges:

1. Future transformations that reorder effects need an explicit proof/analysis contract; uncertainty should preserve ordering or use a conservative fallback.
2. Do not import a full dependence/polyhedral framework unless S3 evidence requires it. First inventory which active passes actually reorder relevant effects.
3. P14 should distinguish transformation legality from machine-specific profitability.
4. Opportunity census must deduplicate overlapping evidence that maps to the same physical saving.
5. Dependence and memory/register optimization literature is particularly relevant if P14 selects loops, arrays, memory traffic or scheduling as the next target.

What this source does **not** prove:

- it does not prove Fortran/vector-machine strategies are profitable for S3/x86-64;
- it does not authorize loop transformation when S3 alias/call/failure semantics are unknown;
- it does not establish a current S3 dependence-analysis deficiency.

Priority: `P1` for P13.2/P13.3 and `P0/P1` if P14 selects loops/memory/control/data-dependence.

---

## Excluded accidental source

`Engineering Education — Aims & Goals for the Eighties` remains excluded. It is an engineering-education conference report, not a compiler-engineering text.

```text
CORPUS_STATUS=EXCLUDED
```

## Seven-source synthesis

The active literature foundation is now:

```text
SSA / PHI / RECONSTRUCTION
        +
ABSTRACT DOMAIN / DATAFLOW / FIXPOINT / SOUNDNESS
        +
PASS ORDER / IR LEVEL / IDENTITY / ANALYSIS LIFETIME
        +
OPTIMIZATION SAFETY / PROFITABILITY
        +
DEPENDENCE / REORDERING LEGALITY
        +
CODE SHAPE / SCHEDULING / REGISTER ALLOCATION
        +
X86-64 / MEMORY HIERARCHY / TARGET RUNTIME
```

The most important research posture after this extension is:

```text
CORRECTNESS FIRST
LEGALITY EXPLICIT
PROFITABILITY SEPARATE
TARGET EFFECT MEASURED
OPPORTUNITY COUNTS DEDUPLICATED
```

## P13/P14 activation map

### P13.1

Primary:

```text
SSA-based Compiler Design
Static Program Analysis
Engineering a Compiler
Muchnick
```

Use for Correction A/B, LICM loop-phi and SCCP partial-phi extraction/validation.

### P13.2

Primary:

```text
Static Program Analysis
Principles of Abstract Interpretation
SSA-based Compiler Design
Engineering a Compiler
Muchnick
```

Conditional:

```text
Allen/Kennedy
```

only where active S3 passes reorder effects or need dependence contracts.

### P13.3

Use the literature to generate discriminating negative/merge/loop/dependence cases, not to copy textbook languages wholesale.

### P14

Primary:

```text
CS:APP
Engineering a Compiler
Muchnick
Allen/Kennedy when target family involves loops/memory/dependence
Computer Architecture: A Quantitative Approach (existing corpus)
```

Runtime remains the final performance oracle for runtime-oriented claims.

## Reading policy

```text
ACTIVE_S3_QUESTION
→ RELEVANT_SOURCE_PASSAGE
→ SOURCE_CLAIM
→ S3_INFERENCE
→ FALSIFIER
→ EXPERIMENT/VERIFIER
→ STATUS
```

Do not add more books until an active S3 question exposes a concrete literature gap.
