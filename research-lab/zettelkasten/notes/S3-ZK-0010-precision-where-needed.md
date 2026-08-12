# S3-ZK-0010 — Approximation should be introduced only where it buys something

```text
TYPE=BRIDGE
STATUS=OPEN
CREATED=2026-08-12
```

## Atomic claim

A global S3 representation analysis need not use the same conservative precision everywhere; approximation should be introduced specifically where it is needed for convergence or compile-time cost, while preserving precision elsewhere.

## Origin

```text
SOURCE_DERIVED + S3_BRIDGE
```

Abstract-interpretation techniques permit approximate domains and convergence accelerators. The S3 bridge is a **precision budget** for backend analyses rather than globally conservative cross-block behavior.

## Candidate policy

```text
tiny/simple CFG       -> exact finite analysis
ordinary CFG          -> precise monotone fixed point
pathological region   -> bounded/widened analysis
unknown/unsafe state  -> conservative materialization fallback
```

## Connections

```text
[[S3-ZK-0010]] --supports--> [[S3-ZK-0004]]
[[S3-ZK-0011]] --enables--> [[S3-ZK-0010]]
```

## Falsifier

If the representation domain is already finite/small enough that exact fixed-point analysis is inexpensive for all S3 functions, widening/precision tiers add unnecessary complexity and should be rejected.
