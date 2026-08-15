# S3-ZK-0065 — Analysis facts need explicit abstract semantics

```text
TYPE=ARCHITECTURE
STATUS=SUPPORTED_AS_RESEARCH_REQUIREMENT
CREATED=2026-08-15
UPDATED=2026-08-15
```

## Atomic claim

Any optimizer fact used to justify a semantics-changing transformation must have a defined abstract meaning: domain, ordering, merge/join behavior, transfer behavior and convergence rule. An implementation-specific flag without that contract is insufficient as proof.

## Origin

```text
SOURCE_DERIVED
INFERENCE
```

Sources:

- Møller & Schwartzbach, *Static Program Analysis*: lattices, monotone frameworks, fixed-point algorithms, transfer functions and soundness;
- Cousot, *Principles of Abstract Interpretation*: concrete/abstract domains, Galois connections, fixpoints, chaotic iterations, reduced products and semantic soundness.

## S3 implication

P13.2 should audit the actual domains relied upon by SCCP, initialization, liveness, loop reasoning and other O1 analyses. The goal is not to rewrite them in a theorem prover; the goal is to make each pass's proof vocabulary explicit enough that `UNKNOWN`, merge and invalidation behavior cannot drift silently.

## Connections

```text
[[S3-ZK-0003]] --candidate domain--> [[S3-ZK-0065]]
[[S3-ZK-0004]] --combined domains--> [[S3-ZK-0065]]
[[S3-ZK-0010]] --approximation discipline--> [[S3-ZK-0065]]
[[S3-ZK-0011]] --fixed point--> [[S3-ZK-0065]]
[[S3-ZK-0022]] --proof facts--> [[S3-ZK-0065]]
```

## Falsifier

If a fact is purely diagnostic and never authorizes transformation, it does not require a sound abstract-semantics contract. This note applies to proof-bearing optimizer facts, not arbitrary telemetry.

## Experiment

Inventory active O1 pass facts and classify each as:

```text
TRANSFORMATION_PROOF_FACT
DIAGNOSTIC_ONLY
CONTROL_METADATA
```

For proof facts, record domain, join, transfer, invalidators and fallback.

## Evidence

Literature establishes the analysis framework. P12 supplies motivation through real phi/fixpoint/provenance failures, but a complete S3 pass inventory remains to be done in P13.2.

## Decision

```text
SUPPORTED_AS_RESEARCH_REQUIREMENT
```
