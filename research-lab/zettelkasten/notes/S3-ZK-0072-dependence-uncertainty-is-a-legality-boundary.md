# S3-ZK-0072 — Dependence uncertainty is a legality boundary

```text
TYPE=ARCHITECTURE
STATUS=SUPPORTED_AS_RESEARCH_REQUIREMENT
CREATED=2026-08-15
UPDATED=2026-08-15
```

## Atomic claim

For transformations that reorder memory/control effects, inability to rule out a dependence is a legality boundary: uncertainty should preserve the original ordering or take a checked/conservative fallback.

## Origin

```text
SOURCE_DERIVED
INFERENCE
```

### Source claim

Allen & Kennedy treats dependence information as a basis for deciding whether loop/program transformations are legal. Their dependence-testing discussion explicitly uses conservative approximations because exact dependence testing can be expensive, and their loop-transformation chapters separate safety constraints from profitability decisions.

### S3 inference

When future S3 passes reorder operations across loops, branches, loads/stores, calls, or aliases, they must have a proof/analysis contract strong enough to establish the required independence. `UNKNOWN` must not be interpreted as `NO_DEPENDENCE`.

This does not mandate importing a full polyhedral or Fortran-oriented dependence framework into S3.

## S3 implication

Potential P13 verifier/contract questions:

```text
WHAT_EFFECTS_CAN_THIS_PASS_REORDER?
WHAT_DEPENDENCE_FACT_PROVES_THE_REORDERING_SAFE?
WHAT_INVALIDATES_THAT_FACT?
WHAT_HAPPENS_ON_UNKNOWN?
```

The desired fail-closed rule is:

```text
PROVEN_INDEPENDENT -> transformation may be considered
UNKNOWN_OR_DEPENDENT -> preserve semantics/fallback
```

## Connections

```text
[[S3-ZK-0065]] --supports--> [[S3-ZK-0072]]
[[S3-ZK-0064]] --loop-state-context--> [[S3-ZK-0072]]
[[S3-ZK-0072]] --precedes--> [[S3-ZK-0070]]
```

## Falsifier / narrowing condition

Not every S3 transformation is a dependence problem. Pure algebraic rewrites or transformations with other direct semantic proofs may not require dependence analysis. This note applies only where execution ordering or memory/control interaction is semantically relevant.

## Experiment

During P13.2 pass inventory, classify each pass:

```text
REORDERS_EFFECTS=YES/NO
DEPENDENCE_PROOF_REQUIRED=YES/NO
UNKNOWN_POLICY=
```

Then generate P13.3 negative cases for any pass that relies on such facts.

## Evidence

Literature-derived requirement. No claim is made that current S3 needs a new global dependence-analysis subsystem.

## Decision

```text
SUPPORTED_AS_RESEARCH_REQUIREMENT
```