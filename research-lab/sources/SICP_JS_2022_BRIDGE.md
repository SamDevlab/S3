# SICP JS 2022 — S3 Source Bridge

```text
SOURCE=Structure and Interpretation of Computer Programs, JavaScript Edition
AUTHORS=Harold Abelson / Gerald Jay Sussman / Martin Henz / Tobias Wrigstad
ROLE=P1_LANGUAGE_ARCHITECTURE_SEMANTIC_MODEL
DATE=2026-08-15
STATUS=ACTIVE_SOURCE
PERMANENT_CLAIMS_CREATED=NO
PRODUCTION_EFFECT=NONE
```

This source is used for language semantics, evaluator design, abstract-machine reasoning, and staged self-hosting strategy. It is **not** a primary source for SSA/SCCP/LICM correctness or modern backend optimization.

## Inspected sections

```text
3.1.3  The Costs of Introducing Assignment
3.2    The Environment Model of Evaluation
4.1    The Metacircular Evaluator
4.1.7  Separating Syntactic Analysis from Execution
5.1.2  Abstraction in Machine Design
5.2.4  Monitoring Machine Performance
5.4    The Explicit-Control Evaluator
5.5    Compilation
5.5.7  Interfacing Compiled Code to the Evaluator
```

## Source-derived claims

### Assignment changes the semantic model

The source shows that once assignment/state is introduced, names cannot be treated merely as values under a simple substitution model. Evaluation requires an environment model that carries bindings/state and gives expressions meaning relative to that environment.

S3 bridge:

```text
MUTABLE_STATE
=>
SEMANTIC_CONTEXT_MUST_BE_EXPLICIT
```

This supports auditing whether S3 reference/state semantics are represented explicitly enough across lowering. It does not prove any current S3 bug.

### Evaluator semantics can be factored from representation

The metacircular evaluator presents evaluation through an evaluate/apply cycle while using data abstraction for syntax and runtime representation.

S3 bridge:

```text
LANGUAGE_SEMANTICS
!=
ONE_PHYSICAL_REPRESENTATION
```

This is compatible with `IC-008` and the multi-domain S3 direction.

### Analysis and execution can be separated

Section 4.1.7 explicitly separates one-time syntactic analysis from repeated execution by producing execution functions from analyzed components.

S3 bridge:

A semantic/reference evaluator need not duplicate production compiler architecture. It can expose a stable semantic boundary while allowing compiled paths to optimize independently.

### Abstract machines can hide lower-level primitives deliberately

Section 5.1.2 treats complex operations as primitives to focus on a machine-design layer, while noting that they can later be refined into more elementary operations.

S3 bridge:

```text
SEMANTIC_MACHINE_LAYER
        ↓ refinement
LOWER_MACHINE_LAYER
        ↓ refinement
NATIVE_TARGET
```

This provides a conceptual basis for an explicit S3 reference-machine boundary without claiming that S3 should reproduce the SICP register machine literally.

### Machine simulators can provide structural performance observables

Section 5.2.4 instruments stack pushes, maximum stack depth, and instruction counts in the register-machine simulator.

S3 bridge:

```text
SEMANTIC_WORK
→ ABSTRACT_MACHINE_WORK
→ IR/SSA WORK
→ NATIVE WORK
→ RUNTIME
```

This strengthens causal measurement design but does not make abstract instruction count a runtime oracle. `S3-ZK-0068` remains controlling.

### Explicit-control evaluation exposes machine commitments

Section 5.4 transforms the evaluator into an explicit register/stack controller. This makes function calling, argument passing, continuation, environment, and value storage explicit at a lower machine level.

S3 bridge:

A bounded S3 reference machine could make semantic commitments observable before production lowering, improving differential localization between language semantics and backend realization.

### Interpretation and compilation are alternative realizations of the same source semantics

Section 5.5 distinguishes interpretation from compilation and then integrates compiled and interpreted functions in section 5.5.7.

S3 bridge:

```text
REFERENCE_EVALUATION
        ↘
         semantic agreement
        ↗
COMPILED_EXECUTION
```

This motivates a possible future differential oracle for a bounded S3 subset.

## What this source does NOT prove

```text
DOES_NOT_PROVE=S3_NEEDS_METACIRCULAR_INTERPRETER
DOES_NOT_PROVE=S3_SHOULD_REWRITE_COMPILER_IN_S3_NOW
DOES_NOT_PROVE=ABSTRACT_INSTRUCTION_REDUCTION_IMPLIES_RUNTIME_REDUCTION
DOES_NOT_PROVE=O0_IS_ALREADY_A_FORMAL_SEMANTIC_ORACLE
DOES_NOT_PROVE=REGISTER_MACHINE_MODEL_MATCHES_X86_64_COST
```

## Activation map

### P13.0

Use to distinguish:

```text
LANGUAGE_SEMANTICS
REFERENCE_EVALUATION
COMPILER_IR
TARGET_REALIZATION
```

and detect accidental conflation.

### P13.2 / P13.3

Conditional use: if a small reference evaluator/machine can expose a correctness boundary or differential oracle more cheaply than adding production metadata.

Do not build it automatically.

### P14

Use only as a causal instrumentation idea. Abstract-machine counters are intermediate diagnostics, never final runtime proof.

### Future self-hosting

Use as a strategy reference for incremental semantic-layer replacement rather than a wholesale compiler rewrite.

## Lifecycle decision

No official `S3-ZK-*` IDs are allocated from this source yet. Five derived syntheses are recorded as temporary `IC-009..IC-013` candidates and require bounded S3 evidence before promotion.