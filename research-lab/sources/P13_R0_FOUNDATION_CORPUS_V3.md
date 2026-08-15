# P13.R0 — Compiler Foundation Literature Corpus V3

```text
CAMPAIGN=P13.R0
DATE=2026-08-15
STATUS=COMPLETE_EXTENDED
TECHNICAL_SOURCE_COUNT=8
PURPOSE=LITERATURE_REBASE_FOR_COMPILER_AND_LANGUAGE_FOUNDATION
PRODUCTION_EFFECT=NONE
SOURCE_FILES_STORED_IN_REPO=NO
SUPERSEDES_SOURCE_SET_SUMMARY=P13_R0_FOUNDATION_CORPUS_V2.md
```

V3 preserves all seven compiler/system sources from V2 and adds one language-semantics / abstract-machine source. Literature remains a research input, not evidence that current S3 behaves as a source describes.

## Active technical corpus

```text
1. SSA-based Compiler Design — Rastello / Bouchez Tichadou
2. Static Program Analysis — Møller / Schwartzbach
3. Principles of Abstract Interpretation — Cousot
4. Advanced Compiler Design and Implementation — Muchnick
5. Computer Systems: A Programmer's Perspective, 3e — Bryant / O'Hallaron
6. Engineering a Compiler, supplied 2e — Cooper / Torczon
7. Optimizing Compilers for Modern Architectures — Allen / Kennedy
8. Structure and Interpretation of Computer Programs, JavaScript Edition — Abelson / Sussman / Henz / Wrigstad
```

`Engineering Education — Aims & Goals for the Eighties` remains excluded as a non-compiler technical source for this corpus.

## Source 8 — SICP JS

Primary role:

```text
LANGUAGE_SEMANTICS
ENVIRONMENT_MODEL
STATE_AND_IDENTITY
REFERENCE_EVALUATION
METACIRCULAR_EVALUATION
ANALYSIS_VS_EXECUTION
ABSTRACT_MACHINE
REGISTER_MACHINE_SIMULATION
MACHINE_INSTRUMENTATION
EXPLICIT_CONTROL
INTERPRETATION_VS_COMPILATION
INCREMENTAL_SELF_HOSTING_REFERENCE
```

Priority:

```text
P1=P13.0_LANGUAGE_ARCHITECTURE
P1=future_reference_evaluator_or_self_hosting_work
P2=P13.2/P13.3_if_a_bounded_semantic_oracle_is_needed
P2=P14_causal_instrumentation_only
```

Inspected sections and detailed bridges are recorded in `SICP_JS_2022_BRIDGE.md`.

## New S3 bridges introduced by source 8

### Semantic context must survive stateful semantics

Assignment/state invalidates models that treat a mutable name as merely a value. For S3 this motivates an explicit audit of where reference/state/environment semantics become concrete compiler state.

This is a bridge, not evidence of a current defect.

### Reference evaluation and compiled execution can be independent realizations

A reference evaluator can preserve the language meaning while production compilation remains free to use different internal/physical representations.

Potential future architecture:

```text
S3 SOURCE
   │
   ├── REFERENCE EVALUATOR / REFERENCE MACHINE
   │          │
   │          └── semantic result / failure behavior
   │
   └── O0 / O1 / NATIVE
              │
              └── semantic result / failure behavior

DIFFERENTIAL AGREEMENT
```

No new evaluator is authorized by literature alone.

### Abstract-machine cost is an intermediate causal layer

SICP's machine simulator demonstrates that execution can be instrumented for instruction count, stack operations and stack depth before reasoning about a physical target.

For S3:

```text
SEMANTIC_WORK
→ ABSTRACT_MACHINE_WORK
→ IR/SSA WORK
→ ASSEMBLY/NATIVE WORK
→ RUNTIME
```

This does **not** override `S3-ZK-0068`: fewer structural instructions remain insufficient to infer lower runtime.

### Self-hosting should be staged by semantic boundaries

The progression evaluator → explicit-control machine → compiler → interpreter/compiler integration provides a useful model for incremental implementation replacement.

S3 inference:

```text
PRESERVE_REFERENCE_SEMANTICS
        ↓
REPLACE_ONE_IMPLEMENTATION_LAYER
        ↓
DIFFERENTIAL_VALIDATE
        ↓
ADVANCE
```

This is preferable as a research strategy to a wholesale self-hosting rewrite, but is not yet a production plan.

## Eight-source synthesis

The active foundation now spans:

```text
LANGUAGE SEMANTICS / EVALUATION MODEL
        +
SSA / PHI / RECONSTRUCTION
        +
ABSTRACT DOMAIN / DATAFLOW / FIXPOINT / SOUNDNESS
        +
PASS ORDER / IR LEVEL / IDENTITY / ANALYSIS LIFETIME
        +
OPTIMIZATION SAFETY / REALIZATION / PROFITABILITY
        +
DEPENDENCE / REORDERING LEGALITY
        +
CODE SHAPE / SCHEDULING / REGISTER ALLOCATION
        +
X86-64 / MEMORY HIERARCHY / TARGET RUNTIME
```

## P13 activation map

### P13.0

Add explicit reality-map rows for:

```text
REFERENCE_SEMANTICS_SOURCE=
REFERENCE_EVALUATOR_STATUS=
O0_ROLE=
O1_ROLE=
NATIVE_ROLE=
SEMANTIC_ORACLE_BOUNDARY=
STATE/ENVIRONMENT_MODEL=
```

Do not assume O0 is a formal reference evaluator merely because it is less optimized.

### P13.1

No change to the primary correctness extraction sources. SICP is secondary context only.

### P13.2 / P13.3

If existing oracles leave a bounded semantic gap, evaluate whether a small evaluator/reference-machine oracle has higher expected value than adding more production mechanisms. Do not build one by default.

### P14

Abstract-machine counters may be added only as causal diagnostics if they answer the selected target question. Final runtime claims still require target runtime measurement.

## Reading policy

```text
ACTIVE_S3_QUESTION
→ RELEVANT_SOURCE_PASSAGE
→ SOURCE_CLAIM
→ S3_INFERENCE
→ LIFECYCLE_CLASS
→ FALSIFIER
→ BOUNDED_VALIDATION
→ STATUS
```

## Final corpus state

```text
TECHNICAL_SOURCE_COUNT=8
SICP_ACTIVE=YES
SICP_PRIORITY=P1
SICP_PERMANENT_ZETTELS_CREATED=NO
SICP_TEMPORARY_INSIGHT_CANDIDATES=5
ADD_MORE_BOOKS_BY_DEFAULT=NO
```