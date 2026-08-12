# S3-ZK-0007 — Tiny-CFG exact optimization can provide an optimality oracle

```text
TYPE=HYPOTHESIS
STATUS=OPEN
CREATED=2026-08-12
```

## Atomic claim

For tiny CFGs/value sets, an intentionally exponential exact search can quantify the best achievable representation/materialization cost under an explicit simplified model and therefore measure the optimality gap of production heuristics.

## Origin

```text
COMBINATORIAL_OPTIMIZATION_BRIDGE + HYPOTHESIS
```

## S3 implication

Instead of asking whether generated code 'looks good', compute:

```text
BASELINE_COST
HEURISTIC_COST
ORACLE_COST
OPTIMALITY_GAP = HEURISTIC_COST - ORACLE_COST
```

Possible cost components:

```text
stores
loads
copies
rematerializations
call-preservation operations
weighted dynamic frequency
```

## Constraints

The oracle:

- is not production code by default;
- must model semantics conservatively;
- should remain bounded to tiny cases;
- is useful even when the optimal problem is NP-hard.

## Connections

```text
[[S3-ZK-0007]] --measures--> [[S3-ZK-0005]]
[[S3-ZK-0007]] --measures--> [[S3-ZK-0008]]
[[S3-ZK-0007]] --measures--> [[S3-ZK-0012]]
```

## Falsifier

If the simplified oracle cost has little correlation with actual S3 frame/code/runtime behavior, revise the objective rather than declaring heuristic failure.

## Experiment

Implement brute-force binary location assignment for <= 20 free decisions and compare with the min-cut prototype on cases where the cut model should be exact.
