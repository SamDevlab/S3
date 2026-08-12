# S3-ZK-0011 — Fixed-point convergence is an engineering parameter

```text
TYPE=PERMANENT
STATUS=SUPPORTED
CREATED=2026-08-12
```

## Atomic claim

For iterative program analyses, convergence strategy, precision, and compile-time cost must be engineered together; correctness requires a safe result, not necessarily the most expensive possible precision everywhere.

## Origin

```text
SOURCE_DERIVED
```

Program-analysis literature provides least/greatest fixed-point reasoning and widening/narrowing for convergence control.

## S3 implication

Every new iterative backend analysis should record:

```text
DOMAIN_HEIGHT=
WORKLIST_ORDER=
MONOTONICITY=
CONVERGENCE_BOUND=
WIDENING_USED=
PRECISION_LOSS=
COMPILE_TIME_COST=
```

## Connections

```text
[[S3-ZK-0011]] --supports--> [[S3-ZK-0010]]
[[S3-ZK-0003]] --uses--> [[S3-ZK-0011]]
```

## Experiment

For any proposed global-residence analysis, generate cyclic CFGs and verify termination, deterministic fixed point, and stable results under different block iteration orders.
