# S3-ZK-0012 — Is residence benefit submodular in a useful restricted domain?

```text
TYPE=QUESTION
STATUS=OPEN
CREATED=2026-08-12
```

## Atomic question

For some restricted S3 region/cost model, does the benefit function `F(S)` of keeping a set `S` of values resident exhibit diminishing returns/submodularity?

## Origin

```text
SOURCE_DERIVED + HYPOTHESIS
```

Submodular functions have strong combinatorial optimization structure. The S3 connection is speculative.

## Candidate definition

```text
F(S) = weighted frame/load/store/copy cost avoided
       when values in S remain location-flexible/resident
```

Test the diminishing-returns form for A ⊆ B and x ∉ B:

```text
F(A ∪ {x}) - F(A) >= F(B ∪ {x}) - F(B)
```

## Why it matters

If a useful model is submodular, greedy/approximation techniques may have theoretical guarantees. If not, the counterexample identifies interactions such as register pressure, phi coupling, or call preservation that create complementarity instead of diminishing returns.

## Connections

```text
[[S3-ZK-0012]] --related-to--> [[S3-ZK-0008]]
[[S3-ZK-0012]] --related-to--> [[S3-ZK-0005]]
[[S3-ZK-0007]] --can-test--> [[S3-ZK-0012]]
```

## Falsifier

Enumerate small value sets and find A ⊆ B, x ∉ B violating diminishing returns under the exact defined cost model.

A minimal violation should be preserved as a negative-result note rather than hidden.
