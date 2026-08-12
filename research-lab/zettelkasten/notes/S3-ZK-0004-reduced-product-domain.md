# S3-ZK-0004 — Representation facts may compose better as a reduced product domain

```text
TYPE=HYPOTHESIS
STATUS=OPEN
CREATED=2026-08-12
```

## Atomic claim

S3 representation knowledge may be more precise and maintainable when decomposed into orthogonal facts and recombined, rather than encoded in one monolithic enum.

## Origin

```text
SOURCE_DERIVED + HYPOTHESIS
```

Program-analysis literature shows analyses can be combined through products/reduced products. The S3 bridge is to split representation state into independently meaningful dimensions.

## Candidate components

```text
LocationAvailability = {virtual/register, memory}
MemoryFreshness      = {valid, stale, nonexistent}
Observability         = {private, address_observed, foreign_visible}
Rematerializability   = {yes, no}
CallSurvival          = {safe, clobbered, unknown}
```

The real product must be minimized by experiment.

## Connections

```text
[[S3-ZK-0003]] --alternative-to--> [[S3-ZK-0004]]
[[S3-ZK-0010]] --supports--> [[S3-ZK-0004]]
```

## Falsifier

If cross-product state explosion or complex reduction rules add more compiler complexity than useful precision, prefer a simpler lattice/domain.

## Experiment

Model a small set of S3 cases in both a monolithic residence domain and a product domain; compare state count, transfer simplicity, and precision at joins.
