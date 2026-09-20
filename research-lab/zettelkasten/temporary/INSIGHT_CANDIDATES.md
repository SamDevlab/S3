# S3 Zettelkasten — Temporary Insight Candidates

```text
DATE=2026-08-15
STATUS=ACTIVE
OFFICIAL_ZETTEL_IDS_ALLOCATED=NO
CANDIDATE_COUNT=16
```

These are second-order syntheses produced by connecting existing supported and open notes after the P13.R0 literature rebase.

They are intentionally **temporary**. Plausibility and explanatory power are not enough for permanent promotion.

Do not cite `IC-*` identifiers as established S3 facts.

## IC-001 — Optimization needs three gates: legality, realizability, profitability

Synthesis:

```text
LEGALITY
Can semantics be preserved?
    ↓
REALIZABILITY
Does the candidate map to a unique, actual compiler/physical effect?
    ↓
PROFITABILITY
Does that realized effect improve the target objective?
```

Connections:

```text
[[S3-ZK-0054]]
[[S3-ZK-0057]]
[[S3-ZK-0061]]
[[S3-ZK-0070]]
[[S3-ZK-0074]]
```

Why temporary:

The two-gate safety/profitability distinction is supported; elevating realizability into a general independent compiler gate is a new S3 synthesis that should be tested against future campaigns.

Candidate experiment:

Require the next optimization campaign to classify each candidate at all three gates and determine whether the extra gate prevents a false promotion or duplicate opportunity estimate.

---

## IC-002 — `UNKNOWN` is typed uncertainty

Synthesis:

```text
CORRECTNESS_UNKNOWN
→ fail closed / preserve behavior

PROFITABILITY_UNKNOWN
→ measure / model / benchmark

DIAGNOSTIC_UNKNOWN
→ classify / collect evidence
```

Connections:

```text
[[S3-ZK-0060]]
[[S3-ZK-0063]]
[[S3-ZK-0065]]
[[S3-ZK-0068]]
[[S3-ZK-0072]]
```

Why temporary:

The component rules are supported, but a compiler-wide uncertainty taxonomy has not yet been audited against active O1 state.

Candidate experiment:

P13.2 should inventory `UNKNOWN`-like states and classify whether each is semantic, profitability or diagnostic uncertainty.

---

## IC-003 — Proof facts require semantic ownership

Synthesis:

```text
A FACT WITHOUT STABLE SEMANTIC OWNERSHIP
IS NOT A TRANSPORTABLE PROOF.
```

A proof-bearing fact may need:

```text
FACT_ID
SEMANTIC_VALUE_OR_SITE_ID
PROPERTY
DERIVED_BY
VALID_REGION
DEPENDENCIES
INVALIDATORS
```

Connections:

```text
[[S3-ZK-0022]]
[[S3-ZK-0065]]
[[S3-ZK-0069]]
[[S3-ZK-0075]]
```

Why temporary:

Correction A proves that incidental object identity is invalid for semantic identity in the relevant compiler state. It does not yet prove S3 needs a general proof-object ownership system.

Candidate experiment:

P13.2 should trace a small set of proof-bearing facts across SSA reconstruction and record whether they are transferred, recomputed, invalidated or accidentally retained.

---

## IC-004 — Lowering boundaries should preserve a minimal proof interface

Synthesis:

A lowering boundary should not preserve maximal source structure merely for optionality. It should explicitly classify downstream-relevant facts as:

```text
PRESERVED
RECOMPUTABLE
INVALIDATED
INTENTIONALLY_DISCARDED
```

Connections:

```text
[[S3-ZK-0009]]
[[S3-ZK-0022]]
[[S3-ZK-0027]]
[[S3-ZK-0065]]
[[S3-ZK-0069]]
```

Why temporary:

The need to preserve required information is supported, but the proposed minimal proof-interface architecture has not been shown necessary or cost-effective for current S3.

Candidate experiment:

Build one boundary recoverability table in P13.2 before designing new metadata.

---

## IC-005 — Representation flexibility needs an explicit commitment boundary

Synthesis:

```text
DELAY IRREVERSIBLE REPRESENTATION CHOICES
UNTIL A JUSTIFYING CONSTRAINT EXISTS,
BUT DO NOT MAXIMIZE OPTIONALITY FOREVER.
```

Possible commitment evidence:

```text
SEMANTIC_REQUIREMENT
ABI_REQUIREMENT
RESOURCE_CONSTRAINT
TARGET_ARCHITECTURE_REQUIREMENT
MEASURED_PROFITABILITY_DECISION
```

Connections:

```text
[[S3-ZK-0009]]
[[S3-ZK-0016]]
[[S3-ZK-0017]]
[[S3-ZK-0071]]
[[S3-ZK-0073]]
```

Why temporary:

This refines an older preservation philosophy but no general S3 commitment-boundary metric has been demonstrated.

Candidate experiment:

When P14 selects a target, identify the earliest irreversible representation commitment and test whether delaying it changes a unique realizable downstream effect.

---

## IC-006 — The optimizer pipeline can be audited as a proof-flow graph

Synthesis:

Pass ordering may be partially modeled through explicit relationships:

```text
PRODUCES
CONSUMES
PRESERVES
INVALIDATES
REQUIRES
```

rather than only by a sequential pass list.

Connections:

```text
[[S3-ZK-0022]]
[[S3-ZK-0065]]
[[S3-ZK-0067]]
[[S3-ZK-0069]]
[[S3-ZK-0075]]
```

Why temporary:

The existing `SSAPassContract` architecture may already encode enough of this information, or the added structure may not justify its complexity.

Candidate experiment:

P13.2 should map the existing pass contracts first. Add no new framework unless missing dependencies cause an observable correctness or invalidation gap.

---

## IC-007 — Negative results can become scoped exclusion constraints

Synthesis:

A closed negative-result note can actively constrain future target selection through:

```text
CLAIM
SCOPE
SHA_RANGE
CORPUS
ASSUMPTIONS
WHAT_WAS_FALSIFIED
WHAT_WAS_NOT_FALSIFIED
REOPEN_CONDITION
```

Connections:

```text
[[S3-ZK-0052]]
[[S3-ZK-0054]]
[[S3-ZK-0057]]
[[S3-ZK-0058]]
[[S3-ZK-0059]]
[[S3-ZK-0060]]
[[S3-ZK-0061]]
[[S3-ZK-0062]]
```

Why temporary:

The permanent index already adopts a reopen rule, but the full exclusion-constraint schema has not yet been applied retroactively to all negative notes.

Candidate experiment:

Before P14 target selection, require each candidate family to reconcile against existing scoped negative results.

---

## IC-008 — Separate semantic domain, legal representations and target realization

Synthesis:

```text
SEMANTIC DOMAIN
    ↓
LEGAL REPRESENTATION SET
    ↓
TARGET-SPECIFIC REALIZATION
```

For example:

```text
trit / tryte / i64 / f64 / reference / aggregate
        ↓
register / immediate / flags / frame / packed / canonical memory / ...
        ↓
x86-64 realization today
```

Candidate policy:

```text
SEMANTICS = LANGUAGE POLICY
LEGAL REPRESENTATIONS = COMPILER POLICY
PHYSICAL SELECTION = TARGET POLICY
```

Connections:

```text
[[S3-ZK-0016]]
[[S3-ZK-0017]]
[[S3-ZK-0067]]
[[S3-ZK-0073]]
```

Why temporary:

This is a promising synthesis for a multi-domain S3, but the compiler architecture has not yet been shown to require this explicit three-layer model.

Candidate experiment:

P13.0/P13.2 should map where semantic type, representation legality and target lowering are currently conflated versus explicitly separated.

---

## IC-009 — Reference evaluation can be an independent semantic boundary

Synthesis:

```text
SOURCE SEMANTICS
      ↓
REFERENCE EVALUATION
      ↓ semantic result/failure

independent from

SOURCE SEMANTICS
      ↓
COMPILER / NATIVE EXECUTION
      ↓ semantic result/failure
```

Source connection:

```text
SICP JS 2022
4.1 Metacircular Evaluator
5.5 Compilation
```

Existing S3 connections:

```text
[[S3-ZK-0026]]
[[S3-ZK-0069]]
[[S3-ZK-0075]]
IC-008
```

Why temporary:

SICP demonstrates evaluator/compiler separation for its language, but S3 has not yet established that a new independent evaluator is necessary or higher-value than existing O0/O1/native differential infrastructure.

Candidate experiment:

P13.0 should first classify the actual current semantic oracle. Only if a concrete oracle gap remains should a bounded evaluator/reference-machine prototype be considered.

---

## IC-010 — Explicit-control machines expose semantic-to-machine commitments

Synthesis:

Transforming an evaluator into an explicit register/stack controller can reveal where implicit semantic mechanisms become concrete state, control, environment and calling commitments.

Source connection:

```text
SICP JS 2022
5.1.2 Abstraction in Machine Design
5.4 Explicit-Control Evaluator
```

Existing S3 connections:

```text
[[S3-ZK-0009]]
[[S3-ZK-0027]]
[[S3-ZK-0067]]
IC-005
IC-008
```

Why temporary:

This is a conceptual machine-design bridge. It does not establish that S3 needs another IR or register-machine implementation.

Candidate experiment:

For one bounded feature with difficult semantics, map source semantic state → first explicit compiler commitment → native realization. Add no new machine layer unless the map exposes an actionable correctness or observability gap.

---

## IC-011 — Abstract-machine cost is a causal layer, not a runtime oracle

Synthesis:

```text
SEMANTIC WORK
→ ABSTRACT-MACHINE WORK
→ IR/SSA WORK
→ NATIVE STRUCTURE
→ RUNTIME
```

Source connection:

```text
SICP JS 2022
5.2.4 Monitoring Machine Performance
```

Existing S3 connections:

```text
[[S3-ZK-0029]]
[[S3-ZK-0068]]
[[S3-ZK-0071]]
```

Why temporary:

Machine-level instruction/stack counters can improve causal localization, but current S3 has no established abstract machine whose counters are known to explain a useful gap.

Candidate experiment:

Only when a future P14 target has an interpreter/reference-machine path, measure matched semantic operations and abstract-machine operations alongside native runtime. Reject the metric if it adds no discriminating information.

---

## IC-012 — Self-hosting should progress by semantic-layer replacement

Synthesis:

```text
REFERENCE SEMANTICS
      ↓
REPLACE ONE IMPLEMENTATION LAYER
      ↓
DIFFERENTIAL VALIDATION
      ↓
NEXT LAYER ONLY IF TRUST INCREASES
```

Source connection:

```text
SICP JS 2022
4.1 evaluator
5.4 explicit control
5.5 compiler
5.5.7 evaluator/compiler integration
```

Existing S3 connections:

```text
[[S3-ZK-0026]]
[[S3-ZK-0069]]
IC-009
```

Why temporary:

This is a migration strategy, not evidence that self-hosting is currently the highest-value S3 milestone.

Candidate experiment:

When self-hosting is eventually authorized, select one semantically bounded compiler component and require differential equivalence before replacing the next layer. Do not start that program during P13 foundation work.

---


### 2026-09-19 evidence update

PRs #301 and #302 provide direct bounded evidence for this synthesis. The self-hosting frontend advanced by keeping an independent hosted frontend as oracle while replacing lexer/parser decisions with ordinary S3-native execution in small semantic slices. Expression precedence/grouping and identifier primaries were added without reference fallback, with Linux x86-64 native qualification and full-suite validation on the functional heads.

This materially strengthens IC-012, but the candidate remains temporary until the approach is exercised across broader statement/block/function-body and later semantic stages. The current evidence supports the method for the bounded source-frontend subset, not a universal self-hosting theorem.


### 2026-09-20 evidence update — statement sequence

PR #303 extended the same replacement strategy from expression/identifier parsing to variable-length statement sequences. Single-, two-, three- and variable-count statement blocks passed, order and block boundaries were preserved, trailing source was rejected, Linux x86-64 qualification reached 55 focused passes, and the full suite passed on the functional head with no reference fallback.

This further strengthens IC-012 for the native source-frontend domain: semantic-layer replacement has now survived a transition from expression trees to ordered statement structure. It remains temporary until broader program structure/semantics exercise the same method.

## IC-013 — Evaluator/compiler agreement can be a bounded differential oracle

Synthesis:

```text
VALID BOUNDED S3 PROGRAM
    ├── REFERENCE EVALUATOR
    ├── O0
    ├── O1
    └── NATIVE
          ↓
RESULT + FAILURE-BEHAVIOR AGREEMENT
```

Source connection:

```text
SICP JS 2022
5.5 interpretation vs compilation
5.5.7 compiled/interpreted interoperability
```

Existing S3 connections:

```text
[[S3-ZK-0063]]
[[S3-ZK-0064]]
[[S3-ZK-0069]]
[[S3-ZK-0072]]
```

Why temporary:

A differential evaluator could strengthen correctness evidence, but only if its implementation errors are sufficiently independent from the compiler and the supported semantic subset is explicit.

Candidate experiment:

If P13.3 exposes a semantic family poorly covered by the existing Python reference/O0/native oracles, prototype the smallest independent evaluator for that family, freeze generated seeds, and compare result and failure semantics. Do not generalize from one subset.

## Promotion rule for insight candidates

An `IC-*` candidate may become a normal `S3-ZK-*` note only after it has:

```text
ATOMIC_CLAIM
SOURCE/NOTE PROVENANCE
CURRENT S3 EVIDENCE
SCOPE
FALSIFIER
BOUNDED VALIDATION PATH
```

Do not promote all thirteen automatically. Negative evidence may reject or merge candidates.

## P14 reconciliation review

The five requested candidates were reviewed against the bounded P14 evidence.
They remain temporary and none was promoted automatically.

```text
IC_ID=IC-001
P14_RELATION=P14 demonstrates the distinction between observed work, avoidability, legality, realizability and profitability for one selected target; it supports gate separation but does not prove a universal independent three-gate architecture or a transformation.
SUPPORTED_COMPONENTS=separate safety, mechanism and objective checks; observed dynamic work is not proof of savings
UNSUPPORTED_COMPONENTS=universal realizability gate; general transformation authorization
NEW_EVIDENCE=P14_1 mixed scaling and P14_2 mechanism localization with WORK_PROVABLY_AVOIDABLE=UNKNOWN
STATUS_AFTER_P14=REMAINS_TEMPORARY_SUPPORTED_IN_PART
PROMOTE_TO_ZETTEL=NO

IC_ID=IC-005
P14_RELATION=P14 shows a dynamic gap without a static structural delta in the measured funnel, so the question of where representation is committed remains relevant; it does not establish a general commitment metric.
SUPPORTED_COMPONENTS=need to identify the commitment boundary before assigning a representation transformation
UNSUPPORTED_COMPONENTS=explicit representation commitment boundary in this workload; general commitment metric
NEW_EVIDENCE=P14_2 typed IR, SSA, de-SSA and Assembly marginal counts were zero while dynamic work was material
STATUS_AFTER_P14=REMAINS_TEMPORARY_OPEN
PROMOTE_TO_ZETTEL=NO

IC_ID=IC-006
P14_RELATION=P13.2 plus the P14 semantic-to-native funnel support stage-aware auditing; P14 did not prove that a general proof-flow graph architecture is required.
SUPPORTED_COMPONENTS=auditing causal stages and preserving IR-level attribution
UNSUPPORTED_COMPONENTS=general proof-flow graph architecture; replacement of existing contracts
NEW_EVIDENCE=P14_2 recorded typed IR, SSA, de-SSA, Assembly, native and dynamic stages
STATUS_AFTER_P14=REMAINS_TEMPORARY_SUPPORTED_AS_METHOD_ONLY
PROMOTE_TO_ZETTEL=NO

IC_ID=IC-007
P14_RELATION=P14 supplies a scoped exclusion: hot dynamic loads/stores, repeated addresses, or structural reductions do not prove avoidability; it does not generalize this exclusion to all workloads.
SUPPORTED_COMPONENTS=negative evidence can constrain the exact P14 target line; unknown is not authorization
UNSUPPORTED_COMPONENTS=general exclusion schema; universal negative result
NEW_EVIDENCE=P14_2 localized LOADS_STORES while leaving WORK_PROVABLY_AVOIDABLE=UNKNOWN
STATUS_AFTER_P14=REMAINS_TEMPORARY_SCOPED
PROMOTE_TO_ZETTEL=NO

IC_ID=IC-011
P14_RELATION=P14 used a semantic -> typed IR -> SSA -> de-SSA -> Assembly -> x86 -> dynamic -> runtime funnel, supporting causal-layer discipline; it does not prove an abstract-machine cost model.
SUPPORTED_COMPONENTS=structural layers and runtime must remain distinct causal evidence
UNSUPPORTED_COMPONENTS=established abstract machine; abstract-machine counters as a runtime oracle
NEW_EVIDENCE=P14_2 identified DYNAMIC_EXECUTION as first material amplification and LOADS_STORES as the dominant extra work class
STATUS_AFTER_P14=REMAINS_TEMPORARY_SUPPORTED_AS_DISCIPLINE_ONLY
PROMOTE_TO_ZETTEL=NO
```

```text
P14_RECONCILIATION_ZETTELS=S3-ZK-0076..S3-ZK-0079
PROMOTE_TO_ZETTEL=NO for IC-001,IC-005,IC-006,IC-007,IC-011
```
### 2026-09-19 evidence update

The independent GenericLexer/GenericParser/SyntaxArena path used by PRs #301/#302 acted as a bounded differential oracle for the separately implemented native S3 frontend. Structural agreement covered token/syntax behavior while native execution was qualified on Linux x86-64.

This strengthens the claim that independent reference/compiler agreement is useful when implementation independence and semantic scope are explicit. It does not yet establish the need for a second full evaluator for all of S3.



### 2026-09-20 evidence update — statement sequence

PR #303 used the same independent-oracle boundary to validate ordered block structure and variable statement count while the native S3 parser made the covered parsing decisions. This broadens the oracle evidence beyond isolated expressions/primaries.

The result strengthens bounded differential-oracle usefulness, but still does not establish a universal evaluator/compiler agreement framework for all S3 semantics.

## IC-014 — Implicit signatures and numeric representation inference are separate research questions

Synthesis:

A concise surface form such as:

```s3
fn soma(a, b):
    return a + b
```

contains at least two separable research problems:

```text
SIGNATURE / SEMANTIC TYPE INFERENCE
        !=
PHYSICAL NUMERIC REPRESENTATION SELECTION
```

A future compiler could infer semantic relationships among parameters/returns while still treating concrete integer width as a later representation decision. This connects to representation-flexibility and commitment-boundary ideas, but does not imply that runtime width promotion is desirable.

Connections:

```text
[[S3-ZK-0016]]
[[S3-ZK-0017]]
IC-005
IC-008
```

Why temporary:

Full parameter inference can require type variables, constraint solving, call-site/interprocedural information, overload resolution and recursion handling. Automatic range-based integer-width selection adds control-flow/range analysis and ABI concerns. Dynamic promotion from i32 to i64 during native execution would complicate stack layout, registers, SSA, aggregates, optimization and FFI.

Current bounded direction:

- keep explicit types as the stable self-hosting target;
- if revisited, test optional return inference separately from parameter inference;
- treat compile-time representation selection separately from semantic type inference;
- keep explicit concrete widths where ABI/FFI/binary contracts require them;
- prefer static width selection before execution over dynamic widening.

Candidate experiment:

Only after the native frontend/type pipeline is mature, choose one deliberately small subset (for example literal-only return inference or one local arithmetic constraint) and measure whether the reduction in annotation burden justifies the semantic/compiler complexity. Do not make this part of the current self-hosting campaign.


## IC-015 — Self-hosting is an enabling milestone, not the terminal objective

Synthesis:

```text
SELF_HOSTING
    ↓
PROGRAM CAPABILITY
    ↓
REAL WORKLOAD
    ↓
INDEPENDENT CORRECTNESS
    ↓
RESOURCE MEASUREMENT
    ↓
USEFUL COMPUTE / COST
```

Self-hosting matters when it improves autonomy, correctness, compiler control, implementation independence or the ability to execute useful programs. It is not by itself the terminal success criterion for S3.

Why temporary:

The current native frontend campaign has not yet reached a representative scientific workload. The strategic claim must be tested by carrying at least one useful program from source through native execution and independent measurement.

Candidate experiment:

Use the first scientific-kernel-oriented workload as a post-frontend maturity gate. Require semantic correctness before performance measurement and report cost per work unit rather than treating self-host completion as the endpoint.

---

## IC-016 — External useful workloads should drive post-core language capability selection

Synthesis:

After a minimal coherent language core exists, additional language/compiler capability should be prioritized by the requirements of useful external workloads rather than by syntax completeness alone.

```text
USEFUL WORKLOAD
    ↓
REQUIRED LANGUAGE/SEMANTIC CAPABILITY
    ↓
IMPLEMENT MINIMUM MISSING CAPABILITY
    ↓
CORRECTNESS
    ↓
MEASUREMENT
```

Current motivating workload:

A future RMSD / pairwise geometric kernel derived from the Biolab molecular-discovery workflow can act as one capability driver, without requiring the S3 compiler repository to absorb Biolab itself.

Why temporary:

One workload can bias a language design if treated as universal. The candidate therefore proposes workload-driven prioritization, not workload-specific semantics.

Candidate experiment:

For the next native-program-frontend campaign, map the capabilities required by a small scientific kernel (local state, iteration, calls, numeric operations, indexed data if needed). Prefer those capabilities over unrelated language expansion, while preserving the real S3 grammar and architecture.

### 2026-09-20 evidence update — native program frontend closure

PR #304 extended the bounded native source slice through typed locals,
assignment, typed parameters, calls, relational expressions and `while`
structure. Focused differential tests passed on Windows and Linux x86-64.
The evidence remains representational: no native semantic/lowering/execution
pipeline, `f64`, indexed data layout, or math primitive was introduced.

This strengthens IC-012's bounded semantic-layer replacement discipline and
provides directional evidence for IC-015/IC-016: a real program structure and
the scientific-kernel requirement map are more informative than syntax
completeness. It does not promote any candidate or establish a scientific
kernel implementation. IC-014 remains unchanged because all signatures in
the slice are explicitly typed.

```text
PR304_NATIVE_PROGRAM_FRONTEND=PASS_FOR_REPRESENTATIONAL_SUBSET
SCIENTIFIC_KERNEL_READINESS=BLOCKED_ARCHITECTURALLY
MICROKERNEL_EXECUTED=NO
PROMOTE_TO_ZETTEL=NO
```

### 2026-09-20 evidence update - native indexed data boundary

The native typed-value line reached a bounded indexed-data contract using
explicit metadata and typed vector payloads. Local construction, lengths, and
payload reads pass, but the hosted semantic model rejects a reference to the
nominal aggregate because references currently require scalar targets. This is
evidence that hosted arrays/vectors/slices do not, by themselves, specify a
native aggregate ABI. Ownership, lifetime, aliasing, and transfer behavior must
be designed before indexed execution or scientific workloads can be promoted.

```text
NATIVE_INDEXED_VALUE_CONTRACT=PASS_FOR_LOCAL_PROBES
NATIVE_AGGREGATE_CALL_BOUNDARY=BLOCKED
NATIVE_INDEXED_EXECUTION=NOT_PROVEN
NUMERIC_WORKLOAD=NOT_STARTED
SCIENTIFIC_WORKLOAD=NOT_STARTED
STRENGTHENS=IC-005,IC-008,IC-012,IC-015,IC-016
IC-014=UNCHANGED
PROMOTE_TO_ZETTEL=NO
```

### 2026-09-20 evidence update - native typed value protocol

The native semantic path generalized its proven i64 execution into an explicit
typed scalar value/result protocol and executed a real f64 call/local/
assignment/return fixture without coercion or hosted fallback. This strengthens
IC-005, IC-008, IC-012, IC-015, and IC-016 while leaving IC-014 unchanged.

The experiment also produced a negative boundary result: hosted fixed arrays
and slices do not define a native collection payload, length, bounds, or
ownership/lifetime representation. Native indexed and scientific workloads
remain blocked until that contract is designed and proven.

```text
NATIVE_TYPED_VALUE_PROTOCOL=PASS
NATIVE_I64=PASS
NATIVE_F64=PASS
NATIVE_INDEXED_DATA=BLOCKED_ARCHITECTURALLY
SCIENTIFIC_WORKLOAD=NOT_STARTED
FULL_SUITE=4021 passed, 312 skipped, 0 failed
PROMOTE_TO_ZETTEL=NO
```
