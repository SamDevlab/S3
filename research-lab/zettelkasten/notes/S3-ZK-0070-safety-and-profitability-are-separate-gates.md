# S3-ZK-0070 — Safety and profitability are separate optimization gates

```text
TYPE=PERMANENT
STATUS=SUPPORTED
CREATED=2026-08-15
UPDATED=2026-08-15
```

## Atomic claim

A compiler transformation is not justified merely because it is semantically legal, and it is not justified merely because a structural metric improves. Correctness/safety and objective-specific profitability are independent gates.

## Origin

```text
SOURCE_DERIVED
S3_MEASURED
```

### Source claim

Cooper & Torczon, *Engineering a Compiler*, separates optimization into two core questions: safety (preserve program meaning) and profitability (improve the intended objective). Allen & Kennedy repeatedly separates legality/safety of loop transformations from profitability and shows that a legal transformation may still lose useful parallelism or perform poorly for a target architecture.

### S3 inference

Future S3 optimization research should register distinct gates:

```text
SEMANTIC_SAFETY_GATE
MECHANISM_EFFECT_GATE
PROFITABILITY_GATE
```

For runtime-oriented work, the profitability gate ultimately requires runtime evidence. Static IR/x86 reduction may establish mechanism but does not establish runtime profitability.

P12 provides S3-specific supporting evidence: compact-state produced real static/dynamic structural reductions but failed the production runtime objective.

## S3 implication

P13 correctness-only fixes do not need a runtime performance gate.

P14+ performance candidates must never use a structural reduction as a substitute for runtime profitability.

A future optimization whose goal is code size, compile time, energy, or another objective must preregister the corresponding profitability metric rather than inherit a runtime gate blindly.

## Connections

```text
[[S3-ZK-0029]] --supports--> [[S3-ZK-0070]]
[[S3-ZK-0068]] --supports--> [[S3-ZK-0070]]
[[S3-ZK-0070]] --governs--> P14+
```

## Falsifier / narrowing condition

This note would be too broad if `profitability` were interpreted as runtime speed only. The target objective may differ. The invariant is separation of semantic legality from the chosen optimization objective.

## Experiment

For every future optimization candidate, record independently:

```text
SAFETY=
STRUCTURAL_MECHANISM=
PROFITABILITY_OBJECTIVE=
PROFITABILITY_RESULT=
```

## Evidence

P12.13/P12.17 already demonstrate a safe structural reduction that did not realize the desired runtime benefit.

## Decision

```text
SUPPORTED
```