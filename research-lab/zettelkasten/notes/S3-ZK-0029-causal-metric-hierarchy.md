# S3-ZK-0029 — Causal metrics outrank unstable relative ratios

TYPE: PERMANENT
STATUS: SUPPORTED

## Thesis

Compiler-performance evaluation needs a hierarchy of evidence.

A comparator-relative ratio can move opposite to the compiler's own absolute runtime when the external denominator changes. Therefore structural causal metrics, absolute S3 timings and external-relative ratios must remain distinct.

## P4 evidence

P4 recorded:

```text
GCC-relative geomean:
34.708283588x -> 38.975981467x
```

while absolute S3 runtime moved:

```text
8890.413541 ns/parse -> 8405.052702 ns/parse
S3_RUNTIME_DELTA=-5.46%
```

The GCC denominator varied between runs.

At the same time, direct static frame evidence showed a large targeted change:

```text
frame loads:  1549 -> 491
frame stores: 1520 -> 471
```

## Evidence hierarchy

For a targeted compiler transformation prefer:

```text
1. semantic/correctness proof
2. direct causal structural metric
3. absolute S3 runtime under controlled protocol
4. external comparator-relative ratio
```

The ordering does not make lower levels useless; it prevents a noisy or moving denominator from reversing the interpretation of a directly measured transformation.

## Connections

- [[S3-ZK-0026]] demo success is not maturity
- [[S3-ZK-0021]] information-loss metrics
- [[S3-ZK-0030]] metadata traffic as a separate residual state space

## Source

Production P4 / PR #170, reconciled in `research-lab/reconciliations/P4_20260812.md`.
