# P13.R0 — Literature and Zettelkasten Rebase V3

```text
DATE=2026-08-15
STATUS=COMPLETE_EXTENDED
TECHNICAL_SOURCE_COUNT=8
P12_18_STARTED=NO
PRODUCTION_CHANGED=NO
MAIN_CHANGED=NO
RESEARCH_BRANCH=research/zettelkasten-lab-20260812
SUPERSEDES_ONLY_SOURCE_SET_SUMMARY=P13_R0_LITERATURE_REBASE_V2.md
```

## Reason for V3

After the seven-source compiler/system foundation was closed, the supplied `Structure and Interpretation of Computer Programs, JavaScript Edition` exposed a concrete gap in the literature map: not SSA/backend engineering, but **language-semantics, reference-evaluation and abstract-machine architecture**.

The source is therefore admitted as P1. It does not reopen P12 and does not authorize self-hosting or a new evaluator implementation by itself.

## Final eight-source foundation

```text
1. SSA-based Compiler Design
2. Static Program Analysis
3. Principles of Abstract Interpretation
4. Advanced Compiler Design and Implementation
5. Computer Systems: A Programmer's Perspective, 3e
6. Engineering a Compiler, supplied 2e
7. Optimizing Compilers for Modern Architectures
8. Structure and Interpretation of Computer Programs, JavaScript Edition
```

## What SICP changes

### A. P13.0 gains a semantic-reference axis

Project reality should distinguish:

```text
LANGUAGE_SEMANTICS
REFERENCE_EVALUATION
O0_COMPILATION
O1_COMPILATION
NATIVE_EXECUTION
```

These roles must not be conflated. In particular:

```text
LESS_OPTIMIZED_COMPILER
!=
FORMAL_REFERENCE_EVALUATOR
```

P13.0 should determine what actually serves as S3's semantic oracle today.

### B. Stateful semantics deserve an explicit model boundary

SICP's assignment/environment progression reinforces that mutable names/state need context beyond a simple value-substitution view.

S3 research question:

```text
WHERE_DO_REFERENCE_STATE_AND_OBSERVABLE_MUTATION
BECOME_EXPLICIT_COMPILER COMMITMENTS?
```

No defect is claimed until source/tests expose one.

### C. A reference evaluator could become a differential oracle

SICP demonstrates evaluator and compiler as distinct realizations of one source-language semantics and later interfaces compiled and interpreted execution.

Potential future S3 experiment:

```text
BOUNDED_VALID_PROGRAM
      │
      ├── REFERENCE_EVALUATOR
      ├── O0
      ├── O1
      └── NATIVE
             ↓
      RESULT/FAILURE AGREEMENT
```

This is an `INSIGHT_CANDIDATE`, not a P13 implementation requirement.

### D. Abstract-machine counters become an optional causal layer

The register-machine simulator explicitly measures stack operations/depth and instruction execution.

S3 may use a similar *concept* when useful:

```text
SEMANTIC WORK
→ REFERENCE/ABSTRACT MACHINE WORK
→ IR/SSA
→ ASSEMBLY/X86
→ RUNTIME
```

The P12.17 lesson remains authoritative: structural reduction is not runtime proof.

### E. Self-hosting gets a safer research strategy

Instead of a wholesale compiler rewrite, the literature suggests a staged path where semantic behavior remains anchored while one implementation layer is replaced and compared.

Candidate strategy:

```text
REFERENCE SEMANTICS
      ↓
ONE BOUNDED SELF-HOSTED LAYER
      ↓
DIFFERENTIAL VALIDATION
      ↓
NEXT LAYER ONLY IF TRUST INCREASES
```

This does not move self-hosting ahead of P13 correctness foundation work.

## New temporary insight candidates

No official Zettel IDs were allocated.

```text
IC-009 Reference evaluation can be an independent semantic boundary
IC-010 Explicit-control machines expose semantic-to-machine commitments
IC-011 Abstract-machine cost is a causal layer, not a runtime oracle
IC-012 Self-hosting should progress by semantic-layer replacement
IC-013 Evaluator/compiler agreement can be a bounded differential oracle
```

They live in `zettelkasten/temporary/INSIGHT_CANDIDATES.md` and require bounded S3 evidence before promotion.

## P13 impact

```text
P13.0=ADD_SEMANTIC_ORACLE_REALITY_MAP
P13.1=UNCHANGED_PRIMARY_PLAN
P13.2=REFERENCE_MACHINE_ORACLE_OPTIONAL_ONLY_IF_GAP_FOUND
P13.3=EVALUATOR_DIFFERENTIAL_OPTIONAL_ONLY_IF_BOUNDED_AND_USEFUL
P13.4=NO_NEW_GATE_YET
```

## P14 impact

```text
ABSTRACT_MACHINE_METRICS=OPTIONAL_DIAGNOSTIC
RUNTIME_FINAL_ORACLE=UNCHANGED
TARGET_PROFITABILITY_POLICY=UNCHANGED
```

## Anti-expansion decision

```text
SICP_ADDED_BECAUSE=CONCRETE_SEMANTICS_ORACLE_GAP
ADD_MORE_BOOKS_BY_DEFAULT=NO
BUILD_NEW_EVALUATOR_NOW=NO
START_SELF_HOSTING_NOW=NO
REOPEN_P12=NO
```

## Final state

```text
P13_R0_RESULT=LITERATURE_REBASE_COMPLETE_EXTENDED_V3
EIGHT_TECHNICAL_SOURCES_CONFIRMED=YES
SICP_SOURCE_BRIDGE=research-lab/sources/SICP_JS_2022_BRIDGE.md
PERMANENT_NOTE_COUNT_UNCHANGED=52
TEMPORARY_OFFICIAL_NOTE_COUNT_UNCHANGED=23
TEMPORARY_INSIGHT_CANDIDATE_COUNT=13
P12_18=NOT_STARTED
NEXT_PHASE=P13.0_PROJECT_REALITY_AND_COMPILER_REBASE
```