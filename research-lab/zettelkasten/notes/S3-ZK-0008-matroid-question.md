# S3-ZK-0008 — Do restricted resident sets have matroid-like structure?

```text
TYPE=QUESTION
STATUS=OPEN
CREATED=2026-08-12
```

## Atomic question

In a restricted compiler domain, do sets of logical values that may be kept resident under resource/safety constraints satisfy heredity and an exchange property strong enough to form a matroid?

## Origin

```text
SOURCE_DERIVED + HYPOTHESIS
```

Matroids characterize important independence systems where greedy optimization is exact. The S3 connection is speculative and must be proved or refuted.

## Candidate restricted domain

Start deliberately small:

```text
single register class
no calls
no address-taken values
fixed program region
known pairwise interference
K physical registers
```

Then define what 'independent' means precisely.

## Why it matters

If an appropriate independence system is a matroid, a simple greedy optimizer may have a proof of optimality for that restricted problem. If it is not, the counterexample tells us exactly which compiler interaction breaks greedy structure.

## Connections

```text
[[S3-ZK-0008]] --related-to--> [[S3-ZK-0012]]
[[S3-ZK-0007]] --measures--> [[S3-ZK-0008]]
```

## Falsifier

Find sets A and B of feasible residents with |A| < |B| such that no element of B\A can be added to A while remaining feasible.

A minimal counterexample should become a `NEGATIVE_RESULT` note.
